"""
Logging configuration and utilities.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import structlog


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    enable_structured: bool = True,
    enable_colors: bool = True
) -> None:
    """
    Setup logging configuration for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        enable_structured: Whether to use structured logging
        enable_colors: Whether to enable colored output (console only)
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    if enable_structured:
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer() if log_file else structlog.dev.ConsoleRenderer(colors=enable_colors)
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        # Get the root logger and set its level
        root_logger = logging.getLogger()
        root_logger.setLevel(numeric_level)

        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        if enable_colors and not log_file:
            formatter = logging.Formatter(
                '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            )
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # File handler (if specified)
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(numeric_level)
            file_formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)

    else:
        # Standard logging configuration
        logging.basicConfig(
            level=numeric_level,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_file) if log_file else logging.NullHandler()
            ]
        )

    # Set specific logger levels
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    # Log the logging setup
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured: level={level}, file={log_file or 'console only'}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class LogContext:
    """Context manager for adding context to log messages."""

    def __init__(self, logger: logging.Logger, **context):
        """
        Initialize log context.

        Args:
            logger: Logger instance
            **context: Context key-value pairs
        """
        self.logger = logger
        self.context = context
        self.original_extra = {}

    def __enter__(self):
        """Enter the context."""
        # Store original extra attributes
        for key in self.context:
            if hasattr(self.logger, key):
                self.original_extra[key] = getattr(self.logger, key)

        # Set new context
        for key, value in self.context.items():
            setattr(self.logger, key, value)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context."""
        # Restore original attributes
        for key in self.context:
            if key in self.original_extra:
                setattr(self.logger, key, self.original_extra[key])
            else:
                if hasattr(self.logger, key):
                    delattr(self.logger, key)


def log_function_call(logger: Optional[logging.Logger] = None, level: str = "DEBUG"):
    """
    Decorator to log function calls with parameters and results.

    Args:
        logger: Logger instance (if None, uses function's module logger)
        level: Logging level for the messages

    Returns:
        Decorated function
    """
    def decorator(func):
        import functools
        import inspect

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get logger
            func_logger = logger or logging.getLogger(func.__module__)
            log_level = getattr(logging, level.upper(), logging.DEBUG)

            # Log function entry
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            func_logger.log(
                log_level,
                f"Calling {func.__name__} with args: {bound_args.arguments}"
            )

            try:
                # Call function
                result = func(*args, **kwargs)

                # Log successful completion
                func_logger.log(
                    log_level,
                    f"Completed {func.__name__} successfully"
                )

                return result

            except Exception as e:
                # Log exception
                func_logger.error(
                    f"Exception in {func.__name__}: {e}",
                    exc_info=True
                )
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get logger
            func_logger = logger or logging.getLogger(func.__module__)
            log_level = getattr(logging, level.upper(), logging.DEBUG)

            # Log function entry
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            func_logger.log(
                log_level,
                f"Calling {func.__name__} with args: {bound_args.arguments}"
            )

            try:
                # Call async function
                result = await func(*args, **kwargs)

                # Log successful completion
                func_logger.log(
                    log_level,
                    f"Completed {func.__name__} successfully"
                )

                return result

            except Exception as e:
                # Log exception
                func_logger.error(
                    f"Exception in {func.__name__}: {e}",
                    exc_info=True
                )
                raise

        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator


class PerformanceTimer:
    """Context manager for timing operations."""

    def __init__(self, logger: logging.Logger, operation_name: str, level: str = "INFO"):
        """
        Initialize performance timer.

        Args:
            logger: Logger instance
            operation_name: Name of the operation being timed
            level: Logging level for timing messages
        """
        self.logger = logger
        self.operation_name = operation_name
        self.level = getattr(logging, level.upper(), logging.INFO)
        self.start_time = None

    def __enter__(self):
        """Start timing."""
        import time
        self.start_time = time.time()
        self.logger.log(self.level, f"Started {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End timing and log duration."""
        import time
        if self.start_time:
            duration = time.time() - self.start_time
            status = "failed" if exc_type else "completed"
            self.logger.log(
                self.level,
                f"{self.operation_name.title()} {status} in {duration:.3f}s"
            )


def setup_request_logging():
    """Setup HTTP request logging for debugging."""
    import http.client as http_client

    # Enable HTTP debugging
    http_client.HTTPConnection.debuglevel = 1

    # Configure requests logging
    logging.getLogger("requests.packages.urllib3").setLevel(logging.DEBUG)
    logging.getLogger("requests.packages.urllib3").propagate = True


def mask_sensitive_data(data: str, patterns: list = None) -> str:
    """
    Mask sensitive data in log messages.

    Args:
        data: String that may contain sensitive data
        patterns: List of regex patterns for sensitive data

    Returns:
        String with sensitive data masked
    """
    import re

    if not patterns:
        patterns = [
            r'password["\s]*[:=]["\s]*[^"&\s]+',
            r'token["\s]*[:=]["\s]*[^"&\s]+',
            r'key["\s]*[:=]["\s]*[^"&\s]+',
            r'secret["\s]*[:=]["\s]*[^"&\s]+',
        ]

    masked_data = data
    for pattern in patterns:
        masked_data = re.sub(pattern, lambda m: m.group().split('=')[0] + '=***', masked_data, flags=re.IGNORECASE)

    return masked_data