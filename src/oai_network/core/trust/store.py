"""
Trust Store

Persistent storage for trust data (ledgers, scores, feedback).
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional, List
from pathlib import Path
from threading import Lock

from .models import TrustEvent, TrustScore, Feedback, ReputationLedger, TrustEventType


class TrustStore:
    """
    SQLite-based storage for trust data.
    
    Stores:
    - Reputation ledgers (immutable event logs)
    - Current trust scores (cached for performance)
    - Feedback records
    """
    
    def __init__(self, db_path: str = "trust.db"):
        self.db_path = db_path
        self._lock = Lock()
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
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
                        total_interactions INTEGER NOT NULL,
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
                        interaction_id TEXT NOT NULL,
                        rating INTEGER NOT NULL,
                        comment TEXT,
                        timestamp TEXT NOT NULL,
                        verified INTEGER NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_feedback_agent 
                    ON feedback(agent_did)
                """)
                
                conn.commit()
            finally:
                conn.close()
    
    def add_event(self, event: TrustEvent):
        """Add a trust event to the ledger."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT INTO trust_events (
                        id, agent_did, event_type, timestamp,
                        interaction_id, counterparty_did, capability_name,
                        latency_ms, cost, feedback_text, feedback_rating,
                        metadata, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.id,
                    event.agent_did,
                    event.event_type.value,
                    event.timestamp.isoformat(),
                    event.interaction_id,
                    event.counterparty_did,
                    event.capability_name,
                    event.latency_ms,
                    event.cost,
                    event.feedback_text,
                    event.feedback_rating,
                    json.dumps(event.metadata),
                    event.source,
                ))
                conn.commit()
            finally:
                conn.close()
    
    def get_ledger(self, agent_did: str, since: Optional[datetime] = None) -> ReputationLedger:
        """Get reputation ledger for an agent."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                query = "SELECT * FROM trust_events WHERE agent_did = ?"
                params = [agent_did]
                
                if since:
                    query += " AND timestamp >= ?"
                    params.append(since.isoformat())
                
                query += " ORDER BY timestamp ASC"
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                events = []
                for row in rows:
                    event = TrustEvent(
                        id=row[0],
                        agent_did=row[1],
                        event_type=TrustEventType(row[2]),
                        timestamp=datetime.fromisoformat(row[3]),
                        interaction_id=row[4],
                        counterparty_did=row[5],
                        capability_name=row[6],
                        latency_ms=row[7],
                        cost=row[8],
                        feedback_text=row[9],
                        feedback_rating=row[10],
                        metadata=json.loads(row[11]) if row[11] else {},
                        source=row[12],
                    )
                    events.append(event)
                
                return ReputationLedger(
                    agent_did=agent_did,
                    events=events,
                )
            finally:
                conn.close()
    
    def save_score(self, score: TrustScore):
        """Save or update a trust score."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO trust_scores (
                        agent_did, overall_score, interaction_score, feedback_score,
                        identity_score, behavior_score, total_interactions,
                        successful_interactions, failed_interactions, avg_latency_ms,
                        total_feedback, positive_feedback, negative_feedback,
                        identity_verified, policy_violations, last_updated,
                        last_interaction, confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    score.agent_did,
                    score.overall_score,
                    score.interaction_score,
                    score.feedback_score,
                    score.identity_score,
                    score.behavior_score,
                    score.total_interactions,
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
                ))
                conn.commit()
            finally:
                conn.close()
    
    def get_score(self, agent_did: str) -> Optional[TrustScore]:
        """Get current trust score for an agent."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT * FROM trust_scores WHERE agent_did = ?",
                    (agent_did,)
                )
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                return TrustScore(
                    agent_did=row[0],
                    overall_score=row[1],
                    interaction_score=row[2],
                    feedback_score=row[3],
                    identity_score=row[4],
                    behavior_score=row[5],
                    total_interactions=row[6],
                    successful_interactions=row[7],
                    failed_interactions=row[8],
                    avg_latency_ms=row[9],
                    total_feedback=row[10],
                    positive_feedback=row[11],
                    negative_feedback=row[12],
                    identity_verified=bool(row[13]),
                    policy_violations=row[14],
                    last_updated=datetime.fromisoformat(row[15]),
                    last_interaction=datetime.fromisoformat(row[16]) if row[16] else None,
                    confidence=row[17],
                )
            finally:
                conn.close()
    
    def add_feedback(self, feedback: Feedback):
        """Add feedback record."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT INTO feedback (
                        id, agent_did, rater_did, interaction_id,
                        rating, comment, timestamp, verified
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    feedback.id,
                    feedback.agent_did,
                    feedback.rater_did,
                    feedback.interaction_id,
                    feedback.rating,
                    feedback.comment,
                    feedback.timestamp.isoformat(),
                    1 if feedback.verified else 0,
                ))
                conn.commit()
            finally:
                conn.close()
    
    def get_feedback(self, agent_did: str, limit: int = 100) -> List[Feedback]:
        """Get feedback for an agent."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT * FROM feedback WHERE agent_did = ? ORDER BY timestamp DESC LIMIT ?",
                    (agent_did, limit)
                )
                rows = cursor.fetchall()
                
                feedback_list = []
                for row in rows:
                    feedback = Feedback(
                        id=row[0],
                        agent_did=row[1],
                        rater_did=row[2],
                        interaction_id=row[3],
                        rating=row[4],
                        comment=row[5],
                        timestamp=datetime.fromisoformat(row[6]),
                        verified=bool(row[7]),
                    )
                    feedback_list.append(feedback)
                
                return feedback_list
            finally:
                conn.close()
    
    def get_top_agents(self, limit: int = 10, min_interactions: int = 5) -> List[TrustScore]:
        """Get top agents by trust score."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute("""
                    SELECT * FROM trust_scores 
                    WHERE total_interactions >= ?
                    ORDER BY overall_score DESC, confidence DESC
                    LIMIT ?
                """, (min_interactions, limit))
                
                rows = cursor.fetchall()
                
                scores = []
                for row in rows:
                    score = TrustScore(
                        agent_did=row[0],
                        overall_score=row[1],
                        interaction_score=row[2],
                        feedback_score=row[3],
                        identity_score=row[4],
                        behavior_score=row[5],
                        total_interactions=row[6],
                        successful_interactions=row[7],
                        failed_interactions=row[8],
                        avg_latency_ms=row[9],
                        total_feedback=row[10],
                        positive_feedback=row[11],
                        negative_feedback=row[12],
                        identity_verified=bool(row[13]),
                        policy_violations=row[14],
                        last_updated=datetime.fromisoformat(row[15]),
                        last_interaction=datetime.fromisoformat(row[16]) if row[16] else None,
                        confidence=row[17],
                    )
                    scores.append(score)
                
                return scores
            finally:
                conn.close()
    
    def get_stats(self) -> dict:
        """Get overall trust system statistics."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                # Total agents
                cursor = conn.execute("SELECT COUNT(DISTINCT agent_did) FROM trust_events")
                total_agents = cursor.fetchone()[0]
                
                # Total events
                cursor = conn.execute("SELECT COUNT(*) FROM trust_events")
                total_events = cursor.fetchone()[0]
                
                # Events by type
                cursor = conn.execute("""
                    SELECT event_type, COUNT(*) 
                    FROM trust_events 
                    GROUP BY event_type
                """)
                events_by_type = dict(cursor.fetchall())
                
                # Average trust score
                cursor = conn.execute("SELECT AVG(overall_score) FROM trust_scores")
                avg_score = cursor.fetchone()[0] or 0.0
                
                return {
                    'total_agents': total_agents,
                    'total_events': total_events,
                    'events_by_type': events_by_type,
                    'average_trust_score': avg_score,
                }
            finally:
                conn.close()