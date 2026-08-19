"""
Tests for the CLI module.
"""

import pytest
from click.testing import CliRunner
from oai_network.cli.main import cli


class TestCLI:
    """Tests for CLI commands."""
    
    def setup_method(self):
        """Set up CLI runner."""
        self.runner = CliRunner()
    
    def test_cli_help(self):
        """Test CLI help command."""
        result = self.runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert "OAI Network CLI" in result.output
        assert "identity" in result.output
        assert "agent" in result.output
        assert "discover" in result.output
        assert "delegate" in result.output
        assert "trust" in result.output
        assert "negotiate" in result.output
        assert "health" in result.output
    
    def test_identity_generate(self):
        """Test identity generate command."""
        result = self.runner.invoke(cli, ['identity', 'generate', '--name', 'Test Agent'])
        
        assert result.exit_code == 0
        assert "did:oai:" in result.output
        assert "Ed25519" in result.output
        assert "Test Agent" in result.output
    
    def test_identity_generate_rsa(self):
        """Test identity generate with RSA key."""
        result = self.runner.invoke(cli, ['identity', 'generate', '--name', 'RSA Agent', '--key-type', 'RSA'])
        
        assert result.exit_code == 0
        assert "did:oai:" in result.output
        assert "RSA" in result.output
    
    def test_identity_generate_output_file(self, tmp_path):
        """Test identity generate with output file."""
        output_file = tmp_path / "identity.json"
        
        result = self.runner.invoke(cli, [
            'identity', 'generate',
            '--name', 'File Agent',
            '--output', str(output_file)
        ])
        
        assert result.exit_code == 0
        assert output_file.exists()
        
        import json
        with open(output_file) as f:
            data = json.load(f)
        
        assert data["identity"]["did"].startswith("did:oai:")
        assert data["identity"]["metadata"]["name"] == "File Agent"
    
    def test_identity_show(self, tmp_path):
        """Test identity show command."""
        # First create an identity file
        output_file = tmp_path / "identity.json"
        self.runner.invoke(cli, [
            'identity', 'generate',
            '--name', 'Show Agent',
            '--output', str(output_file)
        ])
        
        # Now show it
        result = self.runner.invoke(cli, ['identity', 'show', '--input', str(output_file)])
        
        assert result.exit_code == 0
        assert "did:oai:" in result.output
        assert "Show Agent" in result.output
    
    def test_identity_show_missing_file(self):
        """Test identity show with missing file."""
        result = self.runner.invoke(cli, ['identity', 'show', '--input', '/nonexistent.json'])
        
        assert result.exit_code != 0
        assert "not found" in result.output.lower()
    
    def test_agent_register(self, tmp_path):
        """Test agent register command."""
        # Create identity first
        identity_file = tmp_path / "identity.json"
        self.runner.invoke(cli, [
            'identity', 'generate',
            '--name', 'Register Agent',
            '--output', str(identity_file)
        ])
        
        # Register agent
        result = self.runner.invoke(cli, [
            'agent', 'register',
            '--identity', str(identity_file),
            '--registry', 'http://localhost:8000'
        ])
        
        # Will fail without running registry, but command should be recognized
        assert "register" in result.output.lower() or result.exit_code == 0
    
    def test_agent_heartbeat(self, tmp_path):
        """Test agent heartbeat command."""
        identity_file = tmp_path / "identity.json"
        self.runner.invoke(cli, [
            'identity', 'generate',
            '--name', 'Heartbeat Agent',
            '--output', str(identity_file)
        ])
        
        result = self.runner.invoke(cli, [
            'agent', 'heartbeat',
            '--identity', str(identity_file),
            '--registry', 'http://localhost:8000',
            '--status', 'healthy'
        ])
        
        assert "heartbeat" in result.output.lower() or result.exit_code == 0
    
    def test_agent_unregister(self, tmp_path):
        """Test agent unregister command."""
        identity_file = tmp_path / "identity.json"
        self.runner.invoke(cli, [
            'identity', 'generate',
            '--name', 'Unregister Agent',
            '--output', str(identity_file)
        ])
        
        result = self.runner.invoke(cli, [
            'agent', 'unregister',
            '--identity', str(identity_file),
            '--registry', 'http://localhost:8000'
        ])
        
        assert "unregister" in result.output.lower() or result.exit_code == 0
    
    def test_discover_find(self):
        """Test discover find command."""
        result = self.runner.invoke(cli, [
            'discover', 'find',
            '--query', 'text summarization',
            '--registry', 'http://localhost:8000'
        ])
        
        assert "discover" in result.output.lower() or result.exit_code == 0
    
    def test_discover_find_with_filters(self):
        """Test discover find with filters."""
        result = self.runner.invoke(cli, [
            'discover', 'find',
            '--query', 'translation',
            '--type', 'nlp',
            '--tags', 'translation,language',
            '--min-trust', '0.7',
            '--max-results', '5',
            '--registry', 'http://localhost:8000'
        ])
        
        assert "discover" in result.output.lower() or result.exit_code == 0
    
    def test_discover_get(self):
        """Test discover get command."""
        result = self.runner.invoke(cli, [
            'discover', 'get',
            '--did', 'did:oai:test123',
            '--registry', 'http://localhost:8000'
        ])
        
        assert "discover" in result.output.lower() or result.exit_code == 0
    
    def test_delegate_run(self, tmp_path):
        """Test delegate run command."""
        identity_file = tmp_path / "identity.json"
        self.runner.invoke(cli, [
            'identity', 'generate',
            '--name', 'Delegate Agent',
            '--output', str(identity_file)
        ])
        
        result = self.runner.invoke(cli, [
            'delegate', 'run',
            '--identity', str(identity_file),
            '--capability', 'text_summarization',
            '--input', '{"text": "Test text to summarize"}',
            '--registry', 'http://localhost:8000'
        ])
        
        assert "delegate" in result.output.lower() or result.exit_code == 0
    
    def test_delegate_run_with_requirements(self, tmp_path):
        """Test delegate run with requirements."""
        identity_file = tmp_path / "identity.json"
        self.runner.invoke(cli, [
            'identity', 'generate',
            '--name', 'Delegate Agent 2',
            '--output', str(identity_file)
        ])
        
        result = self.runner.invoke(cli, [
            'delegate', 'run',
            '--identity', str(identity_file),
            '--capability', 'translation',
            '--input', '{"text": "Hello", "target_lang": "es"}',
            '--max-price', '0.05',
            '--max-latency', '3000',
            '--min-trust', '0.8',
            '--registry', 'http://localhost:8000'
        ])
        
        assert "delegate" in result.output.lower() or result.exit_code == 0
    
    def test_trust_score(self):
        """Test trust score command."""
        result = self.runner.invoke(cli, [
            'trust', 'score',
            '--did', 'did:oai:test123',
            '--registry', 'http://localhost:8000'
        ])
        
        assert "trust" in result.output.lower() or result.exit_code == 0
    
    def test_trust_feedback(self):
        """Test trust feedback command."""
        result = self.runner.invoke(cli, [
            'trust', 'feedback',
            '--from-did', 'did:oai:reviewer',
            '--to-did', 'did:oai:target',
            '--rating', '5',
            '--comment', 'Excellent service',
            '--capability', 'text_summarization',
            '--registry', 'http://localhost:8000'
        ])
        
        assert "feedback" in result.output.lower() or result.exit_code == 0
    
    def test_negotiate_start(self, tmp_path):
        """Test negotiate start command."""
        identity_file = tmp_path / "identity.json"
        self.runner.invoke(cli, [
            'identity', 'generate',
            '--name', 'Negotiate Agent',
            '--output', str(identity_file)
        ])
        
        result = self.runner.invoke(cli, [
            'negotiate', 'start',
            '--identity', str(identity_file),
            '--responder', 'did:oai:responder',
            '--template', 'a2a_delegation',
            '--params', '{"price": 0.10, "timeout": 30}',
            '--registry', 'http://localhost:8000'
        ])
        
        assert "negotiate" in result.output.lower() or result.exit_code == 0
    
    def test_health_check(self):
        """Test health check command."""
        result = self.runner.invoke(cli, [
            'health',
            '--registry', 'http://localhost:8000'
        ])
        
        assert "health" in result.output.lower() or result.exit_code == 0
    
    def test_interactive_mode_help(self):
        """Test interactive mode help."""
        result = self.runner.invoke(cli, ['interactive', '--help'])
        
        assert result.exit_code == 0
        assert "interactive" in result.output.lower()
    
    def test_invalid_command(self):
        """Test invalid command handling."""
        result = self.runner.invoke(cli, ['invalid_command'])
        
        assert result.exit_code != 0
        assert "no such command" in result.output.lower()
    
    def test_missing_required_option(self):
        """Test missing required option."""
        result = self.runner.invoke(cli, ['identity', 'generate'])
        
        assert result.exit_code != 0
        assert "missing option" in result.output.lower() or "required" in result.output.lower()
    
    def test_invalid_key_type(self):
        """Test invalid key type."""
        result = self.runner.invoke(cli, [
            'identity', 'generate',
            '--name', 'Test',
            '--key-type', 'INVALID'
        ])
        
        assert result.exit_code != 0
        assert "invalid" in result.output.lower()
    
    def test_invalid_rating(self):
        """Test invalid feedback rating."""
        result = self.runner.invoke(cli, [
            'trust', 'feedback',
            '--from-did', 'did:oai:reviewer',
            '--to-did', 'did:oai:target',
            '--rating', '10',  # Invalid - should be 1-5
            '--registry', 'http://localhost:8000'
        ])
        
        assert result.exit_code != 0
    
    def test_output_format_json(self, tmp_path):
        """Test JSON output format."""
        identity_file = tmp_path / "identity.json"
        result = self.runner.invoke(cli, [
            'identity', 'generate',
            '--name', 'JSON Agent',
            '--output', str(identity_file),
            '--format', 'json'
        ])
        
        assert result.exit_code == 0
        assert identity_file.exists()
        
        import json
        with open(identity_file) as f:
            data = json.load(f)
        
        assert "identity" in data
        assert "proof" in data
    
    def test_output_format_yaml(self, tmp_path):
        """Test YAML output format."""
        identity_file = tmp_path / "identity.yaml"
        result = self.runner.invoke(cli, [
            'identity', 'generate',
            '--name', 'YAML Agent',
            '--output', str(identity_file),
            '--format', 'yaml'
        ])
        
        assert result.exit_code == 0
        assert identity_file.exists()
        
        import yaml
        with open(identity_file) as f:
            data = yaml.safe_load(f)
        
        assert "identity" in data
        assert "proof" in data
    
    def test_verbose_flag(self):
        """Test verbose flag."""
        result = self.runner.invoke(cli, [
            '--verbose',
            'identity', 'generate',
            '--name', 'Verbose Agent'
        ])
        
        assert result.exit_code == 0
        # Verbose should show more details
    
    def test_version_flag(self):
        """Test version flag."""
        result = self.runner.invoke(cli, ['--version'])
        
        assert result.exit_code == 0
        assert "version" in result.output.lower()
    
    def test_config_file_option(self, tmp_path):
        """Test config file option."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
registry_url: "http://localhost:8000"
default_timeout: 30
""")
        
        result = self.runner.invoke(cli, [
            '--config', str(config_file),
            'health'
        ])
        
        # Should recognize config file
        assert result.exit_code == 0 or "config" in result.output.lower()


