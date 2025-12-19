"""ASQL Schema System.

This module provides schema support for ASQL:
1. Column/Table metadata from databases or config files
2. Relationship mapping (explicit from config, inferred from conventions)
3. Schema loading from dbt schema.yml and asql_schema.yml

The schema enables smart join inference when only table names are provided.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import inflect

# Inflect engine for pluralization/singularization
_inflect_engine = inflect.engine()


@lru_cache(maxsize=1000)
def pluralize(word: str) -> str:
    """Get the plural form of a word using inflect library."""
    result = _inflect_engine.plural(word)
    return result if result else word + "s"


@lru_cache(maxsize=1000)
def singularize(word: str) -> str:
    """Get the singular form of a word using inflect library."""
    result = _inflect_engine.singular_noun(word)
    # singular_noun returns False if word is not a plural
    return result if result else word


def get_table_name_variants(name: str) -> List[str]:
    """Get all possible table name variants (singular, plural, original).
    
    Returns variants in order of preference for matching.
    """
    name_lower = name.lower()
    variants = [name_lower]
    
    # Add plural form
    plural = pluralize(name_lower)
    if plural != name_lower:
        variants.append(plural)
    
    # Add singular form
    singular = singularize(name_lower)
    if singular and singular != name_lower and singular not in variants:
        variants.append(singular)
    
    return variants


@dataclass
class Column:
    """Represents a table column."""
    
    name: str
    type: Optional[str] = None
    primary_key: bool = False
    
    def __post_init__(self) -> None:
        # Normalize column name to lowercase for case-insensitive matching
        self.name = self.name.lower()


@dataclass
class Table:
    """Represents a database table with its columns."""
    
    name: str
    columns: Dict[str, Column] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        # Normalize table name to lowercase for case-insensitive matching
        self.name = self.name.lower()
    
    def has_column(self, name: str) -> bool:
        """Check if table has a column (case-insensitive)."""
        return name.lower() in self.columns
    
    def get_column(self, name: str) -> Optional[Column]:
        """Get a column by name (case-insensitive)."""
        return self.columns.get(name.lower())
    
    def add_column(self, column: Column) -> None:
        """Add a column to the table."""
        self.columns[column.name.lower()] = column
    
    @classmethod
    def from_column_list(cls, name: str, columns: List[str]) -> "Table":
        """Create a table from a list of column names."""
        table = cls(name=name)
        for col_name in columns:
            # Mark 'id' as primary key by convention
            is_pk = col_name.lower() == "id"
            table.add_column(Column(name=col_name, primary_key=is_pk))
        return table
    
    def get_primary_key(self) -> Optional[str]:
        """Get the primary key column name for this table.
        
        Checks in order:
        1. Columns explicitly marked as primary_key=True
        2. Convention: 'id'
        3. Convention: 'pk'
        4. Convention: '{singular_table_name}_id' (e.g., users.user_id)
        
        Returns:
            The primary key column name, or None if not found
        """
        # 1. Check for explicitly marked primary key
        for col in self.columns.values():
            if col.primary_key:
                return col.name
        
        # 2. Check for 'id' convention
        if self.has_column("id"):
            return "id"
        
        # 3. Check for 'pk' convention
        if self.has_column("pk"):
            return "pk"
        
        # 4. Check for '{singular}_id' convention (e.g., users.user_id)
        singular = singularize(self.name)
        singular_id = f"{singular}_id"
        if self.has_column(singular_id):
            return singular_id
        
        return None


@dataclass
class Relationship:
    """Represents a foreign key relationship between tables.
    
    Attributes:
        from_table: Source table name (e.g., "orders")
        from_column: Source column name (e.g., "user_id")
        to_table: Target table name (e.g., "users")
        to_column: Target column name (e.g., "id")
        alias: Optional alias for FK traversal (e.g., "user" enables .user.)
        source: Whether relationship is explicit (from config) or inferred (from naming)
    """
    
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    alias: Optional[str] = None
    source: Literal["explicit", "inferred"] = "inferred"
    
    def __post_init__(self) -> None:
        # Normalize all names to lowercase
        self.from_table = self.from_table.lower()
        self.from_column = self.from_column.lower()
        self.to_table = self.to_table.lower()
        self.to_column = self.to_column.lower()
        if self.alias:
            self.alias = self.alias.lower()
    
    def matches(self, from_table: str, to_table: str) -> bool:
        """Check if this relationship connects the given tables."""
        return (
            self.from_table == from_table.lower() and 
            self.to_table == to_table.lower()
        )
    
    def get_join_condition(self) -> str:
        """Generate the ON clause for this relationship."""
        return f"{self.from_table}.{self.from_column} = {self.to_table}.{self.to_column}"


@dataclass
class Schema:
    """Complete schema with tables and relationships.
    
    The schema has two layers:
    1. Tables: Raw column metadata from DB, dbt, or config files
    2. Relationships: Both explicit (from config) and inferred (from naming conventions)
    
    Usage:
        # Load from dbt
        schema = Schema.from_dbt("path/to/dbt/models")
        
        # Load from ASQL config
        schema = Schema.from_yaml("asql_schema.yml")
        
        # Find relationship for join inference
        rel = schema.find_relationship("orders", "users")
        if rel:
            on_clause = rel.get_join_condition()
    """
    
    tables: Dict[str, Table] = field(default_factory=dict)
    relationships: List[Relationship] = field(default_factory=list)
    
    def add_table(self, table: Table) -> None:
        """Add a table to the schema."""
        self.tables[table.name.lower()] = table
    
    def get_table(self, name: str) -> Optional[Table]:
        """Get a table by name (case-insensitive)."""
        return self.tables.get(name.lower())
    
    def has_table(self, name: str) -> bool:
        """Check if schema has a table (case-insensitive)."""
        return name.lower() in self.tables
    
    def add_relationship(self, rel: Relationship) -> None:
        """Add a relationship to the schema."""
        self.relationships.append(rel)
    
    def find_relationship(
        self, 
        from_table: str, 
        to_table: str
    ) -> Optional[Relationship]:
        """Find a relationship between two tables.
        
        Explicit relationships take precedence over inferred ones.
        
        Args:
            from_table: Source table name
            to_table: Target table name
            
        Returns:
            The matching Relationship, or None if not found
        """
        from_table_lower = from_table.lower()
        to_table_lower = to_table.lower()
        
        # First, look for explicit relationships
        for rel in self.relationships:
            if rel.matches(from_table_lower, to_table_lower) and rel.source == "explicit":
                return rel
        
        # Then, look for inferred relationships
        for rel in self.relationships:
            if rel.matches(from_table_lower, to_table_lower) and rel.source == "inferred":
                return rel
        
        return None
    
    def find_all_relationships(
        self, 
        from_table: str, 
        to_table: str
    ) -> List[Relationship]:
        """Find all relationships between two tables.
        
        Returns explicit relationships first, then inferred.
        """
        from_table_lower = from_table.lower()
        to_table_lower = to_table.lower()
        
        explicit = []
        inferred = []
        
        for rel in self.relationships:
            if rel.matches(from_table_lower, to_table_lower):
                if rel.source == "explicit":
                    explicit.append(rel)
                else:
                    inferred.append(rel)
        
        return explicit + inferred
    
    def infer_relationships(self) -> None:
        """Infer relationships from column naming conventions.
        
        Scans all tables for columns ending in '_id' and attempts to find
        a corresponding target table using multiple strategies.
        
        Supported patterns:
        - user_id -> users.id (alias: user)
        - users_id -> users.id (alias: users) - plural form
        - customer_id -> customers.id (alias: customer)
        - owner_user_id -> users.id (alias: owner) - named relationship
        - created_by_user_id -> users.id (alias: created_by) - multi-underscore alias
        
        The algorithm progressively splits the column name to find a matching table,
        supporting both simple FKs and named/aliased relationships.
        """
        for table_name, table in self.tables.items():
            for col_name, column in table.columns.items():
                # Only process columns ending in _id
                if not col_name.endswith("_id"):
                    continue
                
                # Remove the _id suffix
                base_name = col_name[:-3]  # e.g., "user" from "user_id", "owner_user" from "owner_user_id"
                
                if not base_name:
                    continue
                
                # Try to find a matching table and determine alias
                result = self._find_fk_target(base_name)
                if not result:
                    continue
                
                target_table, alias = result
                
                # Get the primary key of the target table
                target = self.get_table(target_table)
                if not target:
                    continue
                
                pk_col = target.get_primary_key()
                if not pk_col:
                    continue
                
                # Check if this relationship already exists
                existing = self.find_relationship(table_name, target_table)
                if existing and existing.from_column == col_name:
                    continue  # Already have this relationship
                
                # Create inferred relationship
                rel = Relationship(
                    from_table=table_name,
                    from_column=col_name,
                    to_table=target_table,
                    to_column=pk_col,
                    alias=alias,
                    source="inferred"
                )
                self.add_relationship(rel)
    
    def _find_fk_target(self, base_name: str) -> Optional[Tuple[str, str]]:
        """Find the target table for a FK column base name.
        
        Uses progressive splitting to handle multi-underscore patterns like:
        - "user" -> users table, alias "user"
        - "users" -> users table, alias "users"
        - "owner_user" -> first try "owner_user(s)" table, then "user(s)" with alias "owner"
        - "created_by_user" -> try progressively: "created_by_user(s)", "by_user(s)", "user(s)"
        
        Args:
            base_name: The column name without the _id suffix (e.g., "user", "owner_user")
            
        Returns:
            Tuple of (target_table_name, alias) or None if no match found
        """
        # Try the full base_name first (including all underscores)
        target = self._find_table_by_name(base_name)
        if target:
            return (target, base_name)
        
        # Progressive split: try removing underscore segments from the left
        # For "owner_user", try: "owner_user", then "user" with alias "owner"
        # For "created_by_user", try: "created_by_user", "by_user", "user"
        parts = base_name.split("_")
        
        for i in range(1, len(parts)):
            # Alias is everything before the split point
            alias = "_".join(parts[:i])
            # Table candidate is everything after
            table_candidate = "_".join(parts[i:])
            
            target = self._find_table_by_name(table_candidate)
            if target:
                return (target, alias)
        
        return None
    
    def _find_table_by_name(self, name: str) -> Optional[str]:
        """Find a table by name, trying multiple variants.
        
        Tries:
        1. Exact match (case-insensitive)
        2. Plural form (using inflect)
        3. Singular form (using inflect)
        
        Args:
            name: The table name to search for
            
        Returns:
            The actual table name if found, or None
        """
        name_lower = name.lower()
        
        # 1. Try exact match
        if self.has_table(name_lower):
            return name_lower
        
        # 2. Try plural form
        plural = pluralize(name_lower)
        if plural != name_lower and self.has_table(plural):
            return plural
        
        # 3. Try singular form (in case input was plural)
        singular = singularize(name_lower)
        if singular and singular != name_lower and self.has_table(singular):
            return singular
        
        return None
    
    @classmethod
    def from_yaml(cls, path: str | Path, infer_relationships: bool = True) -> "Schema":
        """Load schema from asql_schema.yml format.
        
        Expected format:
        ```yaml
        tables:
          orders:
            columns: [id, user_id, amount, created_at]
          users:
            columns: [id, name, email]
            
        relationships:
          - from: orders.user_id
            to: users.id
            alias: user
        ```
        
        Args:
            path: Path to the YAML file
            
        Returns:
            Schema instance with tables and relationships
        """
        import yaml
        
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Schema file not found: {path}")
        
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        
        schema = cls()
        
        # Load tables
        tables_data = data.get("tables", {})
        for table_name, table_info in tables_data.items():
            if isinstance(table_info, dict):
                columns = table_info.get("columns", [])
            elif isinstance(table_info, list):
                columns = table_info
            else:
                columns = []
            
            table = Table.from_column_list(table_name, columns)
            schema.add_table(table)
        
        # Load explicit relationships
        rels_data = data.get("relationships", [])
        for rel_info in rels_data:
            from_ref = rel_info.get("from", "")
            to_ref = rel_info.get("to", "")
            alias = rel_info.get("alias")
            
            # Parse "table.column" format
            if "." in from_ref and "." in to_ref:
                from_table, from_col = from_ref.rsplit(".", 1)
                to_table, to_col = to_ref.rsplit(".", 1)
                
                rel = Relationship(
                    from_table=from_table,
                    from_column=from_col,
                    to_table=to_table,
                    to_column=to_col,
                    alias=alias,
                    source="explicit"
                )
                schema.add_relationship(rel)
        
        # Infer additional relationships from naming conventions
        if infer_relationships:
            schema.infer_relationships()
        
        return schema
    
    @classmethod
    def from_dbt(cls, path: str | Path, infer_relationships: bool = True) -> "Schema":
        """Load schema from dbt project.
        
        Supports multiple dbt artifacts (in order of preference):
        1. manifest.json - Best source, contains all refs and compiled metadata
        2. schema.yml / _models.yml files - Relationship tests and column info
        
        Expected YAML format:
        ```yaml
        models:
          - name: orders
            columns:
              - name: user_id
                tests:
                  - relationships:
                      to: ref('users')
                      field: id
        ```
        
        Args:
            path: Path to dbt project, target/ directory, or models/ directory
            
        Returns:
            Schema instance with tables and relationships
        """
        import yaml
        
        path = Path(path)
        
        # Try manifest.json first (best source for relationships)
        manifest_path = None
        if (path / "target" / "manifest.json").exists():
            manifest_path = path / "target" / "manifest.json"
        elif (path / "manifest.json").exists():
            manifest_path = path / "manifest.json"
        
        if manifest_path:
            return cls._from_dbt_manifest(manifest_path, infer_relationships=infer_relationships)
        
        # Find all schema.yml files
        if path.is_file():
            schema_files = [path]
        else:
            # Search for schema.yml, schema.yaml, and _schema.yml files
            schema_files = list(path.glob("**/schema.yml"))
            schema_files.extend(path.glob("**/schema.yaml"))
            schema_files.extend(path.glob("**/*_schema.yml"))
            schema_files.extend(path.glob("**/*_schema.yaml"))
        
        schema = cls()
        
        for schema_file in schema_files:
            with open(schema_file) as f:
                data = yaml.safe_load(f) or {}
            
            # Process models (dbt uses "models" key)
            models = data.get("models", [])
            for model in models:
                if not isinstance(model, dict):
                    continue
                
                model_name = model.get("name", "")
                if not model_name:
                    continue
                
                # Extract columns
                table = Table(name=model_name)
                columns = model.get("columns", [])
                
                for col_info in columns:
                    if isinstance(col_info, str):
                        col_name = col_info
                        col_type = None
                        is_pk = col_name.lower() == "id"
                        tests = []
                    elif isinstance(col_info, dict):
                        col_name = col_info.get("name", "")
                        col_type = col_info.get("data_type")
                        is_pk = col_info.get("primary_key", col_name.lower() == "id")
                        tests = col_info.get("tests", [])
                    else:
                        continue
                    
                    if not col_name:
                        continue
                    
                    table.add_column(Column(
                        name=col_name,
                        type=col_type,
                        primary_key=is_pk
                    ))
                    
                    # Extract relationships from tests
                    for test in tests:
                        if isinstance(test, dict) and "relationships" in test:
                            rel_info = test["relationships"]
                            to_ref = rel_info.get("to", "")
                            to_field = rel_info.get("field", "id")
                            
                            # Parse ref('table_name') format
                            ref_match = re.search(r"ref\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", to_ref)
                            if ref_match:
                                to_table = ref_match.group(1)
                            else:
                                # Try using the value directly
                                to_table = to_ref.strip("'\"")
                            
                            if to_table:
                                # Derive alias from column name
                                # user_id -> user, owner_user_id -> owner
                                alias = None
                                col_lower = col_name.lower()
                                if col_lower.endswith("_id"):
                                    alias = col_lower[:-3]  # Remove _id
                                
                                rel = Relationship(
                                    from_table=model_name,
                                    from_column=col_name,
                                    to_table=to_table,
                                    to_column=to_field,
                                    alias=alias,
                                    source="explicit"
                                )
                                schema.add_relationship(rel)
                
                schema.add_table(table)
            
            # Also check for "sources" (dbt sources format)
            sources = data.get("sources", [])
            for source in sources:
                if not isinstance(source, dict):
                    continue
                
                source_tables = source.get("tables", [])
                for table_info in source_tables:
                    if isinstance(table_info, dict):
                        table_name = table_info.get("name", "")
                        if table_name:
                            columns = table_info.get("columns", [])
                            table = Table(name=table_name)
                            for col in columns:
                                if isinstance(col, dict):
                                    col_name = col.get("name", "")
                                    if col_name:
                                        table.add_column(Column(name=col_name))
                                elif isinstance(col, str):
                                    table.add_column(Column(name=col))
                            schema.add_table(table)
        
        # Infer additional relationships from naming conventions
        if infer_relationships:
            schema.infer_relationships()
        
        return schema
    
    @classmethod
    def _from_dbt_manifest(cls, manifest_path: Path, infer_relationships: bool = True) -> "Schema":
        """Load schema from dbt manifest.json.
        
        The manifest.json is the best source for relationships because:
        1. It's always generated when dbt runs
        2. It contains all parsed refs (model dependencies)
        3. It has column metadata and relationship tests
        
        Args:
            manifest_path: Path to manifest.json
            
        Returns:
            Schema instance with tables and relationships
        """
        import json
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        schema = cls()
        
        # Extract nodes (models, sources, seeds)
        nodes = manifest.get("nodes", {})
        sources = manifest.get("sources", {})
        
        # Process models
        for node_id, node in nodes.items():
            if node.get("resource_type") not in ("model", "seed"):
                continue
            
            model_name = node.get("name", "")
            if not model_name:
                continue
            
            table = Table(name=model_name)
            
            # Extract columns
            columns = node.get("columns", {})
            for col_name, col_info in columns.items():
                is_pk = col_name.lower() == "id"
                col_type = col_info.get("data_type") if isinstance(col_info, dict) else None
                table.add_column(Column(name=col_name, type=col_type, primary_key=is_pk))
            
            schema.add_table(table)
            
            # Extract relationships from depends_on.nodes (refs)
            depends_on = node.get("depends_on", {})
            ref_nodes = depends_on.get("nodes", [])
            
            for ref_id in ref_nodes:
                # ref_id format: "model.project.table_name" or "source.project.source.table"
                parts = ref_id.split(".")
                if len(parts) >= 3 and parts[0] == "model":
                    to_table = parts[-1]
                    
                    # Try to find the FK column in this model
                    # Look for {to_table_singular}_id pattern
                    to_singular = to_table.rstrip('s') if to_table.endswith('s') else to_table
                    fk_col = f"{to_singular}_id"
                    
                    if table.has_column(fk_col):
                        rel = Relationship(
                            from_table=model_name,
                            from_column=fk_col,
                            to_table=to_table,
                            to_column="id",
                            alias=to_singular,
                            source="explicit"  # From dbt refs
                        )
                        schema.add_relationship(rel)
        
        # Process sources
        for source_id, source_node in sources.items():
            source_name = source_node.get("name", "")
            if source_name:
                table = Table(name=source_name)
                columns = source_node.get("columns", {})
                for col_name, col_info in columns.items():
                    col_type = col_info.get("data_type") if isinstance(col_info, dict) else None
                    table.add_column(Column(name=col_name, type=col_type))
                schema.add_table(table)
        
        # Also check for relationship tests in the manifest
        # These are in the "nodes" with resource_type="test"
        for node_id, node in nodes.items():
            if node.get("resource_type") != "test":
                continue
            
            test_metadata = node.get("test_metadata", {})
            if test_metadata.get("name") != "relationships":
                continue
            
            # Extract relationship test info
            kwargs = test_metadata.get("kwargs", {})
            to_ref = kwargs.get("to", "")
            to_field = kwargs.get("field", "id")
            column_name = kwargs.get("column_name", "")
            
            # Get the model this test is on
            depends_on = node.get("depends_on", {})
            ref_nodes = depends_on.get("nodes", [])
            
            from_model = None
            to_model = None
            
            for ref_id in ref_nodes:
                parts = ref_id.split(".")
                if len(parts) >= 3:
                    model_name = parts[-1]
                    # Parse ref('model') from to field
                    if f"ref('{model_name}')" in to_ref or f'ref("{model_name}")' in to_ref:
                        to_model = model_name
                    else:
                        from_model = model_name
            
            if from_model and to_model and column_name:
                alias = column_name[:-3] if column_name.lower().endswith("_id") else None
                rel = Relationship(
                    from_table=from_model,
                    from_column=column_name,
                    to_table=to_model,
                    to_column=to_field,
                    alias=alias,
                    source="explicit"
                )
                schema.add_relationship(rel)
        
        # Infer additional relationships from naming conventions
        if infer_relationships:
            schema.infer_relationships()
        
        return schema
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Schema":
        """Create schema from a dictionary.
        
        Useful for programmatic schema definition.
        
        Args:
            data: Dictionary with 'tables' and 'relationships' keys
            
        Returns:
            Schema instance
        """
        schema = cls()
        
        # Load tables
        for table_name, table_info in data.get("tables", {}).items():
            if isinstance(table_info, dict):
                columns = table_info.get("columns", [])
            elif isinstance(table_info, list):
                columns = table_info
            else:
                columns = []
            
            table = Table.from_column_list(table_name, columns)
            schema.add_table(table)
        
        # Load relationships
        for rel_info in data.get("relationships", []):
            rel = Relationship(
                from_table=rel_info["from_table"],
                from_column=rel_info["from_column"],
                to_table=rel_info["to_table"],
                to_column=rel_info.get("to_column", "id"),
                alias=rel_info.get("alias"),
                source=rel_info.get("source", "explicit")
            )
            schema.add_relationship(rel)
        
        return schema
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert schema to dictionary for serialization."""
        return {
            "tables": {
                name: {
                    "columns": [
                        {
                            "name": col.name,
                            "type": col.type,
                            "primary_key": col.primary_key
                        }
                        for col in table.columns.values()
                    ]
                }
                for name, table in self.tables.items()
            },
            "relationships": [
                {
                    "from_table": rel.from_table,
                    "from_column": rel.from_column,
                    "to_table": rel.to_table,
                    "to_column": rel.to_column,
                    "alias": rel.alias,
                    "source": rel.source
                }
                for rel in self.relationships
            ]
        }
