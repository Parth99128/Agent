"""
Delegation Manager

Manages the delegation lifecycle - requesting, tracking, and completing delegations.
"""

from datetime import datetime, timezone
from typing import Optional, List, Callable, Any
from .models import (
    DelegationRequest, DelegationResponse, DelegationTask,
    DelegationResult, DelegationChain, DelegationStatus,
    DelegationPolicy, DelegationPriority
)
from ..negotiation.protocol import NegotiationProtocol
from ..negotiation.models import NegotiationTemplate
from ..discovery.service import DiscoveryService
from ..discovery.models import DiscoveryQuery
from ..capabilities.matcher import CapabilityMatcher


class DelegationManager:
    """
    Manages task delegation between agents.
    
    Features:
    - Find capable agents via discovery
    - Negotiate terms via negotiation protocol
    - Track delegation progress
    - Handle retries and timeouts
    - Support delegation chains (multi-hop)
    """
    
    def __init__(
        self,
        discovery_service: DiscoveryService,
        negotiation_protocol: NegotiationProtocol,
        policy: Optional[DelegationPolicy] = None,
        trust_store=None,  # TrustStore for checking trust scores
    ):
        self.discovery = discovery_service
        self.negotiation = negotiation_protocol
        self.policy = policy or DelegationPolicy()
        self.trust_store = trust_store
        self.tasks: dict[str, DelegationTask] = {}
        self.chains: dict[str, DelegationChain] = {}
        self.callbacks: dict[str, Callable] = {}
    
    def delegate(
        self,
        delegator_did: str,
        capability_name: str,
        input_data: dict[str, Any],
        delegatee_did: Optional[str] = None,
        priority: str = "normal",
        timeout_seconds: int = 300,
        requires_approval: bool = False,
        callback_url: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> DelegationTask:
        """
        Delegate a task to another agent.
        
        If delegatee_did is not specified, will discover the best agent.
        """
        # Find delegatee if not specified
        if delegatee_did is None:
            delegatee_did = self._find_best_agent(capability_name, delegator_did)
            if not delegatee_did:
                raise ValueError(f"No suitable agent found for capability: {capability_name}")
        
        # Check policy
        trust_score = 0.5
        verified = False
        if self.trust_store:
            score = self.trust_store.get_score(delegatee_did)
            if score:
                trust_score = score.overall_score
                verified = score.identity_verified
        
        allowed, reason = self.policy.can_delegate_to(delegatee_did, trust_score, verified)
        if not allowed:
            raise ValueError(f"Delegation not allowed: {reason}")
        
        allowed, reason = self.policy.can_delegate_capability(capability_name)
        if not allowed:
            raise ValueError(f"Capability delegation not allowed: {reason}")
        
        # Create request
        request = DelegationRequest(
            delegator_did=delegator_did,
            delegatee_did=delegatee_did,
            capability_name=capability_name,
            input_data=input_data,
            priority=DelegationPriority(priority),
            timeout_seconds=min(timeout_seconds, self.policy.max_timeout_seconds),
            requires_approval=requires_approval,
            callback_url=callback_url,
            metadata=metadata or {},
        )
        
        # Create task
        task = DelegationTask(
            id=request.id,
            request=request,
            status=DelegationStatus.PENDING,
        )
        
        self.tasks[task.id] = task
        
        # Start negotiation if needed
        if requires_approval:
            self._start_negotiation(task)
        else:
            # Auto-accept for now (in real implementation, would send to delegatee)
            task.status = DelegationStatus.ACCEPTED
            task.started_at = datetime.now(timezone.utc)
            self._execute_task(task)
        
        return task
    
    def _find_best_agent(self, capability_name: str, requester_did: str) -> Optional[str]:
        """Find the best agent for a capability."""
        query = DiscoveryQuery(
            query=capability_name,
            min_trust_score=self.policy.min_trust_score,
            require_verified=self.policy.require_verified_identity,
            limit=5,
            sort_by="trust",
            requester_did=requester_did,
        )
        
        results = self.discovery.discover(query)
        if not results:
            return None
        
        # Return the top result's agent DID
        return results[0].agent_did
    
    def _start_negotiation(self, task: DelegationTask):
        """Start negotiation for a delegation."""
        request = self.negotiation.create_request_from_template(
            template_name='delegation',
            initiator_did=task.request.delegator_did,
            responder_did=task.request.delegatee_did,
            capability_name=task.request.capability_name,
            expires_in_seconds=task.request.timeout_seconds,
        )
        
        session = self.negotiation.initiate(request)
        task.session_id = session.id
        task.status = DelegationStatus.IN_PROGRESS
    
    def _execute_task(self, task: DelegationTask):
        """Execute a delegation task (placeholder for actual implementation)."""
        # In a real implementation, this would:
        # 1. Send the request to the delegatee agent
        # 2. Wait for response
        # 3. Handle retries, timeouts, etc.
        # For now, we'll simulate completion
        task.status = DelegationStatus.IN_PROGRESS
        task.started_at = datetime.now(timezone.utc)
        
        # Simulate async execution
        # This would be replaced with actual agent communication
        pass
    
    def handle_response(self, task_id: str, response: DelegationResponse) -> DelegationTask:
        """Handle a response from a delegatee."""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        if response.accepted:
            task.status = DelegationStatus.ACCEPTED
            task.started_at = datetime.now(timezone.utc)
            task.session_id = response.session_id
            self._execute_task(task)
        else:
            task.status = DelegationStatus.REJECTED
            task.last_error = response.rejection_reason
        
        return task
    
    def complete_task(self, task_id: str, result: DelegationResult) -> DelegationTask:
        """Mark a task as completed with a result."""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        task.status = result.status
        task.completed_at = datetime.now(timezone.utc)
        task.progress = 1.0
        
        # Trigger callback if registered
        if task.request.callback_url:
            self._trigger_callback(task.request.callback_url, result)
        
        return task
    
    def fail_task(self, task_id: str, error: str) -> DelegationTask:
        """Mark a task as failed."""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        task.status = DelegationStatus.FAILED
        task.last_error = error
        task.completed_at = datetime.now(timezone.utc)
        
        # Retry if possible
        if task.can_retry():
            task.retry_count += 1
            task.status = DelegationStatus.PENDING
            task.last_error = None
            self._execute_task(task)
        
        return task
    
    def get_task(self, task_id: str) -> Optional[DelegationTask]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
    
    def get_tasks_by_delegator(self, delegator_did: str) -> List[DelegationTask]:
        """Get all tasks for a delegator."""
        return [
            task for task in self.tasks.values()
            if task.request.delegator_did == delegator_did
        ]
    
    def get_tasks_by_delegatee(self, delegatee_did: str) -> List[DelegationTask]:
        """Get all tasks for a delegatee."""
        return [
            task for task in self.tasks.values()
            if task.request.delegatee_did == delegatee_did
        ]
    
    def create_chain(
        self,
        root_delegator_did: str,
        capability_name: str,
        input_data: dict[str, Any],
        max_depth: int = 3,
    ) -> DelegationChain:
        """Create a delegation chain for multi-hop delegation."""
        chain = DelegationChain(
            root_delegator_did=root_delegator_did,
            max_depth=max_depth,
        )
        
        self.chains[chain.id] = chain
        
        # Start first delegation
        task = self.delegate(
            delegator_did=root_delegator_did,
            capability_name=capability_name,
            input_data=input_data,
        )
        
        chain.add_task(task)
        return chain
    
    def continue_chain(self, chain_id: str, capability_name: str, input_data: dict) -> Optional[DelegationTask]:
        """Continue a delegation chain to the next hop."""
        chain = self.chains.get(chain_id)
        if not chain:
            return None
        
        if chain.current_depth >= chain.max_depth:
            return None
        
        latest_task = chain.get_latest_task()
        if not latest_task or not latest_task.is_terminal():
            return None
        
        # Delegate to next agent
        task = self.delegate(
            delegator_did=latest_task.request.delegatee_did,
            capability_name=capability_name,
            input_data=input_data,
        )
        
        chain.add_task(task)
        return task
    
    def _trigger_callback(self, url: str, result: DelegationResult):
        """Trigger a callback URL (placeholder)."""
        # In real implementation, would make HTTP request to callback_url
        pass
    
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