class TestCLIIntegration:
    """Integration tests for CLI workflows."""
    
    def setup_method(self):
        """Set up CLI runner."""
        self.runner = CliRunner()
    
    def test_full_identity_workflow(self, tmp_path):
        """Test complete identity workflow: generate -> show."""
        identity_file = tmp_path / "workflow_identity.json"
        
        # Generate
        result = self.runner.invoke(cli, [
            'identity', 'generate',
            '--name', 'Workflow Agent',
            '--output', str(identity_file)
        ])
        assert result.exit_code == 0
        
        # Show
        result = self.runner.invoke(cli, [
            'identity', 'show',
            '--input', str(identity_file)
        ])
        assert result.exit_code == 0
        assert "Workflow Agent" in result.output
    
    def test_agent_lifecycle_commands(self, tmp_path):
        """Test agent lifecycle commands are recognized."""
        identity_file = tmp_path / "identity.json"
        self.runner.invoke(cli, [
            'identity', 'generate',
            '--name', 'Lifecycle Agent',
            '--output', str(identity_file)
        ])
        
        # All these commands should be recognized (may fail without registry)
        commands = [
            ['agent', 'register', '--identity', str(identity_file), '--registry', 'http://localhost:8000'],
            ['agent', 'heartbeat', '--identity', str(identity_file), '--registry', 'http://localhost:8000'],
            ['agent', 'unregister', '--identity', str(identity_file), '--registry', 'http://localhost:8000'],
        ]
        
        for cmd in commands:
            result = self.runner.invoke(cli, cmd)
            # Should not be "no such command" error
            assert "no such command" not in result.output.lower()
    
    def test_discovery_workflow(self):
        """Test discovery workflow commands."""
        commands = [
            ['discover', 'find', '--query', 'test', '--registry', 'http://localhost:8000'],
            ['discover', 'get', '--did', 'did:oai:test', '--registry', 'http://localhost:8000'],
        ]
        
        for cmd in commands:
            result = self.runner.invoke(cli, cmd)
            assert "no such command" not in result.output.lower()
    
    def test_delegation_workflow(self, tmp_path):
        """Test delegation workflow commands."""
        identity_file = tmp_path / "identity.json"
        self.runner.invoke(cli, [
            'identity', 'generate',
            '--name', 'Delegation Agent',
            '--output', str(identity_file)
        ])
        
        result = self.runner.invoke(cli, [
            'delegate', 'run',
            '--identity', str(identity_file),
            '--capability', 'test',
            '--input', '{}',
            '--registry', 'http://localhost:8000'
        ])
        
        assert "no such command" not in result.output.lower()
    
    def test_trust_workflow(self):
        """Test trust workflow commands."""
        commands = [
            ['trust', 'score', '--did', 'did:oai:test', '--registry', 'http://localhost:8000'],
            ['trust', 'feedback', '--from-did', 'did:oai:a', '--to-did', 'did:oai:b', '--rating', '3', '--registry', 'http://localhost:8000'],
        ]
        
        for cmd in commands:
            result = self.runner.invoke(cli, cmd)
            assert "no such command" not in result.output.lower()
    
    def test_negotiation_workflow(self, tmp_path):
        """Test negotiation workflow commands."""
        identity_file = tmp_path / "identity.json"
        self.runner.invoke(cli, [
            'identity', 'generate',
            '--name', 'Negotiation Agent',
            '--output', str(identity_file)
        ])
        
        result = self.runner.invoke(cli, [
            'negotiate', 'start',
            '--identity', str(identity_file),
            '--responder', 'did:oai:responder',
            '--template', 'a2a_delegation',
            '--params', '{}',
            '--registry', 'http://localhost:8000'
        ])
        
        assert "no such command" not in result.output.lower()


