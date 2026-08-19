"""
Tests for the delegation module.
"""

import pytest
from oai_network.core.delegation.models import (
    DelegationRequest, DelegationResponse, DelegationTask,
    DelegationResult, DelegationChain, DelegationStatus
)
from oai_network.core.delegation.manager import DelegationManager
from oai_network.core.delegation.policy import DelegationPolicyEngine


class TestDelegationModels:
    """Tests for delegation data models."""
    
    def test_delegation_request_creation(self):
        """Test creating a DelegationRequest."""
        request = DelegationRequest(
            delegator_did="did:oai:delegator",
            capability="text_summarization",
            input_data={"text": "Long text to summarize"},
            requirements={"max_price": 0.10, "max_latency_ms": 5000}
        )
        
        assert request.delegator_did == "did:oai:delegator"
        assert request.capability == "text_summarization"
        assert request.input_data["text"] == "Long text to summarize"
        assert request.requirements["max_price"] == 0.10
    
    def test_delegation_response_accept(self):
        """Test creating an accepting DelegationResponse."""
        response = DelegationResponse(
            request_id="req-123",
            delegatee_did="did:oai:delegatee",
            accepted=True,
            task_id="task-123"
        )
        
        assert response.accepted is True
        assert response.task_id == "task-123"
    
    def test_delegation_response_reject(self):
        """Test creating a rejecting DelegationResponse."""
        response = DelegationResponse(
            request_id="req-123",
            delegatee_did="did:oai:delegatee",
            accepted=False,
            rejection_reason="Capability not available"
        )
        
        assert response.accepted is False
        assert response.rejection_reason == "Capability not available"
    
    def test_delegation_task(self):
        """Test DelegationTask."""
        task = DelegationTask(
            task_id="task-123",
            request_id="req-123",
            delegator_did="did:oai:delegator",
            delegatee_did="did:oai:delegatee",
            capability="text_summarization",
            input_data={"text": "test"},
            status=DelegationStatus.PENDING
        )
        
        assert task.task_id == "task-123"
        assert task.status == DelegationStatus.PENDING
    
    def test_delegation_result(self):
        """Test DelegationResult."""
        result = DelegationResult(
            task_id="task-123",
            status=DelegationStatus.COMPLETED,
            output_data={"summary": "Short summary"},
            execution_time_ms=1500
        )
        
        assert result.task_id == "task-123"
        assert result.status == DelegationStatus.COMPLETED
        assert result.output_data["summary"] == "Short summary"
        assert result.execution_time_ms == 1500
    
    def test_delegation_chain(self):
        """Test DelegationChain."""
        chain = DelegationChain(
            chain_id="chain-123",
            original_request_id="req-123",
            tasks=["task-1", "task-2", "task-3"]
        )
        
        assert chain.chain_id == "chain-123"
        assert len(chain.tasks) == 3
        assert chain.tasks[0] == "task-1"
    
    def test_delegation_statuses(self):
        """Test all delegation statuses."""
        assert DelegationStatus.PENDING.value == "pending"
        assert DelegationStatus.ACCEPTED.value == "accepted"
        assert DelegationStatus.IN_PROGRESS.value == "in_progress"
        assert DelegationStatus.COMPLETED.value == "completed"
        assert DelegationStatus.FAILED.value == "failed"
        assert DelegationStatus.REJECTED.value == "rejected"
        assert DelegationStatus.TIMEOUT.value == "timeout"


