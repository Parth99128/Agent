"""
Policy Loader

Loads policies from YAML/JSON files and directories.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Optional, List
from .models import Policy, PolicyRule, PolicyEffect, PolicyCondition, Budget, BudgetPeriod, PolicyOperator
from .engine import PolicyEngine


class PolicyLoader:
    """
    Loads policies from files and directories.

    Supports:
    - Loading from dict
    - Single YAML/JSON policy files
    - Directories of policy files (returns list)
    - Merging multiple policies
    """

    def load_from_dict(self, data: dict) -> Policy:
        """Load a policy from a dictionary."""
        return Policy(**data)

    def load_from_file(self, file_path: str) -> Policy:
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

        return self.load_from_dict(data)

    def load_directory(self, dir_path: str) -> List[Policy]:
        """Load all policies from a directory. Returns a list of policies."""
        path = Path(dir_path)

        if not path.exists() or not path.is_dir():
            raise ValueError(f"Directory not found: {dir_path}")

        policies = []

        for file_path in sorted(path.glob('*.yaml')) + sorted(path.glob('*.yml')) + sorted(path.glob('*.json')):
            try:
                policy = self.load_from_file(str(file_path))
                policies.append(policy)
            except Exception as e:
                print(f"Warning: Failed to load {file_path}: {e}")

        return policies

    def merge_policies(self, policies: List[Policy], merged_id: str) -> Policy:
        """Merge multiple policies into one."""
        all_rules = []
        all_budgets = []

        for policy in policies:
            all_rules.extend(policy.rules)
            all_budgets.extend(policy.budgets)

        return Policy(
            policy_id=merged_id,
            name=f"Merged Policy ({merged_id})",
            description=f"Merged from {len(policies)} policies",
            rules=all_rules,
            budgets=all_budgets,
        )

    def create_default_policy(self) -> Policy:
        """Create a sensible default policy."""
        engine = PolicyEngine()
        return engine.create_default_policy()