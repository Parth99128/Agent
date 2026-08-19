"""
Tests for the policy module.
"""

import pytest
from oai_network.policy.models import (
    Policy, PolicyRule, PolicyEffect, PolicyCondition, PolicyOperator,
    Budget, BudgetPeriod
)
from oai_network.policy.engine import PolicyEngine
from oai_network.policy.loader import PolicyLoader


class TestPolicyModels:
    """Tests for policy data models."""
    
    def test_policy_creation(self):
        """Test creating a Policy."""
        policy = Policy(
            policy_id="test-policy",
            name="Test Policy",
            description="A test policy",
            version="1.0.0",
            rules=[]
        )
        
        assert policy.policy_id == "test-policy"
        assert policy.name == "Test Policy"
        assert policy.version == "1.0.0"
    
    def test_policy_rule_creation(self):
        """Test creating a PolicyRule."""
        rule = PolicyRule(
            rule_id="rule-1",
            name="Allow delegation",
            effect=PolicyEffect.ALLOW,
            conditions=[
                PolicyCondition(
                    field="capability",
                    operator=PolicyOperator.EQUALS,
                    value="text_summarization"
                )
            ]
        )
        
        assert rule.rule_id == "rule-1"
        assert rule.effect == PolicyEffect.ALLOW
        assert len(rule.conditions) == 1
        assert rule.conditions[0].field == "capability"
    
    def test_policy_effects(self):
        """Test PolicyEffect enum."""
        assert PolicyEffect.ALLOW.value == "allow"
        assert PolicyEffect.DENY.value == "deny"
    
    def test_policy_operators(self):
        """Test PolicyOperator enum."""
        assert PolicyOperator.EQUALS.value == "equals"
        assert PolicyOperator.NOT_EQUALS.value == "not_equals"
        assert PolicyOperator.GREATER_THAN.value == "greater_than"
        assert PolicyOperator.LESS_THAN.value == "less_than"
        assert PolicyOperator.IN.value == "in"
        assert PolicyOperator.NOT_IN.value == "not_in"
        assert PolicyOperator.CONTAINS.value == "contains"
    
    def test_budget_creation(self):
        """Test creating a Budget."""
        budget = Budget(
            budget_id="budget-1",
            name="Monthly Budget",
            period=BudgetPeriod.MONTHLY,
            limit=100.0,
            currency="USD"
        )
        
        assert budget.budget_id == "budget-1"
        assert budget.period == BudgetPeriod.MONTHLY
        assert budget.limit == 100.0
        assert budget.currency == "USD"
    
    def test_budget_periods(self):
        """Test BudgetPeriod enum."""
        assert BudgetPeriod.HOURLY.value == "hourly"
        assert BudgetPeriod.DAILY.value == "daily"
        assert BudgetPeriod.WEEKLY.value == "weekly"
        assert BudgetPeriod.MONTHLY.value == "monthly"
        assert BudgetPeriod.YEARLY.value == "yearly"
    
    def test_policy_with_budget(self):
        """Test policy with budget."""
        budget = Budget(
            budget_id="budget-1",
            name="Test Budget",
            period=BudgetPeriod.DAILY,
            limit=10.0
        )
        
        policy = Policy(
            policy_id="policy-with-budget",
            name="Policy with Budget",
            version="1.0.0",
            rules=[],
            budgets=[budget]
        )
        
        assert len(policy.budgets) == 1
        assert policy.budgets[0].limit == 10.0


