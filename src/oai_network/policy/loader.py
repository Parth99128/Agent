"""
Policy Loader

Loads policies from YAML/JSON files and directories.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Optional, List
from .models import Policy, PolicyRule, PolicyEffect, PolicyCondition, Budget, BudgetPeriod, PolicyConditionType, PolicyOperator
from .engine import PolicyEngine


class PolicyLoader:
    """
    Loads policies from files and directories.
    
    Supports:
    - Single YAML/JSON policy files
    - Directories of policy files (merged)
    - Policy inheritance/extension
    """
    
    @staticmethod
    def load_from_file(file_path: str) -> Policy:
        """Load a policy from a single file."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Policy file not found: {file_path}")
        
        content = path.read_text()
        
        if path.suffix in ('.yaml', '.yml'):
            data = yaml.safe_load(content)
        elif path.suffix == '.json':
            data = json.loads(content)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
        
        return Policy(**data)
    
    @staticmethod
    def load_from_directory(dir_path: str, merge: bool = True) -> Policy:
        """
        Load policies from a directory.
        
        If merge=True, combines all policies into one (higher priority wins).
        If merge=False, returns the first policy found.
        """
        path = Path(dir_path)
        
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Directory not found: {dir_path}")
        
        policies = []
        
        for file_path in sorted(path.glob('*.yaml')) + sorted(path.glob('*.yml')) + sorted(path.glob('*.json')):
            try:
                policy = PolicyLoader.load_from_file(str(file_path))
                policies.append(policy)
            except Exception as e:
                print(f"Warning: Failed to load {file_path}: {e}")
        
        if not policies:
            raise ValueError(f"No valid policies found in {dir_path}")
        
        if not merge:
            return policies[0]
        
        # Merge policies - highest priority rules win
        merged = Policy(
            name=f"Merged from {dir_path}",
            description=f"Merged from {len(policies)} policy files",
            default_effect=PolicyEffect.DENY,
        )
        
        # Collect all rules and budgets
        all_rules = []
        all_budgets = []
        
        for policy in policies:
            all_rules.extend(policy.rules)
            all_budgets.extend(policy.budgets)
        
        # Sort rules by priority (highest first)
        all_rules.sort(key=lambda r: r.priority, reverse=True)
        
        # Deduplicate by ID (keep first/highest priority)
        seen_rule_ids = set()
        for rule in all_rules:
            if rule.id not in seen_rule_ids:
                merged.add_rule(rule)
                seen_rule_ids.add(rule.id)
        
        # Deduplicate budgets by ID
        seen_budget_ids = set()
        for budget in all_budgets:
            if budget.id not in seen_budget_ids:
                merged.add_budget(budget)
                seen_budget_ids.add(budget.id)
        
        return merged
    
    @staticmethod
    def create_default_policy() -> Policy:
        """Create a sensible default policy."""
        policy = Policy(
            name="Default OAI-Network Policy",
            description="Default policy allowing verified agents with reasonable limits",
            default_effect=PolicyEffect.DENY,
        )
        
        # Allow verified agents with good trust score
        policy.add_rule(PolicyRule(
            name="Allow Verified High-Trust Agents",
            description="Allow verified agents with trust score >= 0.7",
            effect=PolicyEffect.ALLOW,
            priority=100,
            conditions=[
                PolicyCondition(
                    type=PolicyConditionType.IDENTITY_VERIFIED,
                    operator=PolicyOperator.EQUALS,
                    value=True,
                ),
                PolicyCondition(
                    type=PolicyConditionType.TRUST_SCORE,
                    operator=PolicyOperator.GREATER_THAN_OR_EQUAL,
                    value=0.7,
                ),
            ],
        ))
        
        # Allow specific capabilities for all verified agents
        policy.add_rule(PolicyRule(
            name="Allow Basic Capabilities",
            description="Allow basic capabilities for verified agents",
            effect=PolicyEffect.ALLOW,
            priority=50,
            conditions=[
                PolicyCondition(
                    type=PolicyConditionType.IDENTITY_VERIFIED,
                    operator=PolicyOperator.EQUALS,
                    value=True,
                ),
                PolicyCondition(
                    type=PolicyConditionType.CAPABILITY_TYPE,
                    operator=PolicyOperator.IN,
                    value=["search", "summarization", "translation", "code_analysis"],
                ),
            ],
        ))
        
        # Deny unverified agents
        policy.add_rule(PolicyRule(
            name="Deny Unverified Agents",
            description="Deny all unverified agents",
            effect=PolicyEffect.DENY,
            priority=10,
            conditions=[
                PolicyCondition(
                    type=PolicyConditionType.IDENTITY_VERIFIED,
                    operator=PolicyOperator.EQUALS,
                    value=False,
                ),
            ],
        ))
        
        # Deny delegation depth > 3
        policy.add_rule(PolicyRule(
            name="Limit Delegation Depth",
            description="Deny delegations deeper than 3 levels",
            effect=PolicyEffect.DENY,
            priority=200,
            conditions=[
                PolicyCondition(
                    type=PolicyConditionType.DELEGATION_DEPTH,
                    operator=PolicyOperator.GREATER_THAN,
                    value=3,
                ),
            ],
        ))
        
        # Budget: 1000 calls per day per agent
        policy.add_budget(Budget(
            name="Daily Call Limit",
            period=BudgetPeriod.DAILY,
            max_calls=1000,
        ))
        
        # Budget: $10 per day per agent
        policy.add_budget(Budget(
            name="Daily Cost Limit",
            period=BudgetPeriod.DAILY,
            max_cost=10.0,
        ))
        
        return policy
    
    @staticmethod
    def create_strict_policy() -> Policy:
        """Create a strict policy for production use."""
        policy = Policy(
            name="Strict OAI-Network Policy",
            description="Strict policy for production environments",
            default_effect=PolicyEffect.DENY,
        )
        
        # Only allow explicitly whitelisted agents
        policy.add_rule(PolicyRule(
            name="Allow Whitelisted Agents",
            description="Only allow explicitly whitelisted agents",
            effect=PolicyEffect.ALLOW,
            priority=100,
            conditions=[
                PolicyCondition(
                    type=PolicyConditionType.AGENT_DID,
                    operator=PolicyOperator.IN,
                    value=[],  # Populate with allowed DIDs
                ),
                PolicyCondition(
                    type=PolicyConditionType.IDENTITY_VERIFIED,
                    operator=PolicyOperator.EQUALS,
                    value=True,
                ),
            ],
        ))
        
        # Strict delegation limits
        policy.add_rule(PolicyRule(
            name="Strict Delegation Limit",
            description="Maximum 2 delegation levels",
            effect=PolicyEffect.DENY,
            priority=200,
            conditions=[
                PolicyCondition(
                    type=PolicyConditionType.DELEGATION_DEPTH,
                    operator=PolicyOperator.GREATER_THAN,
                    value=2,
                ),
            ],
        ))
        
        # Tight budgets
        policy.add_budget(Budget(
            name="Hourly Call Limit",
            period=BudgetPeriod.HOURLY,
            max_calls=100,
        ))
        
        policy.add_budget(Budget(
            name="Daily Cost Limit",
            period=BudgetPeriod.DAILY,
            max_cost=5.0,
        ))
        
        return policy
    
    @staticmethod
    def create_open_policy() -> Policy:
        """Create an open policy for development/testing."""
        policy = Policy(
            name="Open OAI-Network Policy",
            description="Open policy for development - allows most interactions",
            default_effect=PolicyEffect.ALLOW,
        )
        
        # Deny only explicitly blocked agents
        policy.add_rule(PolicyRule(
            name="Deny Blocked Agents",
            description="Deny explicitly blocked agents",
            effect=PolicyEffect.DENY,
            priority=100,
            conditions=[
                PolicyCondition(
                    type=PolicyConditionType.AGENT_DID,
                    operator=PolicyOperator.IN,
                    value=[],  # Populate with blocked DIDs
                ),
            ],
        ))
        
        # Reasonable delegation limit
        policy.add_rule(PolicyRule(
            name="Moderate Delegation Limit",
            description="Maximum 5 delegation levels",
            effect=PolicyEffect.DENY,
            priority=200,
            conditions=[
                PolicyCondition(
                    type=PolicyConditionType.DELEGATION_DEPTH,
                    operator=PolicyOperator.GREATER_THAN,
                    value=5,
                ),
            ],
        ))
        
        # Generous budgets
        policy.add_budget(Budget(
            name="Daily Call Limit",
            period=BudgetPeriod.DAILY,
            max_calls=10000,
        ))
        
        policy.add_budget(Budget(
            name="Daily Cost Limit",
            period=BudgetPeriod.DAILY,
            max_cost=100.0,
        ))
        
        return policy
    
    @staticmethod
    def save_policy(policy: Policy, file_path: str):
        """Save a policy to a file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if path.suffix in ('.yaml', '.yml'):
            content = policy.to_yaml()
        elif path.suffix == '.json':
            content = policy.to_json()
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
        
        path.write_text(content)
    
    @staticmethod
    def create_engine_from_file(file_path: str) -> PolicyEngine:
        """Create a PolicyEngine from a policy file."""
        policy = PolicyLoader.load_from_file(file_path)
        return PolicyEngine(policy)
    
    @staticmethod
    def create_engine_from_directory(dir_path: str) -> PolicyEngine:
        """Create a PolicyEngine from a policy directory."""
        policy = PolicyLoader.load_from_directory(dir_path)
        return PolicyEngine(policy)