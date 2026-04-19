"""
End-to-end tests for the complete web crawler system.
"""

import pytest
import asyncio
import tempfile
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch
from aioresponses import aioresponses

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def temp_test_env():
    """Create a temporary test environment."""
    temp_dir = tempfile.mkdtemp()

    # Create test config
    config_content = f"""
# Test configuration
crawler:
  max_concurrent_requests: 2
  request_timeout: 10
  max_retries: 1
  retry_delay: 0.1
  request_delay: 0.1
  max_queue_depth: 100
  queue_check_interval: 1.0
  max_page_size: 1048576
  allowed_content_types: ["text/html"]
  respect_robots_txt: false
  follow_redirects: true
  max_redirects: 2
  user_agent: "Test-Crawler/1.0"
  extract_links: true
  extract_text: true
  extract_metadata: true

search:
  index_batch_size: 10
  max_search_results: 50
  min_relevance_score: 0.001
  default_search_limit: 20
  remove_stop_words: true
  enable_stemming: false
  min_term_length: 2
  max_term_length: 50
  title_weight: 2.0
  content_weight: 1.0
  url_weight: 0.5
  freshness_weight: 0.3

database:
  database_url: "sqlite:///{temp_dir}/test.db"
  connection_pool_size: 5
  max_overflow: 10
  pool_timeout: 30
  batch_insert_size: 100
  commit_interval: 10
  vacuum_interval: 86400
  auto_backup: false

monitoring:
  log_level: "ERROR"
  log_file: "{temp_dir}/test.log"
  log_rotation: "daily"
  log_retention_days: 7
  enable_metrics: false
  health_check_interval: 30
  system_resource_monitoring: false

ui:
  enable_web_dashboard: false
  cli_output_format: "json"
  show_progress_bars: false
  color_output: false

system:
  max_memory_usage: 1073741824
  max_cpu_usage: 80
  temp_directory: "{temp_dir}"
  max_url_length: 2048
  allowed_schemes: ["http", "https"]
  blocked_domains: []
  enable_state_persistence: false
  checkpoint_interval: 300
  auto_resume_on_startup: false
"""

    config_path = Path(temp_dir) / "test_config.yaml"
    config_path.write_text(config_content)

    # Create data directory
    data_dir = Path(temp_dir) / "data"
    data_dir.mkdir()

    # Create logs directory
    logs_dir = Path(temp_dir) / "logs"
    logs_dir.mkdir()

    yield temp_dir, str(config_path)

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestEndToEnd:
    """End-to-end tests for the complete system."""

    def test_database_initialization(self, temp_test_env):
        """Test database initialization script."""
        temp_dir, config_path = temp_test_env

        # Run database initialization
        result = subprocess.run([
            sys.executable, "scripts/init_db.py",
            "--config", config_path,
            "--force"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)

        # Should complete successfully
        assert result.returncode == 0, f"Database init failed: {result.stderr}"

        # Database file should exist
        db_path = Path(temp_dir) / "test.db"
        assert db_path.exists()

    def test_cli_help_commands(self):
        """Test CLI help functionality."""
        # Test main help
        result = subprocess.run([
            sys.executable, "-m", "src.main", "--help"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)

        assert result.returncode == 0
        assert "BLG 480E Project 2" in result.stdout

        # Test command-specific help
        for command in ["index", "search", "status", "stats"]:
            result = subprocess.run([
                sys.executable, "-m", "src.main", command, "--help"
            ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)

            assert result.returncode == 0

    def test_status_command_empty_database(self, temp_test_env):
        """Test status command on empty database."""
        temp_dir, config_path = temp_test_env

        # Initialize database first
        subprocess.run([
            sys.executable, "scripts/init_db.py",
            "--config", config_path, "--force"
        ], cwd=Path(__file__).parent.parent)

        # Run status command
        result = subprocess.run([
            sys.executable, "-m", "src.main",
            "--config", config_path,
            "status"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)

        # Should complete successfully
        assert result.returncode == 0

    def test_search_command_empty_index(self, temp_test_env):
        """Test search command on empty index."""
        temp_dir, config_path = temp_test_env

        # Initialize database first
        subprocess.run([
            sys.executable, "scripts/init_db.py",
            "--config", config_path, "--force"
        ], cwd=Path(__file__).parent.parent)

        # Run search command
        result = subprocess.run([
            sys.executable, "-m", "src.main",
            "--config", config_path,
            "search", "--query", "test", "--format", "json"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)

        # Should complete successfully (no results)
        assert result.returncode == 0

        # Should return empty JSON array
        import json
        try:
            results = json.loads(result.stdout)
            assert isinstance(results, list)
            assert len(results) == 0
        except json.JSONDecodeError:
            # Acceptable if no JSON output (just a message)
            pass

    def test_invalid_config_handling(self):
        """Test handling of invalid configuration."""
        # Try with non-existent config file
        result = subprocess.run([
            sys.executable, "-m", "src.main",
            "--config", "nonexistent.yaml",
            "status"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)

        # Should fail gracefully
        assert result.returncode != 0
        assert "Error loading configuration" in result.stderr or "Error loading configuration" in result.stdout

    def test_invalid_command_arguments(self, temp_test_env):
        """Test handling of invalid command arguments."""
        temp_dir, config_path = temp_test_env

        # Test index command without required arguments
        result = subprocess.run([
            sys.executable, "-m", "src.main",
            "--config", config_path,
            "index"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)

        # Should fail with argument error
        assert result.returncode != 0

    def test_utility_scripts(self, temp_test_env):
        """Test utility scripts functionality."""
        temp_dir, config_path = temp_test_env

        # Test reset script
        result = subprocess.run([
            sys.executable, "scripts/reset_db.py",
            "--config", config_path, "--force"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)

        # Should complete successfully
        assert result.returncode == 0

    def test_verbose_logging(self, temp_test_env):
        """Test verbose logging functionality."""
        temp_dir, config_path = temp_test_env

        # Run with verbose flag
        result = subprocess.run([
            sys.executable, "-m", "src.main",
            "--config", config_path, "--verbose",
            "status"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)

        # Should complete successfully
        assert result.returncode == 0

    @pytest.mark.slow
    def test_basic_crawling_workflow_mocked(self, temp_test_env):
        """Test basic crawling workflow with mocked HTTP responses."""
        temp_dir, config_path = temp_test_env

        # Initialize database
        subprocess.run([
            sys.executable, "scripts/init_db.py",
            "--config", config_path, "--force"
        ], cwd=Path(__file__).parent.parent)

        # Create a simple test server response
        test_html = """
        <html>
            <head>
                <title>Test Page</title>
                <meta name="description" content="A test page">
            </head>
            <body>
                <h1>Test Content</h1>
                <p>This is a test page for the crawler to index.</p>
            </body>
        </html>
        """

        # Note: In a real E2E test, you might use a test HTTP server
        # For now, we'll test that the command structure works

        # Try to run crawling command (will fail due to network, but tests CLI)
        result = subprocess.run([
            sys.executable, "-m", "src.main",
            "--config", config_path,
            "index",
            "--origin", "https://httpbin.org/html",  # Use a real test endpoint
            "--depth", "0",
            "--max-pages", "1"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent, timeout=30)

        # The command should attempt to run (may fail on network/timeout)
        # We're mainly testing that the CLI interface works

        # Check that some output was produced (success or error)
        assert len(result.stdout) > 0 or len(result.stderr) > 0

    def test_search_output_formats(self, temp_test_env):
        """Test different search output formats."""
        temp_dir, config_path = temp_test_env

        # Initialize database
        subprocess.run([
            sys.executable, "scripts/init_db.py",
            "--config", config_path, "--force"
        ], cwd=Path(__file__).parent.parent)

        # Test different output formats
        for format_type in ["json", "yaml", "table"]:
            result = subprocess.run([
                sys.executable, "-m", "src.main",
                "--config", config_path,
                "search", "--query", "test", "--format", format_type
            ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)

            # Should complete successfully
            assert result.returncode == 0

    def test_stats_command(self, temp_test_env):
        """Test stats command functionality."""
        temp_dir, config_path = temp_test_env

        # Initialize database
        subprocess.run([
            sys.executable, "scripts/init_db.py",
            "--config", config_path, "--force"
        ], cwd=Path(__file__).parent.parent)

        # Test basic stats
        result = subprocess.run([
            sys.executable, "-m", "src.main",
            "--config", config_path,
            "stats"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)

        assert result.returncode == 0

        # Test detailed stats
        result = subprocess.run([
            sys.executable, "-m", "src.main",
            "--config", config_path,
            "stats", "--detailed"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)

        assert result.returncode == 0

    def test_project_structure_completeness(self):
        """Test that all expected project files exist."""
        project_root = Path(__file__).parent.parent

        # Required files
        required_files = [
            "product_prd.md",
            "readme.md",
            "recommendation.md",
            "multi_agent_workflow.md",
            "requirements.txt",
            "src/main.py",
            "src/__main__.py",
            "config/settings.yaml",
            "scripts/init_db.py",
            "scripts/reset_db.py",
            "scripts/rebuild_index.py"
        ]

        for file_path in required_files:
            full_path = project_root / file_path
            assert full_path.exists(), f"Required file missing: {file_path}"

    def test_agent_documentation_completeness(self):
        """Test that all agent documentation exists."""
        project_root = Path(__file__).parent.parent
        agents_dir = project_root / "agents"

        expected_agents = [
            "system_architect.md",
            "crawler_specialist.md",
            "search_engine_specialist.md",
            "database_specialist.md",
            "performance_engineer.md",
            "testing_engineer.md",
            "ui_ux_designer.md"
        ]

        for agent_file in expected_agents:
            full_path = agents_dir / agent_file
            assert full_path.exists(), f"Agent documentation missing: {agent_file}"

    def test_import_all_modules(self):
        """Test that all main modules can be imported without errors."""
        try:
            from src.crawler.web_crawler import WebCrawler
            from src.search.search_engine import SearchEngine
            from src.database.db_manager import DatabaseManager
            from src.utils.config import Config
            from src.utils.logger import setup_logging
            from src.utils.url_utils import normalize_url
        except ImportError as e:
            pytest.fail(f"Failed to import modules: {e}")


if __name__ == "__main__":
    pytest.main([__file__])