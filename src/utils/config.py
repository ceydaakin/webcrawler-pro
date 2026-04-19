"""
Configuration management utilities.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

import yaml
from pydantic import BaseModel, Field


class CrawlerConfig(BaseModel):
    """Crawler configuration settings."""
    max_concurrent_requests: int = Field(default=10, ge=1, le=100)
    request_timeout: int = Field(default=30, ge=5, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay: float = Field(default=1.0, ge=0.1, le=60.0)
    request_delay: float = Field(default=1.0, ge=0.1, le=10.0)
    max_queue_depth: int = Field(default=10000, ge=100, le=100000)
    queue_check_interval: float = Field(default=5.0, ge=1.0, le=60.0)
    max_page_size: int = Field(default=10485760, ge=1024, le=104857600)  # 1KB to 100MB
    allowed_content_types: list = Field(default=["text/html", "application/xhtml+xml"])
    respect_robots_txt: bool = Field(default=True)
    follow_redirects: bool = Field(default=True)
    max_redirects: int = Field(default=5, ge=1, le=20)
    user_agent: str = Field(default="BLG480E-WebCrawler/1.0")
    extract_links: bool = Field(default=True)
    extract_text: bool = Field(default=True)
    extract_metadata: bool = Field(default=True)


class SearchConfig(BaseModel):
    """Search engine configuration settings."""
    index_batch_size: int = Field(default=100, ge=1, le=10000)
    max_index_memory: int = Field(default=536870912, ge=1048576)  # 1MB minimum
    max_search_results: int = Field(default=50, ge=1, le=1000)
    min_relevance_score: float = Field(default=0.1, ge=0.0, le=1.0)
    default_search_limit: int = Field(default=20, ge=1, le=100)
    remove_stop_words: bool = Field(default=True)
    enable_stemming: bool = Field(default=True)
    min_term_length: int = Field(default=2, ge=1, le=10)
    max_term_length: int = Field(default=50, ge=10, le=200)
    title_weight: float = Field(default=2.0, ge=0.1, le=10.0)
    content_weight: float = Field(default=1.0, ge=0.1, le=10.0)
    url_weight: float = Field(default=0.5, ge=0.1, le=10.0)
    freshness_weight: float = Field(default=0.3, ge=0.0, le=5.0)


class DatabaseConfig(BaseModel):
    """Database configuration settings."""
    database_url: str = Field(default="sqlite:///data/webcrawler.db")
    connection_pool_size: int = Field(default=20, ge=1, le=100)
    max_overflow: int = Field(default=30, ge=0, le=100)
    pool_timeout: int = Field(default=30, ge=5, le=300)
    batch_insert_size: int = Field(default=1000, ge=1, le=10000)
    commit_interval: int = Field(default=100, ge=1, le=10000)
    vacuum_interval: int = Field(default=86400, ge=3600)  # 1 hour minimum
    auto_backup: bool = Field(default=True)
    backup_interval: int = Field(default=21600, ge=3600)  # 1 hour minimum
    backup_retention_days: int = Field(default=30, ge=1, le=365)


class MonitoringConfig(BaseModel):
    """Monitoring and logging configuration."""
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_file: str = Field(default="logs/webcrawler.log")
    log_rotation: str = Field(default="daily", pattern="^(daily|weekly|monthly|size)$")
    log_retention_days: int = Field(default=30, ge=1, le=365)
    enable_metrics: bool = Field(default=True)
    metrics_port: int = Field(default=8000, ge=1024, le=65535)
    metrics_interval: int = Field(default=60, ge=10, le=3600)
    health_check_interval: int = Field(default=30, ge=10, le=300)
    system_resource_monitoring: bool = Field(default=True)


class UIConfig(BaseModel):
    """User interface configuration."""
    enable_web_dashboard: bool = Field(default=True)
    dashboard_port: int = Field(default=8080, ge=1024, le=65535)
    dashboard_host: str = Field(default="127.0.0.1")
    cli_output_format: str = Field(default="table", pattern="^(table|json|yaml)$")
    show_progress_bars: bool = Field(default=True)
    color_output: bool = Field(default=True)


class SystemConfig(BaseModel):
    """System configuration settings."""
    max_memory_usage: int = Field(default=2147483648, ge=134217728)  # 128MB minimum
    max_cpu_usage: int = Field(default=80, ge=10, le=100)
    temp_directory: str = Field(default="/tmp/webcrawler")
    max_url_length: int = Field(default=2048, ge=100, le=8192)
    allowed_schemes: list = Field(default=["http", "https"])
    blocked_domains: list = Field(default=[])
    enable_state_persistence: bool = Field(default=True)
    checkpoint_interval: int = Field(default=300, ge=60, le=3600)
    auto_resume_on_startup: bool = Field(default=True)


class Config(BaseModel):
    """Main configuration class."""
    crawler: CrawlerConfig = Field(default_factory=CrawlerConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)

    @classmethod
    def load(cls, config_path: str) -> 'Config':
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to configuration file

        Returns:
            Config: Loaded configuration object

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file is invalid YAML
            ValueError: If config values are invalid
        """
        config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)

            # Handle empty or None config file
            if not config_data:
                config_data = {}

            return cls(**config_data)

        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Invalid YAML in config file {config_path}: {e}")
        except Exception as e:
            raise ValueError(f"Invalid configuration: {e}")

    def save(self, config_path: str) -> None:
        """
        Save configuration to YAML file.

        Args:
            config_path: Path where to save configuration
        """
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)

        config_dict = self.model_dump()

        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)

    @classmethod
    def create_default(cls, config_path: str) -> 'Config':
        """
        Create a default configuration file.

        Args:
            config_path: Path where to create the configuration file

        Returns:
            Config: Default configuration object
        """
        config = cls()
        config.save(config_path)
        return config

    def update_from_env(self) -> None:
        """
        Update configuration from environment variables.
        Environment variables should be prefixed with WEBCRAWLER_
        """
        env_mapping = {
            'WEBCRAWLER_DB_URL': ('database', 'database_url'),
            'WEBCRAWLER_LOG_LEVEL': ('monitoring', 'log_level'),
            'WEBCRAWLER_MAX_REQUESTS': ('crawler', 'max_concurrent_requests'),
            'WEBCRAWLER_REQUEST_TIMEOUT': ('crawler', 'request_timeout'),
            'WEBCRAWLER_DASHBOARD_PORT': ('ui', 'dashboard_port'),
            'WEBCRAWLER_ENABLE_METRICS': ('monitoring', 'enable_metrics'),
        }

        for env_var, (section, key) in env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                # Get the section object
                section_obj = getattr(self, section)

                # Convert value to appropriate type
                field_info = section_obj.model_fields[key]
                field_type = field_info.annotation

                try:
                    if field_type == bool:
                        converted_value = value.lower() in ('true', '1', 'yes', 'on')
                    elif field_type == int:
                        converted_value = int(value)
                    elif field_type == float:
                        converted_value = float(value)
                    elif field_type == list:
                        converted_value = [item.strip() for item in value.split(',')]
                    else:
                        converted_value = value

                    # Set the value
                    setattr(section_obj, key, converted_value)

                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid value for {env_var}: {value} ({e})")

    def validate(self) -> None:
        """
        Validate configuration values and relationships.

        Raises:
            ValueError: If configuration is invalid
        """
        errors = []

        # Validate port conflicts
        if self.ui.dashboard_port == self.monitoring.metrics_port:
            errors.append("Dashboard port and metrics port cannot be the same")

        # Validate resource limits
        if self.crawler.max_concurrent_requests > self.database.connection_pool_size:
            errors.append("Max concurrent requests should not exceed database connection pool size")

        # Validate directories
        try:
            Path(self.system.temp_directory).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create temp directory {self.system.temp_directory}: {e}")

        try:
            Path(self.monitoring.log_file).parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create log directory for {self.monitoring.log_file}: {e}")

        if errors:
            raise ValueError("Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors))

    def __str__(self) -> str:
        """Return a string representation of the configuration."""
        return f"WebCrawler Config:\n" \
               f"  Crawler: {self.crawler.max_concurrent_requests} concurrent requests\n" \
               f"  Database: {self.database.database_url}\n" \
               f"  Search: {self.search.max_search_results} max results\n" \
               f"  Monitoring: {self.monitoring.log_level} log level\n" \
               f"  UI: Dashboard on port {self.ui.dashboard_port}"