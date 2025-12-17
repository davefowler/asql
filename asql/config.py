"""ASQL Configuration System.

This module provides the configuration system for ASQL style preferences.
Config affects OUTPUT style (reverse_compile, normalize), not input parsing.
ASQL always accepts all valid syntaxes on input.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional, Dict, Any
from pathlib import Path
import json


@dataclass
class StyleConfig:
    """Style configuration options for ASQL output.
    
    These settings control how ASQL is written when:
    - Converting SQL to ASQL (reverse_compile)
    - Normalizing ASQL (normalize)
    
    Input parsing always accepts all valid syntaxes regardless of these settings.
    """
    
    # Equality operator: = (SQL style) or == (Python style)
    equality: Literal["single", "double"] = "single"
    
    # Count notation: # (shorthand) or count(*) (function)
    count: Literal["hash", "function"] = "hash"
    
    # Null coalescing: ?? (operator) or coalesce() (function)
    coalesce: Literal["operator", "function"] = "operator"
    
    # Row limiting keyword
    limit_keyword: Literal["limit"] = "limit"
    
    # Descending order: -col (prefix) or col DESC (suffix)
    descending: Literal["prefix", "suffix"] = "prefix"
    
    # Type casting: :: (PostgreSQL) or CAST() (SQL standard)
    cast: Literal["double_colon", "function"] = "double_colon"
    
    # String quotes: " (double) or ' (single)
    quotes: Literal["double", "single"] = "double"
    
    # Week start day for week() function
    week_start: Literal["monday", "sunday"] = "monday"
    
    # Sort keyword: order by or sort
    sort_keyword: Literal["order_by", "sort"] = "order_by"
    
    # CTE handling: squash pass-through CTEs like "from table stash as name"
    # When True, removes CTEs that are just SELECT * FROM table with no transforms
    squash_empty_ctes: bool = True
    
    # Keep final empty CTE: dbt users often have a final "stash as X" then "from X" pattern
    # When True, keeps this pattern even if squash_empty_ctes is True
    # Only applies to empty CTEs - non-empty CTEs are never squashed
    keep_final_empty_cte: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "equality": self.equality,
            "count": self.count,
            "coalesce": self.coalesce,
            "limit_keyword": self.limit_keyword,
            "descending": self.descending,
            "cast": self.cast,
            "quotes": self.quotes,
            "week_start": self.week_start,
            "sort_keyword": self.sort_keyword,
            "squash_empty_ctes": self.squash_empty_ctes,
            "keep_final_empty_cte": self.keep_final_empty_cte,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StyleConfig":
        """Create from dictionary."""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


@dataclass
class ASQLConfig:
    """Complete ASQL configuration.
    
    Example usage:
        # Load from file (auto-discovers asql.config.yaml)
        config = ASQLConfig.load()
        
        # Use a preset
        config = ASQLConfig.from_preset("sql-compat")
        
        # Custom config
        config = ASQLConfig(
            dialect="bigquery",
            style=StyleConfig(equality="single", count="function")
        )
    """
    
    # Preset name: default, sql-compat, concise
    preset: str = "default"
    
    # Target SQL dialect for compile()
    dialect: str = "snowflake"
    
    # Style configuration
    style: StyleConfig = field(default_factory=StyleConfig)
    
    @classmethod
    def load(cls, path: Optional[Path] = None) -> "ASQLConfig":
        """Load config from file or return defaults.
        
        Args:
            path: Explicit config file path. If None, searches for config file.
            
        Returns:
            ASQLConfig instance
        """
        if path is None:
            path = cls._find_config_file()
        
        if path is None or not path.exists():
            return cls()
        
        return cls._load_from_file(path)
    
    @classmethod
    def _find_config_file(cls) -> Optional[Path]:
        """Find config file in current directory or parents."""
        names = ["asql.config.yaml", "asql.config.yml", ".asqlrc.yaml"]
        
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            for name in names:
                config_path = parent / name
                if config_path.exists():
                    return config_path
        
        return None
    
    @classmethod
    def _load_from_file(cls, path: Path) -> "ASQLConfig":
        """Load config from a file."""
        try:
            import yaml
            with open(path) as f:
                data = yaml.safe_load(f)
            return cls.from_dict(data or {})
        except ImportError:
            # YAML not available, try JSON
            if path.suffix == ".json":
                with open(path) as f:
                    data = json.load(f)
                return cls.from_dict(data)
            raise ImportError("PyYAML required to load YAML config files")
    
    @classmethod
    def from_preset(cls, preset: str) -> "ASQLConfig":
        """Create config from a preset name.
        
        Available presets:
        - default: Balanced ASQL style (=, #, ??, -col)
        - sql-compat: Familiar to SQL users (=, count(*), coalesce(), col DESC)
        - concise: Maximum brevity
        
        Args:
            preset: Preset name
            
        Returns:
            ASQLConfig instance
        """
        presets = {
            "default": cls._default_preset,
            "sql-compat": cls._sql_compat_preset,
            "concise": cls._concise_preset,
        }
        
        if preset not in presets:
            raise ValueError(f"Unknown preset: {preset}. Available: {list(presets.keys())}")
        
        return presets[preset]()
    
    @classmethod
    def _default_preset(cls) -> "ASQLConfig":
        """Default ASQL style - balanced."""
        return cls(
            preset="default",
            style=StyleConfig(
                equality="single",
                count="hash",
                coalesce="operator",
                descending="prefix",
                cast="double_colon",
                quotes="double",
                sort_keyword="order_by",
            )
        )
    
    @classmethod
    def _sql_compat_preset(cls) -> "ASQLConfig":
        """SQL-compatible style - familiar to SQL users."""
        return cls(
            preset="sql-compat",
            style=StyleConfig(
                equality="single",
                count="function",
                coalesce="function",
                descending="suffix",
                cast="function",
                quotes="single",
                sort_keyword="order_by",
            )
        )
    
    @classmethod
    def _concise_preset(cls) -> "ASQLConfig":
        """Concise style - maximum brevity."""
        return cls(
            preset="concise",
            style=StyleConfig(
                equality="single",
                count="hash",
                coalesce="operator",
                descending="prefix",
                cast="double_colon",
                quotes="double",
                sort_keyword="sort",
            )
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ASQLConfig":
        """Create from dictionary (e.g., parsed YAML/JSON)."""
        preset = data.get("preset", "default")
        dialect = data.get("dialect", "snowflake")
        
        # Start with preset defaults
        config = cls.from_preset(preset)
        config.dialect = dialect
        
        # Override style options if provided
        if "style" in data and isinstance(data["style"], dict):
            for key, value in data["style"].items():
                if hasattr(config.style, key):
                    setattr(config.style, key, value)
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "preset": self.preset,
            "dialect": self.dialect,
            "style": self.style.to_dict(),
        }


# Default config instance
DEFAULT_CONFIG = ASQLConfig()