class TestPolicyEngine:
    """Tests for PolicyEngine."""
    
    def test_evaluate_allow_rule(self, policy_engine):
        """Test evaluating an allow rule."""
        policy = Policy(
            policy_id="test-policy",
            name="Test",
            version="1.0.0",
            rules=[
                PolicyRule(
                    rule_id="rule-1",
                    name="Allow summarization",
                    effect=PolicyEffect.ALLOW,
                    conditions=[
                        PolicyCondition(
                            field="capability",
                            operator=PolicyOperator.EQUALS,
                            value="text_summarization"
                        )
                    ]
                )
            ]
        )
        
        context = {"capability": "text_summarization"}
        decision = policy_engine.evaluate(policy, context)
        
        assert decision.allowed is True
        assert decision.matched_rule_id == "rule-1"
    
    def test_evaluate_deny_rule(self, policy_engine):
        """Test evaluating a deny rule."""
        policy = Policy(
            policy_id="test-policy",
            name="Test",
            version="1.0.0",
            rules=[
                PolicyRule(
                    rule_id="rule-1",
                    name="Deny dangerous",
                    effect=PolicyEffect.DENY,
                    conditions=[
                        PolicyCondition(
                            field="capability",
                            operator=PolicyOperator.EQUALS,
                            value="dangerous_capability"
                        )
                    ]
                )
            ]
        )
        
        context = {"capability": "dangerous_capability"}
        decision = policy_engine.evaluate(policy, context)
        
        assert decision.allowed is False
        assert decision.matched_rule_id == "rule-1"
    
    def test_evaluate_multiple_rules_first_match(self, policy_engine):
        """Test first matching rule wins."""
        policy = Policy(
            policy_id="test-policy",
            name="Test",
            version="1.0.0",
            rules=[
                PolicyRule(
                    rule_id="rule-1",
                    name="Deny all",
                    effect=PolicyEffect.DENY,
                    conditions=[]
                ),
                PolicyRule(
                    rule_id="rule-2",
                    name="Allow summarization",
                    effect=PolicyEffect.ALLOW,
                    conditions=[
                        PolicyCondition(
                            field="capability",
                            operator=PolicyOperator.EQUALS,
                            value="text_summarization"
                        )
                    ]
                )
            ]
        )
        
        context = {"capability": "text_summarization"}
        decision = policy_engine.evaluate(policy, context)
        
        # First rule (deny all) matches because it has no conditions
        assert decision.allowed is False
        assert decision.matched_rule_id == "rule-1"
    
    def test_evaluate_no_match_default_deny(self, policy_engine):
        """Test default deny when no rules match."""
        policy = Policy(
            policy_id="test-policy",
            name="Test",
            version="1.0.0",
            rules=[
                PolicyRule(
                    rule_id="rule-1",
                    name="Allow specific",
                    effect=PolicyEffect.ALLOW,
                    conditions=[
                        PolicyCondition(
                            field="capability",
                            operator=PolicyOperator.EQUALS,
                            value="text_summarization"
                        )
                    ]
                )
            ]
        )
        
        context = {"capability": "other_capability"}
        decision = policy_engine.evaluate(policy, context)
        
        assert decision.allowed is False
        assert decision.matched_rule_id is None
    
    def test_evaluate_complex_conditions(self, policy_engine):
        """Test evaluating complex conditions."""
        policy = Policy(
            policy_id="test-policy",
            name="Test",
            version="1.0.0",
            rules=[
                PolicyRule(
                    rule_id="rule-1",
                    name="Complex rule",
                    effect=PolicyEffect.ALLOW,
                    conditions=[
                        PolicyCondition(
                            field="capability",
                            operator=PolicyOperator.IN,
                            value=["text_summarization", "translation"]
                        ),
                        PolicyCondition(
                            field="trust_score",
                            operator=PolicyOperator.GREATER_THAN,
                            value=0.7
                        )
                    ]
                )
            ]
        )
        
        # Both conditions match
        context = {"capability": "text_summarization", "trust_score": 0.8}
        decision = policy_engine.evaluate(policy, context)
        assert decision.allowed is True
        
        # First condition fails
        context = {"capability": "other", "trust_score": 0.8}
        decision = policy_engine.evaluate(policy, context)
        assert decision.allowed is False
        
        # Second condition fails
        context = {"capability": "text_summarization", "trust_score": 0.5}
        decision = policy_engine.evaluate(policy, context)
        assert decision.allowed is False
    
    def test_evaluate_budget_check(self, policy_engine):
        """Test budget checking in policy evaluation."""
        budget = Budget(
            budget_id="budget-1",
            name="Daily Budget",
            period=BudgetPeriod.DAILY,
            limit=10.0,
            currency="USD"
        )
        
        policy = Policy(
            policy_id="test-policy",
            name="Test",
            version="1.0.0",
            rules=[
                PolicyRule(
                    rule_id="rule-1",
                    name="Allow with budget",
                    effect=PolicyEffect.ALLOW,
                    conditions=[]
                )
            ],
            budgets=[budget]
        )
        
        # Within budget
        context = {"capability": "text_summarization", "cost": 5.0}
        decision = policy_engine.evaluate(policy, context)
        assert decision.allowed is True
        
        # Exceeds budget
        context = {"capability": "text_summarization", "cost": 15.0}
        decision = policy_engine.evaluate(policy, context)
        assert decision.allowed is False
        assert "budget" in decision.reason.lower()
    
    def test_evaluate_with_explanation(self, policy_engine):
        """Test evaluation returns explanation."""
        policy = Policy(
            policy_id="test-policy",
            name="Test",
            version="1.0.0",
            rules=[
                PolicyRule(
                    rule_id="rule-1",
                    name="Allow summarization",
                    effect=PolicyEffect.ALLOW,
                    conditions=[
                        PolicyCondition(
                            field="capability",
                            operator=PolicyOperator.EQUALS,
                            value="text_summarization"
                        )
                    ]
                )
            ]
        )
        
        context = {"capability": "text_summarization"}
        decision = policy_engine.evaluate(policy, context)
        
        assert decision.explanation is not None
        assert "rule-1" in decision.explanation
        assert "ALLOW" in decision.explanation
    
    def test_default_policy(self, policy_engine):
        """Test default policy creation."""
        policy = policy_engine.create_default_policy()
        
        assert policy.policy_id == "default"
        assert len(policy.rules) > 0
        # Should have some basic rules
        rule_names = [r.name for r in policy.rules]
        assert any("delegation" in name.lower() for name in rule_names)


