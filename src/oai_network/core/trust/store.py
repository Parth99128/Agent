"""
Trust Store

Persistent storage for trust data (ledgers, scores, feedback).
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional, List
from threading import Lock

from .models import TrustEvent, TrustScore, Feedback, ReputationLedger, TrustEventType
from oai_network.core.observability import (
    get_logger, log_agent_action, log_error, get_trace_id
)


class _AwaitableResult:
    """
    A wrapper that holds a synchronous result but can also be awaited.

    This allows methods to be called both synchronously (``store.add_event(e)``)
    and asynchronously (``await store.add_event(e)``) while executing the
    underlying work immediately in both cases.
    """

    __slots__ = ("_result",)

    def __init__(self, result):
        self._result = result

    def __await__(self):
        async def _coro():
            return self._result
        return _coro().__await__()

    # Allow transparent attribute access for sync callers
    def __iter__(self):
        return iter(self._result) if self._result is not None else iter([])

    def __len__(self):
        return len(self._result) if self._result is not None else 0

    def __getitem__(self, index):
        return self._result[index]

    def __repr__(self):
        return f"_AwaitableResult({self._result!r})"


class TrustStore:
    """
    SQLite-based storage for trust data.

    Stores:
    - Reputation ledgers (immutable event logs)
    - Current trust scores (cached for performance)
    - Feedback records
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._lock = Lock()
        # Use a single persistent connection so :memory: databases persist across queries
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.logger = get_logger("oai-network-trust-store")
        self._init_db()

    def _init_db(self):
        """Initialize database tables."""
        conn = self._conn
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trust_events (
                id TEXT PRIMARY KEY,
                agent_did TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                interaction_id TEXT,
                counterparty_did TEXT,
                capability_name TEXT,
                latency_ms REAL,
                cost REAL,
                feedback_text TEXT,
                feedback_rating INTEGER,
                metadata TEXT,
                source TEXT,
                value REAL,
                weight REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trust_events_agent
            ON trust_events(agent_did)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trust_events_timestamp
            ON trust_events(timestamp)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS trust_scores (
                agent_did TEXT PRIMARY KEY,
                overall_score REAL NOT NULL,
                interaction_score REAL NOT NULL,
                feedback_score REAL NOT NULL,
                identity_score REAL NOT NULL,
                behavior_score REAL NOT NULL,
                event_count INTEGER NOT NULL,
                interaction_count INTEGER NOT NULL,
                successful_interactions INTEGER NOT NULL,
                failed_interactions INTEGER NOT NULL,
                avg_latency_ms REAL NOT NULL,
                total_feedback INTEGER NOT NULL,
                positive_feedback INTEGER NOT NULL,
                negative_feedback INTEGER NOT NULL,
                identity_verified INTEGER NOT NULL,
                policy_violations INTEGER NOT NULL,
                last_updated TEXT NOT NULL,
                last_interaction TEXT,
                confidence REAL NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                agent_did TEXT NOT NULL,
                rater_did TEXT NOT NULL,
                interaction_id TEXT,
                rating INTEGER NOT NULL,
                comment TEXT,
                timestamp TEXT NOT NULL,
                verified INTEGER NOT NULL,
                capability TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_agent
            ON feedback(agent_did)
        """)

        conn.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _event_type_value(event_type) -> str:
        """Normalize event_type to a string."""
        if hasattr(event_type, "value"):
            return event_type.value
        return str(event_type)

    def _row_to_event(self, row: sqlite3.Row) -> TrustEvent:
        """Convert a database row to a TrustEvent."""
        return TrustEvent(
            id=row["id"],
            event_type=row["event_type"],
            source_did=row["counterparty_did"] or "",
            target_did=row["agent_did"],
            value=row["value"] if row["value"] is not None else 1.0,
            weight=row["weight"] if row["weight"] is not None else 1.0,
            timestamp=datetime.fromisoformat(row["timestamp"]),
            interaction_id=row["interaction_id"],
            capability_name=row["capability_name"],
            latency_ms=row["latency_ms"],
            cost=row["cost"],
            feedback_text=row["feedback_text"],
            feedback_rating=row["feedback_rating"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            source=row["source"] or "system",
        )

    def _row_to_feedback(self, row: sqlite3.Row) -> Feedback:
        """Convert a database row to a Feedback."""
        return Feedback(
            id=row["id"],
            from_did=row["rater_did"],
            to_did=row["agent_did"],
            interaction_id=row["interaction_id"],
            rating=row["rating"],
            comment=row["comment"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            verified=bool(row["verified"]),
        )

    def _row_to_score(self, row: sqlite3.Row) -> TrustScore:
        """Convert a database row to a TrustScore."""
        return TrustScore(
            agent_did=row["agent_did"],
            overall_score=row["overall_score"],
            interaction_score=row["interaction_score"],
            feedback_score=row["feedback_score"],
            identity_score=row["identity_score"],
            behavior_score=row["behavior_score"],
            event_count=row["event_count"],
            interaction_count=row["interaction_count"],
            successful_interactions=row["successful_interactions"],
            failed_interactions=row["failed_interactions"],
            avg_latency_ms=row["avg_latency_ms"],
            total_feedback=row["total_feedback"],
            positive_feedback=row["positive_feedback"],
            negative_feedback=row["negative_feedback"],
            identity_verified=bool(row["identity_verified"]),
            policy_violations=row["policy_violations"],
            last_updated=datetime.fromisoformat(row["last_updated"]),
            last_interaction=datetime.fromisoformat(row["last_interaction"]) if row["last_interaction"] else None,
            confidence=row["confidence"],
        )

    # ------------------------------------------------------------------
    # Synchronous core methods (used by TrustCalculator.calculate)
    # ------------------------------------------------------------------

    def _add_event_sync(self, event: TrustEvent):
        """Synchronously add a trust event to the ledger."""
        trace_id = get_trace_id()
        conn = self._conn
        agent_did = event.target_did
        event_type_value = self._event_type_value(event.event_type)
        
        log_agent_action(self.logger, "add_trust_event", agent_did, trace_id,
                        event_type=event_type_value,
                        interaction_id=event.interaction_id)
        
        conn.execute(
            """
            INSERT INTO trust_events (
                id, agent_did, event_type, timestamp,
                interaction_id, counterparty_did, capability_name,
                latency_ms, cost, feedback_text, feedback_rating,
                metadata, source, value, weight
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                agent_did,
                event_type_value,
                event.timestamp.isoformat(),
                event.interaction_id,
                event.source_did,
                event.capability_name,
                event.latency_ms,
                event.cost,
                event.feedback_text,
                event.feedback_rating,
                json.dumps(event.metadata),
                event.source,
                event.value,
                event.weight,
            ),
        )
        conn.commit()
        
        log_agent_action(self.logger, "add_trust_event_complete", agent_did, trace_id,
                        event_id=event.id)

    def _get_events_sync(self, agent_did: str, limit: int = 10, offset: int = 0) -> List[TrustEvent]:
        """Synchronously get events for an agent with pagination."""
        conn = self._conn
        cursor = conn.execute(
            """
            SELECT * FROM trust_events
            WHERE agent_did = ?
            ORDER BY timestamp ASC
            LIMIT ? OFFSET ?
            """,
            (agent_did, limit, offset),
        )
        rows = cursor.fetchall()
        return [self._row_to_event(row) for row in rows]

    def _add_feedback_sync(self, feedback: Feedback):
        """Synchronously add a feedback record."""
        conn = self._conn
        conn.execute(
            """
            INSERT INTO feedback (
                id, agent_did, rater_did, interaction_id,
                rating, comment, timestamp, verified, capability
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback.id,
                feedback.to_did,
                feedback.from_did,
                feedback.interaction_id,
                feedback.rating,
                feedback.comment,
                feedback.timestamp.isoformat(),
                1 if feedback.verified else 0,
                getattr(feedback, "capability", None),
            ),
        )
        conn.commit()

        # Also create a trust event so the calculator can factor in the feedback
        event_type = (
            TrustEventType.POSITIVE_FEEDBACK
            if feedback.is_positive()
            else TrustEventType.NEGATIVE_FEEDBACK
            if feedback.is_negative()
            else TrustEventType.POSITIVE_FEEDBACK  # neutral (3) treated as mild positive
        )
        event = TrustEvent(
            event_type=event_type,
            source_did=feedback.from_did,
            target_did=feedback.to_did,
            interaction_id=feedback.interaction_id,
            feedback_text=feedback.comment,
            feedback_rating=feedback.rating,
            timestamp=feedback.timestamp,
            metadata={"feedback_id": feedback.id},
        )
        self._add_event_sync(event)

    def _get_feedback_sync(self, agent_did: str, limit: int = 100) -> List[Feedback]:
        """Synchronously get feedback for an agent."""
        conn = self._conn
        cursor = conn.execute(
            """
            SELECT * FROM feedback
            WHERE agent_did = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (agent_did, limit),
        )
        rows = cursor.fetchall()
        return [self._row_to_feedback(row) for row in rows]

    def get_ledger(self, agent_did: str, since: Optional[datetime] = None) -> ReputationLedger:
        """Get reputation ledger for an agent (synchronous, used by calculator)."""
        trace_id = get_trace_id()
        conn = self._conn
        
        log_agent_action(self.logger, "get_ledger", agent_did, trace_id)
        
        if since:
            cursor = conn.execute(
                """
                SELECT * FROM trust_events
                WHERE agent_did = ? AND timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (agent_did, since.isoformat()),
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM trust_events
                WHERE agent_did = ?
                ORDER BY timestamp ASC
                """,
                (agent_did,),
            )
        rows = cursor.fetchall()
        events = [self._row_to_event(row) for row in rows]
        
        log_agent_action(self.logger, "get_ledger_complete", agent_did, trace_id,
                        events_count=len(events))
        
        return ReputationLedger(agent_did=agent_did, events=events)

    def save_score(self, score: TrustScore):
        """Save or update a trust score."""
        trace_id = get_trace_id()
        conn = self._conn
        
        log_agent_action(self.logger, "save_trust_score", agent_did, trace_id,
                        overall_score=score.overall_score)
        
        conn.execute(
            """
            INSERT OR REPLACE INTO trust_scores (
                agent_did, overall_score, interaction_score, feedback_score,
                identity_score, behavior_score, event_count, interaction_count,
                successful_interactions, failed_interactions, avg_latency_ms,
                total_feedback, positive_feedback, negative_feedback,
                identity_verified, policy_violations, last_updated,
                last_interaction, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                score.agent_did,
                score.overall_score,
                score.interaction_score,
                score.feedback_score,
                score.identity_score,
                score.behavior_score,
                score.event_count,
                score.interaction_count,
                score.successful_interactions,
                score.failed_interactions,
                score.avg_latency_ms,
                score.total_feedback,
                score.positive_feedback,
                score.negative_feedback,
                1 if score.identity_verified else 0,
                score.policy_violations,
                score.last_updated.isoformat(),
                score.last_interaction.isoformat() if score.last_interaction else None,
                score.confidence,
            ),
        )
        conn.commit()
        
        log_agent_action(self.logger, "save_trust_score_complete", agent_did, trace_id)

    def get_score(self, agent_did: str) -> Optional[TrustScore]:
        """Get current cached trust score for an agent."""
        trace_id = get_trace_id()
        conn = self._conn
        
        log_agent_action(self.logger, "get_trust_score", agent_did, trace_id)
        
        cursor = conn.execute(
            "SELECT * FROM trust_scores WHERE agent_did = ?",
            (agent_did,),
        )
        row = cursor.fetchone()
        if not row:
            log_agent_action(self.logger, "get_trust_score_not_found", agent_did, trace_id)
            return None
        
        log_agent_action(self.logger, "get_trust_score_complete", agent_did, trace_id,
                        overall_score=row["overall_score"])
        
        return self._row_to_score(row)

    def get_top_agents(self, limit: int = 10, min_interactions: int = 5) -> List[TrustScore]:
        """Get top agents by trust score."""
        trace_id = get_trace_id()
        conn = self._conn
        
        log_agent_action(self.logger, "get_top_agents", agent_did, trace_id,
                        limit=limit, min_interactions=min_interactions)
        
        cursor = conn.execute(
            """
            SELECT * FROM trust_scores
            WHERE interaction_count >= ?
            ORDER BY overall_score DESC, confidence DESC
            LIMIT ?
            """,
            (min_interactions, limit),
        )
        rows = cursor.fetchall()
        results = [self._row_to_score(row) for row in rows]
        
        log_agent_action(self.logger, "get_top_agents_complete", agent_did, trace_id,
                        count=len(results))
        
        return results

    def get_stats(self) -> dict:
        """Get overall trust system statistics."""
        trace_id = get_trace_id()
        conn = self._conn
        
        log_agent_action(self.logger, "get_stats", agent_did, trace_id)
        
        cursor = conn.execute("SELECT COUNT(DISTINCT agent_did) FROM trust_events")
        total_agents = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(*) FROM trust_events")
        total_events = cursor.fetchone()[0]

        cursor = conn.execute(
            "SELECT event_type, COUNT(*) FROM trust_events GROUP BY event_type"
        )
        events_by_type = dict(cursor.fetchall())

        cursor = conn.execute("SELECT AVG(overall_score) FROM trust_scores")
        avg_score = cursor.fetchone()[0] or 0.0

        stats = {
            "total_agents": total_agents,
            "total_events": total_events,
            "events_by_type": events_by_type,
            "average_trust_score": avg_score,
        }
        
        log_agent_action(self.logger, "get_stats_complete", agent_did, trace_id, **stats)
        
        return stats

    # ------------------------------------------------------------------
    # Dual sync/async methods
    #
    # These methods execute synchronously and return an _AwaitableResult
    # so they can also be used with `await` in async tests.
    # ------------------------------------------------------------------

    def add_event(self, event: TrustEvent):
        """Add a trust event to the ledger (sync, also awaitable)."""
        self._add_event_sync(event)
        return _AwaitableResult(None)

    def get_events_for_agent(
        self, agent_did: str, limit: int = 10, offset: int = 0
    ) -> List[TrustEvent]:
        """Get events for an agent with pagination (sync, also awaitable)."""
        result = self._get_events_sync(agent_did, limit, offset)
        return _AwaitableResult(result)

    def add_feedback(self, feedback: Feedback):
        """Add a feedback record (sync, also awaitable)."""
        self._add_feedback_sync(feedback)
        return _AwaitableResult(None)

    def get_feedback_for_agent(self, agent_did: str) -> List[Feedback]:
        """Get feedback for an agent (sync, also awaitable)."""
        result = self._get_feedback_sync(agent_did, 100)
        return _AwaitableResult(result)

    def get_trust_score(
        self, agent_did: str, calculator: "TrustCalculator"
    ) -> TrustScore:
        """Calculate and return the trust score for an agent (sync, also awaitable)."""
        result = calculator.calculate(agent_did, store=self)
        return _AwaitableResult(result)

    # Backwards-compatible sync alias
    def get_feedback(self, agent_did: str, limit: int = 100) -> List[Feedback]:
        """Get feedback for an agent (sync, backwards compat)."""
        return self._get_feedback_sync(agent_did, limit)

    def close(self):
        """Close the database connection."""
        self._conn.close()