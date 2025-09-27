"""
Configuration settings for the RPA solution.
"""

import os
from pathlib import Path
from typing import Any, Optional

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
    Manages configuration with environment and flow-specific overrides.
    
    This class provides a hierarchical configuration system that supports:
    - Environment-specific configuration (development, staging, production)
    - Flow-specific overrides within each environment
    - Fallback to global configuration for backwards compatibility
    - Support for both secrets (encrypted) and variables (plain text)
    
    Configuration lookup hierarchy (most specific to least specific):
    1. {environment}.{flow}.{key} - Flow-specific in specific environment
    2. {environment}.global.{key} - Global in specific environment  
    3. global.{key} - Base global (backwards compatibility)
    """
    
    def __init__(self, flow_name: Optional[str] = None, environment: Optional[str] = None):
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
    
    def _detect_environment(self) -> str:
        """Detect current environment from environment variables."""
        return os.getenv("PREFECT_ENVIRONMENT", "development")
    
    def get_secret(self, key: str, default: Any = None) -> Any:
        """
        Get secret with environment and flow-specific override.
        
        Args:
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Secret value or default
        """
        # Try flow-specific secret first (most specific)
        if self.flow_name:
            try:
                secret_name = f"{self.environment}-{self.flow_name}-{key.replace('_', '-')}"
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
        Get variable with environment and flow-specific override.
        
        Args:
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Variable value or default
        """
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
    
    def get_all_config(self, keys: list[str], is_secret: bool = False) -> dict[str, Any]:
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


# Global config instance (no flow-specific overrides)
config = ConfigManager()

# Flow-specific config instances
rpa1_config = ConfigManager("rpa1")
rpa2_config = ConfigManager("rpa2")