class TestPolicyLoader:
    """Tests for PolicyLoader."""
    
    def test_load_from_dict(self, policy_loader):
        """Test loading policy from dictionary."""
        policy_dict = {
            "policy_id": "from-dict",
            "name": "From Dict",
            "version": "1.0.0",
            "rules": [
                {
                    "rule_id": "rule-1",
                    "name": "Test Rule",
                    "effect": "allow",
                    "conditions": [
                        {
                            "field": "capability",
                            "operator": "equals",
                            "value": "test"
                        }
                    ]
                }
            ]
        }
        
        policy = policy_loader.load_from_dict(policy_dict)
        
        assert policy.policy_id == "from-dict"
        assert policy.name == "From Dict"
        assert len(policy.rules) == 1
        assert policy.rules[0].effect == PolicyEffect.ALLOW
    
    def test_load_from_yaml(self, policy_loader, tmp_path):
        """Test loading policy from YAML file."""
        yaml_content = """
policy_id: from-yaml
name: From YAML
version: "1.0.0"
rules:
  - rule_id: rule-1
    name: Test Rule
    effect: allow
    conditions:
      - field: capability
        operator: equals
        value: test
"""
        yaml_file = tmp_path / "policy.yaml"
        yaml_file.write_text(yaml_content)
        
        policy = policy_loader.load_from_file(str(yaml_file))
        
        assert policy.policy_id == "from-yaml"
        assert policy.name == "From YAML"
    
    def test_load_from_json(self, policy_loader, tmp_path):
        """Test loading policy from JSON file."""
        json_content = """
{
    "policy_id": "from-json",
    "name": "From JSON",
    "version": "1.0.0",
    "rules": [
        {
            "rule_id": "rule-1",
            "name": "Test Rule",
            "effect": "allow",
            "conditions": [
                {
                    "field": "capability",
                    "operator": "equals",
                    "value": "test"
                }
            ]
        }
    ]
}
"""
        json_file = tmp_path / "policy.json"
        json_file.write_text(json_content)
        
        policy = policy_loader.load_from_file(str(json_file))
        
        assert policy.policy_id == "from-json"
        assert policy.name == "From JSON"
    
    def test_load_directory(self, policy_loader, tmp_path):
        """Test loading all policies from directory."""
        # Create multiple policy files
        for i in range(3):
            yaml_content = f"""
policy_id: policy-{i}
name: Policy {i}
version: "1.0.0"
rules: []
"""
            (tmp_path / f"policy_{i}.yaml").write_text(yaml_content)
        
        policies = policy_loader.load_directory(str(tmp_path))
        
        assert len(policies) == 3
        assert all(p.policy_id.startswith("policy-") for p in policies)
    
    def test_merge_policies(self, policy_loader):
        """Test merging multiple policies."""
        policy1 = Policy(
            policy_id="policy-1",
            name="Policy 1",
            version="1.0.0",
            rules=[
                PolicyRule(
                    rule_id="rule-1",
                    name="Rule 1",
                    effect=PolicyEffect.ALLOW,
                    conditions=[]
                )
            ]
        )
        
        policy2 = Policy(
            policy_id="policy-2",
            name="Policy 2",
            version="1.0.0",
            rules=[
                PolicyRule(
                    rule_id="rule-2",
                    name="Rule 2",
                    effect=PolicyEffect.DENY,
                    conditions=[]
                )
            ]
        )
        
        merged = policy_loader.merge_policies([policy1, policy2], "merged-policy")
        
        assert merged.policy_id == "merged-policy"
        assert len(merged.rules) == 2
    
    def test_create_default_policy(self, policy_loader):
        """Test creating default policy."""
        policy = policy_loader.create_default_policy()
        
        assert policy.policy_id == "default"
        assert policy.name == "Default Policy"
        assert len(policy.rules) > 0