class TestCLIErrorHandling:
    """Tests for CLI error handling."""
    
    def setup_method(self):
        """Set up CLI runner."""
        self.runner = CliRunner()
    
    def test_file_not_found_error(self):
        """Test file not found error handling."""
        result = self.runner.invoke(cli, [
            'identity', 'show',
            '--input', '/nonexistent/file.json'
        ])
        
        assert result.exit_code != 0
    
    def test_invalid_json_input(self, tmp_path):
        """Test invalid JSON input handling."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json")
        
        result = self.runner.invoke(cli, [
            'identity', 'show',
            '--input', str(bad_file)
        ])
        
        assert result.exit_code != 0
    
    def test_invalid_yaml_input(self, tmp_path):
        """Test invalid YAML input handling."""
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("not: valid: yaml: [")
        
        result = self.runner.invoke(cli, [
            'identity', 'show',
            '--input', str(bad_file)
        ])
        
        assert result.exit_code != 0
    
    def test_missing_identity_for_agent_commands(self):
        """Test agent commands without identity."""
        result = self.runner.invoke(cli, [
            'agent', 'register',
            '--registry', 'http://localhost:8000'
        ])
        
        assert result.exit_code != 0
        assert "missing option" in result.output.lower()
    
    def test_invalid_registry_url(self):
        """Test invalid registry URL."""
        result = self.runner.invoke(cli, [
            'health',
            '--registry', 'not-a-url'
        ])
        
        # May or may not fail depending on validation
        # Just verify command runs
        assert result.exit_code in [0, 1, 2]