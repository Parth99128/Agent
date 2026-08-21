"""
Delegation Manager

Manages the delegation lifecycle - requesting, tracking, and completing delegations.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Any
from .models import (
    DelegationRequest, DelegationResponse, DelegationTask,
    DelegationResult, DelegationChain, DelegationStatus,
    DelegationPolicy
)


class DelegationManager:
    """
    Manages task delegation between agents.

    Features:
    - Find capable agents via discovery
    - Track delegation progress
    - Handle retries and timeouts
    - Support delegation chains (multi-hop)
    """

    def __init__(
        self,
        discovery_service=None,
        negotiation_protocol=None,
        policy: Optional[DelegationPolicy] = None,
        trust_store=None,
    ):
        self.discovery = discovery_service
        self.negotiation = negotiation_protocol
        self.policy = policy or DelegationPolicy()
        self.trust_store = trust_store
        self.tasks: dict[str, DelegationTask] = {}
        self.chains: dict[str, DelegationChain] = {}

    async def delegate(self, request: DelegationRequest) -> DelegationResponse:
        """
        Delegate a task to another agent.

        If delegatee_did is not specified, will discover the best agent.

        Returns:
            DelegationResponse with accepted status and task_id
        """
        # Find delegatee if not specified
        delegatee_did = request.delegatee_did
        if delegatee_did is None:
            delegatee_did = await self._find_best_agent(request.capability, request.delegator_did)
            if not delegatee_did:
                return DelegationResponse(
                    request_id=request.id,
                    delegatee_did=None,
                    accepted=False,
                    rejection_reason=f"No capable agent found for capability: {request.capability}"
                )

        # Create task
        task_id = str(uuid.uuid4())
        task = DelegationTask(
            task_id=task_id,
            request_id=request.id,
            delegator_did=request.delegator_did,
            delegatee_did=delegatee_did,
            capability=request.capability,
            input_data=request.input_data,
            status=DelegationStatus.PENDING,
        )

        self.tasks[task_id] = task

        return DelegationResponse(
            request_id=request.id,
            delegatee_did=delegatee_did,
            accepted=True,
            task_id=task_id,
        )

    async def _find_best_agent(self, capability_name: str, requester_did: str) -> Optional[str]:
        """Find the best agent for a capability."""
        if self.discovery is None:
            return None

        from ..discovery.models import DiscoveryQuery
        query = DiscoveryQuery(
            query=capability_name,
            max_results=5,
        )

        results = await self.discovery.discover(query)
        if not results:
            return None

        return results[0].agent_did

    async def execute_task(self, task_id: str) -> DelegationResult:
        """
        Execute a delegated task.

        Returns:
            DelegationResult with output data and status
        """
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        task.status = DelegationStatus.IN_PROGRESS
        task.started_at = datetime.now(timezone.utc)

        # Simulate execution (in real implementation, would call the delegatee agent)
        import time
        start = time.time()
        output_data = {"result": "success", "capability": task.capability, "input": task.input_data}
        elapsed_ms = (time.time() - start) * 1000

        task.status = DelegationStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)
        task.progress = 1.0

        # Record trust event for successful interaction
        if self.trust_store:
            from ..trust.models import TrustEvent, TrustEventType
            event = TrustEvent(
                event_type=TrustEventType.INTERACTION_SUCCESS,
                source_did=task.delegator_did,
                target_did=task.delegatee_did,
                interaction_id=task_id,
                capability_name=task.capability,
                latency_ms=elapsed_ms,
                weight=1.0,
            )
            self.trust_store.add_event(event)

        return DelegationResult(
            task_id=task_id,
            status=DelegationStatus.COMPLETED,
            output_data=output_data,
            execution_time_ms=elapsed_ms,
        )

    async def get_task_status(self, task_id: str) -> Optional[DelegationStatus]:
        """Get the status of a task."""
        task = self.tasks.get(task_id)
        if not task:
            return None
        return task.status

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        task = self.tasks.get(task_id)
        if not task:
            return False

        task.status = DelegationStatus.FAILED
        task.completed_at = datetime.now(timezone.utc)
        task.last_error = "Task cancelled"

        # Record trust event for failed interaction
        if self.trust_store:
            from ..trust.models import TrustEvent, TrustEventType
            event = TrustEvent(
                event_type=TrustEventType.INTERACTION_FAILURE,
                source_did=task.delegator_did,
                target_did=task.delegatee_did,
                interaction_id=task_id,
                capability_name=task.capability,
                weight=1.0,
            )
            self.trust_store.add_event(event)

        return True

    async def record_task_failure(self, task_id: str, error: str, timeout: bool = False) -> bool:
        """Record a task failure for trust tracking."""
        task = self.tasks.get(task_id)
        if not task:
            return False

        task.status = DelegationStatus.FAILED
        task.completed_at = datetime.now(timezone.utc)
        task.last_error = error

        # Record trust event for failed interaction
        if self.trust_store:
            from ..trust.models import TrustEvent, TrustEventType
            event_type = TrustEventType.INTERACTION_TIMEOUT if timeout else TrustEventType.INTERACTION_FAILURE
            event = TrustEvent(
                event_type=event_type,
                source_did=task.delegator_did,
                target_did=task.delegatee_did,
                interaction_id=task_id,
                capability_name=task.capability,
                weight=1.0,
            )
            self.trust_store.add_event(event)

        return True

    async def create_chain(
        self,
        delegator_did: str,
        steps: List[dict[str, Any]],
    ) -> DelegationChain:
        """
        Create a delegation chain for multi-hop delegation.

        Args:
            delegator_did: DID of the original delegator
            steps: List of step dicts with 'capability' and 'input_data'

        Returns:
            DelegationChain with task IDs
        """
        chain_id = str(uuid.uuid4())
        chain = DelegationChain(
            chain_id=chain_id,
            root_delegator_did=delegator_did,
            tasks=[],
        )

        for step in steps:
            task_id = str(uuid.uuid4())
            task = DelegationTask(
                task_id=task_id,
                request_id=str(uuid.uuid4()),
                delegator_did=delegator_did,
                delegatee_did=None,
                capability=step.get("capability", ""),
                input_data=step.get("input_data", {}),
                status=DelegationStatus.PENDING,
            )
            self.tasks[task_id] = task
            chain.add_task(task_id)

        self.chains[chain_id] = chain
        return chain

    async def execute_chain(self, chain_id: str) -> List[DelegationResult]:
        """Execute all tasks in a delegation chain."""
        chain = self.chains.get(chain_id)
        if not chain:
            raise ValueError(f"Chain {chain_id} not found")

        results = []
        for task_id in chain.tasks:
            result = await self.execute_task(task_id)
            results.append(result)

        chain.status = DelegationStatus.COMPLETED
        chain.completed_at = datetime.now(timezone.utc)

        return results

    async def retry_task(self, task_id: str) -> DelegationResponse:
        """Retry a failed task by creating a new task."""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Create a new task with the same parameters
        new_task_id = str(uuid.uuid4())
        new_task = DelegationTask(
            task_id=new_task_id,
            request_id=str(uuid.uuid4()),
            delegator_did=task.delegator_did,
            delegatee_did=task.delegatee_did,
            capability=task.capability,
            input_data=task.input_data,
            status=DelegationStatus.PENDING,
        )
        self.tasks[new_task_id] = new_task

        return DelegationResponse(
            request_id=task.request_id,
            delegatee_did=task.delegatee_did,
            accepted=True,
            task_id=new_task_id,
        )

    def get_task(self, task_id: str) -> Optional[DelegationTask]:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def get_tasks_by_delegator(self, delegator_did: str) -> List[DelegationTask]:
        """Get all tasks for a delegator."""
        return [
            task for task in self.tasks.values()
            if task.delegator_did == delegator_did
        ]

    def get_tasks_by_delegatee(self, delegatee_did: str) -> List[DelegationTask]:
        """Get all tasks for a delegatee."""
        return [
            task for task in self.tasks.values()
            if task.delegatee_did == delegatee_did
        ]

    def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """Remove old completed tasks."""
        now = datetime.now(timezone.utc)
        cutoff = now.timestamp() - (max_age_hours * 3600)

        to_remove = []
        for task_id, task in self.tasks.items():
            if task.is_terminal() and task.completed_at:
                if task.completed_at.timestamp() < cutoff:
                    to_remove.append(task_id)

        for task_id in to_remove:
            del self.tasks[task_id]

        return len(to_remove)