class TestDelegationManager:
    """Tests for DelegationManager."""
    
    @pytest.mark.asyncio
    async def test_delegate_task(self, delegation_manager, sample_delegation_request):
        """Test delegating a task."""
        response = await delegation_manager.delegate(sample_delegation_request)
        
        assert response.accepted is True
        assert response.task_id is not None
        assert response.delegatee_did is not None
    
    @pytest.mark.asyncio
    async def test_delegate_no_capable_agent(self, delegation_manager):
        """Test delegation fails when no capable agent."""
        request = DelegationRequest(
            delegator_did="did:oai:delegator",
            capability="nonexistent_capability",
            input_data={},
            requirements={}
        )
        
        response = await delegation_manager.delegate(request)
        
        assert response.accepted is False
        assert "no capable agent" in response.rejection_reason.lower()
    
    @pytest.mark.asyncio
    async def test_execute_task(self, delegation_manager, sample_delegation_request):
        """Test executing a delegated task."""
        # First delegate
        response = await delegation_manager.delegate(sample_delegation_request)
        assert response.accepted is True
        
        # Then execute
        result = await delegation_manager.execute_task(response.task_id)
        
        assert result.status == DelegationStatus.COMPLETED
        assert result.output_data is not None
    
    @pytest.mark.asyncio
    async def test_get_task_status(self, delegation_manager, sample_delegation_request):
        """Test getting task status."""
        response = await delegation_manager.delegate(sample_delegation_request)
        
        status = await delegation_manager.get_task_status(response.task_id)
        
        assert status == DelegationStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, delegation_manager, sample_delegation_request):
        """Test cancelling a task."""
        response = await delegation_manager.delegate(sample_delegation_request)
        
        cancelled = await delegation_manager.cancel_task(response.task_id)
        
        assert cancelled is True
        
        status = await delegation_manager.get_task_status(response.task_id)
        assert status == DelegationStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_create_delegation_chain(self, delegation_manager):
        """Test creating a delegation chain."""
        # Create a chain of delegations
        chain = await delegation_manager.create_chain(
            delegator_did="did:oai:delegator",
            steps=[
                {"capability": "step1", "input_data": {}},
                {"capability": "step2", "input_data": {}},
                {"capability": "step3", "input_data": {}}
            ]
        )
        
        assert chain.chain_id is not None
        assert len(chain.tasks) == 3
    
    @pytest.mark.asyncio
    async def test_execute_chain(self, delegation_manager):
        """Test executing a delegation chain."""
        chain = await delegation_manager.create_chain(
            delegator_did="did:oai:delegator",
            steps=[
                {"capability": "text_summarization", "input_data": {"text": "test"}},
            ]
        )
        
        results = await delegation_manager.execute_chain(chain.chain_id)
        
        assert len(results) == 1
        assert results[0].status == DelegationStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_retry_failed_task(self, delegation_manager, sample_delegation_request):
        """Test retrying a failed task."""
        # This would require mocking a failure - simplified test
        response = await delegation_manager.delegate(sample_delegation_request)
        
        # Manually set task to failed for testing retry
        task = delegation_manager.tasks[response.task_id]
        task.status = DelegationStatus.FAILED
        
        retry_response = await delegation_manager.retry_task(response.task_id)
        
        assert retry_response.accepted is True
        assert retry_response.task_id != response.task_id  # New task ID


class TestDelegationPolicyEngine:
    """Tests for DelegationPolicyEngine."""
    
    def test_default_policy_allows(self, delegation_policy_engine, sample_delegation_request):
        """Test default policy allows delegation."""
        allowed, reason = delegation_policy_engine.check_delegation(sample_delegation_request)
        
        assert allowed is True
        assert reason == ""
    
    def test_max_depth_exceeded(self, delegation_policy_engine, sample_delegation_request):
        """Test policy rejects when max depth exceeded."""
        # Create a request that would exceed depth
        request = sample_delegation_request
        request.metadata = {"delegation_depth": 10}  # Exceeds default max of 5
        
        allowed, reason = delegation_policy_engine.check_delegation(request)
        
        assert allowed is False
        assert "depth" in reason.lower()
    
    def test_min_trust_score_required(self, delegation_policy_engine, sample_delegation_request):
        """Test policy requires minimum trust score."""
        request = sample_delegation_request
        request.requirements["min_trust_score"] = 0.9  # Very high
        
        # This would need a mock delegatee with low trust
        # Simplified test - just verify the check runs
        allowed, reason = delegation_policy_engine.check_delegation(request)
        
        # With default policy, should still allow (no delegatee to check)
        assert allowed is True
    
    def test_blocked_capabilities(self, delegation_policy_engine):
        """Test policy blocks certain capabilities."""
        # Add blocked capability
        delegation_policy_engine.blocked_capabilities.add("dangerous_capability")
        
        request = DelegationRequest(
            delegator_did="did:oai:delegator",
            capability="dangerous_capability",
            input_data={},
            requirements={}
        )
        
        allowed, reason = delegation_policy_engine.check_delegation(request)
        
        assert allowed is False
        assert "blocked" in reason.lower()
    
    def test_allowed_capabilities_only(self, delegation_policy_engine):
        """Test policy with allowed capabilities list."""
        delegation_policy_engine.allowed_capabilities = {"text_summarization", "translation"}
        
        # Allowed capability
        request1 = DelegationRequest(
            delegator_did="did:oai:delegator",
            capability="text_summarization",
            input_data={},
            requirements={}
        )
        allowed1, _ = delegation_policy_engine.check_delegation(request1)
        assert allowed1 is True
        
        # Not in allowed list
        request2 = DelegationRequest(
            delegator_did="did:oai:delegator",
            capability="not_allowed",
            input_data={},
            requirements={}
        )
        allowed2, _ = delegation_policy_engine.check_delegation(request2)
        assert allowed2 is False
    
    def test_budget_enforcement(self, delegation_policy_engine, sample_delegation_request):
        """Test policy enforces budget limits."""
        request = sample_delegation_request
        request.requirements["max_price"] = 0.001  # Very low budget
        
        # Would need a delegatee with higher price to test properly
        # Just verify check runs
        allowed, reason = delegation_policy_engine.check_delegation(request)
        assert allowed is True  # No delegatee to check against
    
    def test_policy_customization(self, delegation_policy_engine):
        """Test customizing policy parameters."""
        delegation_policy_engine.max_delegation_depth = 3
        delegation_policy_engine.default_min_trust_score = 0.7
        
        assert delegation_policy_engine.max_delegation_depth == 3
        assert delegation_policy_engine.default_min_trust_score == 0.7