"""
Configuration settings for the RPA solution.
"""

import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from prefect.blocks.system import Secret
from prefect.variables import Variable

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
# RPA1 directories
RPA1_DATA_DIR = PROJECT_ROOT / "flows" / "rpa1" / "data"
RPA1_OUTPUT_DIR = PROJECT_ROOT / "flows" / "rpa1" / "output"

# RPA2 directories
RPA2_DATA_DIR = PROJECT_ROOT / "flows" / "rpa2" / "data"
RPA2_OUTPUT_DIR = PROJECT_ROOT / "flows" / "rpa2" / "output"

# Backward compatibility (deprecated)
DATA_DIR = RPA1_DATA_DIR
OUTPUT_DIR = RPA1_OUTPUT_DIR
LOGS_DIR = PROJECT_ROOT / "logs"

# Default settings
DEFAULT_CLEANUP = True
DEFAULT_OUTPUT_FORMAT = "json"

# File patterns
CSV_EXTENSION = ".csv"
JSON_EXTENSION = ".json"
REPORT_PREFIX = "sales_report_"

# Sample data configuration
SAMPLE_PRODUCTS = [
    {"product": "Widget A", "quantity": 100, "price": 10.50, "date": "2024-01-15"},
    {"product": "Widget B", "quantity": 75, "price": 15.75, "date": "2024-01-16"},
    {"product": "Widget C", "quantity": 200, "price": 8.25, "date": "2024-01-17"},
    {"product": "Widget A", "quantity": 150, "price": 10.50, "date": "2024-01-18"},
    {"product": "Widget B", "quantity": 50, "price": 15.75, "date": "2024-01-19"},
]


class ConfigManager:
    """
    Enhanced configuration manager with .env file support.

    This class provides a hierarchical configuration system that supports:
    - .env file configuration (primary)
    - Environment-specific configuration (development, staging, production)
    - Flow-specific overrides within each environment
    - Prefect Secret/Variable blocks (fallback)
    - Distributed processing configuration with validation

    Configuration lookup hierarchy (most specific to least specific):
    1. .env files: flows/{flow}/.env.{environment} (overrides global)
    2. .env files: core/envs/.env.{environment} (global)
    3. Prefect: {environment}.{flow}.{key} - Flow-specific in specific environment
    4. Prefect: {environment}.global.{key} - Global in specific environment
    5. Prefect: global.{key} - Base global (backwards compatibility)
    """

    def __init__(
        self, flow_name: Optional[str] = None, environment: Optional[str] = None
    ):
        """
        Initialize the configuration manager.

        Args:
            flow_name: Name of the flow (e.g., 'rpa1', 'rpa2')
            environment: Environment name (e.g., 'development', 'staging', 'production')
                        If None, will be detected from PREFECT_ENVIRONMENT env var
        """
        self.flow_name = flow_name
        self.environment = environment or self._detect_environment()
        self._cache = {}

        # Load .env files
        self._load_env_files()

    def _detect_environment(self) -> str:
        """Detect current environment from environment variables."""
        return os.getenv("PREFECT_ENVIRONMENT", "development")

    def _load_env_files(self):
        """Load .env files in hierarchical order."""
        # 1. Load global .env file
        global_env_file = PROJECT_ROOT / "core" / "envs" / f".env.{self.environment}"
        if global_env_file.exists():
            load_dotenv(global_env_file)
            print(f"📁 Loaded global config: {global_env_file}")

        # 2. Load flow-specific .env file (overrides global)
        if self.flow_name:
            flow_env_file = (
                PROJECT_ROOT / "flows" / self.flow_name / f".env.{self.environment}"
            )
            if flow_env_file.exists():
                load_dotenv(flow_env_file, override=True)  # override=True for hierarchy
                print(f"📁 Loaded flow config: {flow_env_file}")

    def get_secret(self, key: str, default: Any = None) -> Any:
        """
        Get secret with .env file support and hierarchical fallback.

        Args:
            key: Configuration key
            default: Default value if not found

        Returns:
            Secret value or default
        """
        # 1. Try .env file first (most specific)
        env_key = (
            f"{self.environment.upper()}_{self.flow_name.upper()}_{key.upper()}"
            if self.flow_name
            else f"{self.environment.upper()}_GLOBAL_{key.upper()}"
        )
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value

        # 2. Try Prefect secrets (fallback)
        # Try flow-specific secret first
        if self.flow_name:
            try:
                secret_name = (
                    f"{self.environment}-{self.flow_name}-{key.replace('_', '-')}"
                )
                secret = Secret.load(secret_name)
                return secret.get()
            except ValueError:
                pass

        # Try environment-specific global secret
        try:
            secret_name = f"{self.environment}-global-{key.replace('_', '-')}"
            secret = Secret.load(secret_name)
            return secret.get()
        except ValueError:
            pass

        # Fall back to base global secret (for backwards compatibility)
        try:
            secret_name = f"global-{key.replace('_', '-')}"
            secret = Secret.load(secret_name)
            return secret.get()
        except ValueError:
            return default

    def get_variable(self, key: str, default: Any = None) -> Any:
        """
        Get variable with .env file support and hierarchical fallback.

        Args:
            key: Configuration key
            default: Default value if not found

        Returns:
            Variable value or default
        """
        # 1. Try .env file first (most specific)
        env_key = (
            f"{self.environment.upper()}_{self.flow_name.upper()}_{key.upper()}"
            if self.flow_name
            else f"{self.environment.upper()}_GLOBAL_{key.upper()}"
        )
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value

        # 2. Try Prefect variables (fallback)
        # Try flow-specific variable first
        if self.flow_name:
            try:
                var_name = f"{self.environment}_{self.flow_name}_{key}"
                return Variable.get(var_name)
            except ValueError:
                pass

        # Try environment-specific global variable
        try:
            var_name = f"{self.environment}_global_{key}"
            return Variable.get(var_name)
        except ValueError:
            pass

        # Fall back to base global variable
        try:
            var_name = f"global_{key}"
            return Variable.get(var_name)
        except ValueError:
            return default

    def get_config(self, key: str, default: Any = None, is_secret: bool = False) -> Any:
        """
        Get configuration value (secret or variable).

        Args:
            key: Configuration key
            default: Default value if not found
            is_secret: Whether to look for a secret (True) or variable (False)

        Returns:
            Configuration value or default
        """
        if is_secret:
            return self.get_secret(key, default)
        else:
            return self.get_variable(key, default)

    def get_all_config(
        self, keys: list[str], is_secret: bool = False
    ) -> dict[str, Any]:
        """
        Get multiple configuration values at once.

        Args:
            keys: List of configuration keys
            is_secret: Whether to look for secrets (True) or variables (False)

        Returns:
            Dictionary of key-value pairs
        """
        result = {}
        for key in keys:
            result[key] = self.get_config(key, is_secret=is_secret)
        return result

    def get_distributed_config(self) -> dict[str, Any]:
        """
        Get distributed processing configuration with defaults and validation.

        Returns configuration for distributed processing including batch sizes,
        timeout values, retry limits, and database connection validation.

        Returns:
            Dictionary containing distributed processing configuration:
            {
                "default_batch_size": int,
                "cleanup_timeout_hours": int,
                "max_retries": int,
                "health_check_interval": int,
                "required_databases": list[str],
                "enable_distributed_processing": bool
            }

        Raises:
            ValueError: If configuration validation fails
            RuntimeError: If required database connections are not configured
        """
        # Get configuration values with defaults
        config = {
            "default_batch_size": self._get_int_config(
                "DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE", 100
            ),
            "cleanup_timeout_hours": self._get_int_config(
                "DISTRIBUTED_PROCESSOR_CLEANUP_TIMEOUT_HOURS", 1
            ),
            "max_retries": self._get_int_config("DISTRIBUTED_PROCESSOR_MAX_RETRIES", 3),
            "health_check_interval": self._get_int_config(
                "DISTRIBUTED_PROCESSOR_HEALTH_CHECK_INTERVAL", 300
            ),
            "enable_distributed_processing": self._get_bool_config(
                "DISTRIBUTED_PROCESSOR_ENABLED", True
            ),
        }

        # Get required databases configuration
        required_databases = self.get_config(
            "DISTRIBUTED_PROCESSOR_REQUIRED_DATABASES", "rpa_db,SurveyHub"
        )
        if isinstance(required_databases, str):
            config["required_databases"] = [
                db.strip() for db in required_databases.split(",") if db.strip()
            ]
        else:
            config["required_databases"] = ["rpa_db", "SurveyHub"]

        # Validate configuration
        self._validate_distributed_config(config)

        return config

    def _get_int_config(self, key: str, default: int) -> int:
        """
        Get integer configuration value with validation.

        Args:
            key: Configuration key
            default: Default integer value

        Returns:
            Integer configuration value

        Raises:
            ValueError: If value cannot be converted to integer or is invalid
        """
        value = self.get_config(key, default)

        # If value is None, use default
        if value is None:
            return default

        if isinstance(value, int):
            if value <= 0:
                raise ValueError(f"Configuration {key} must be positive, got: {value}")
            return value

        if isinstance(value, str):
            # Handle empty string
            if not value.strip():
                return default
            try:
                int_value = int(value)
                if int_value <= 0:
                    raise ValueError(
                        f"Configuration {key} must be positive, got: {int_value}"
                    )
                return int_value
            except ValueError as e:
                if "positive" in str(e):
                    raise
                raise ValueError(
                    f"Configuration {key} must be an integer, got: {value}"
                ) from e

        # For any other type, use default
        return default

    def _get_bool_config(self, key: str, default: bool) -> bool:
        """
        Get boolean configuration value with validation.

        Args:
            key: Configuration key
            default: Default boolean value

        Returns:
            Boolean configuration value
        """
        value = self.get_config(key, default)

        # If value is None, use default
        if value is None:
            return default

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            lower_value = value.lower().strip()
            if lower_value in ("true", "1", "yes", "on", "enabled"):
                return True
            elif lower_value in ("false", "0", "no", "off", "disabled"):
                return False
            else:
                raise ValueError(
                    f"Configuration {key} must be a boolean value, got: {value}"
                )

        return bool(value)

    def _validate_distributed_config(self, config: dict[str, Any]) -> None:
        """
        Validate distributed processing configuration.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If configuration validation fails
            RuntimeError: If required database connections are not configured
        """
        # Validate batch size
        if config["default_batch_size"] <= 0 or config["default_batch_size"] > 1000:
            raise ValueError(
                f"default_batch_size must be between 1 and 1000, "
                f"got: {config['default_batch_size']}"
            )

        # Validate timeout hours
        if config["cleanup_timeout_hours"] <= 0 or config["cleanup_timeout_hours"] > 24:
            raise ValueError(
                f"cleanup_timeout_hours must be between 1 and 24, "
                f"got: {config['cleanup_timeout_hours']}"
            )

        # Validate max retries
        if config["max_retries"] <= 0 or config["max_retries"] > 10:
            raise ValueError(
                f"max_retries must be between 1 and 10, got: {config['max_retries']}"
            )

        # Validate health check interval
        if (
            config["health_check_interval"] < 60
            or config["health_check_interval"] > 3600
        ):
            raise ValueError(
                f"health_check_interval must be between 60 and 3600 seconds, "
                f"got: {config['health_check_interval']}"
            )

        # Validate required databases are configured
        for db_name in config["required_databases"]:
            db_type_key = f"{db_name.upper()}_TYPE"
            db_conn_key = f"{db_name.upper()}_CONNECTION_STRING"

            db_type = self.get_config(db_type_key)
            db_conn = self.get_config(db_conn_key)

            if not db_type:
                raise RuntimeError(
                    f"Required database '{db_name}' type not configured. "
                    f"Please set {self.environment.upper()}_GLOBAL_{db_type_key}"
                )

            if not db_conn:
                raise RuntimeError(
                    f"Required database '{db_name}' connection string not configured. "
                    f"Please set {self.environment.upper()}_GLOBAL_{db_conn_key}"
                )

    def validate_distributed_processing_setup(self) -> dict[str, Any]:
        """
        Validate complete distributed processing setup.

        Performs comprehensive validation of distributed processing configuration
        including database connections, configuration values, and system readiness.

        Returns:
            Dictionary containing validation results:
            {
                "valid": bool,
                "config": dict,
                "errors": list[str],
                "warnings": list[str]
            }
        """
        validation_result = {"valid": True, "config": {}, "errors": [], "warnings": []}

        try:
            # Get and validate distributed configuration
            config = self.get_distributed_config()
            validation_result["config"] = config

            # Check if distributed processing is enabled
            if not config["enable_distributed_processing"]:
                validation_result["warnings"].append(
                    "Distributed processing is disabled in configuration"
                )

            # Additional validation warnings
            if config["default_batch_size"] > 500:
                validation_result["warnings"].append(
                    f"Large batch size ({config['default_batch_size']}) may impact performance"
                )

            if config["cleanup_timeout_hours"] < 1:
                validation_result["warnings"].append(
                    f"Short cleanup timeout ({config['cleanup_timeout_hours']} hours) "
                    "may cause premature record cleanup"
                )

        except (ValueError, RuntimeError) as e:
            validation_result["valid"] = False
            validation_result["errors"].append(str(e))

        return validation_result


# Global config instance (no flow-specific overrides)
config = ConfigManager()

# Flow-specific config instances
rpa1_config = ConfigManager("rpa1")
rpa2_config = ConfigManager("rpa2")
rpa3_config = ConfigManager("rpa3")

# Distributed processing config instance
distributed_config = ConfigManager()
