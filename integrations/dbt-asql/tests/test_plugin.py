"""Tests for the dbt-asql plugin functionality."""

import json
import os
from pathlib import Path

import pytest

from dbt_asql.plugin import (
    AsqlCompilationError,
    AsqlExtension,
    InvalidDialectError,
    VALID_DIALECTS,
    compile_project,
    clean_project,
    discover_asql_files,
    get_manifest_models,
    validate_dialect,
    _get_jinja_dialect,
)


class TestGetManifestModels:
    """Tests for manifest model loading."""
    
    def test_missing_manifest(self):
        """Returns empty set when manifest doesn't exist."""
        result = get_manifest_models("/nonexistent/manifest.json")
        assert result == set()
    
    def test_valid_manifest(self, tmp_path: Path):
        """Extracts model names from manifest."""
        manifest = {
            "nodes": {
                "model.project.orders": {
                    "resource_type": "model",
                    "name": "orders",
                },
                "model.project.customers": {
                    "resource_type": "model",
                    "name": "customers",
                },
                "test.project.test_orders": {
                    "resource_type": "test",
                    "name": "test_orders",
                },
            }
        }
        
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        
        result = get_manifest_models(str(manifest_path))
        
        assert result == {"orders", "customers"}
        # Tests should not be included
        assert "test_orders" not in result
    
    def test_malformed_manifest(self, tmp_path: Path):
        """Returns empty set for malformed manifest."""
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text("not valid json", encoding="utf-8")
        
        # Should handle JSON errors gracefully
        with pytest.raises(json.JSONDecodeError):
            get_manifest_models(str(manifest_path))
    
    def test_manifest_missing_nodes(self, tmp_path: Path):
        """Returns empty set when manifest has no nodes."""
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text('{"metadata": {}}', encoding="utf-8")
        
        result = get_manifest_models(str(manifest_path))
        assert result == set()


class TestDiscoverAsqlFiles:
    """Tests for ASQL file discovery."""
    
    def test_missing_directory(self):
        """Returns empty list for missing directory."""
        result = discover_asql_files("/nonexistent/models")
        assert result == []
    
    def test_finds_asql_files(self, tmp_path: Path):
        """Finds .asql files in directory tree."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        # Create some .asql files
        (models_dir / "orders.asql").write_text("from orders", encoding="utf-8")
        (models_dir / "marts").mkdir()
        (models_dir / "marts" / "revenue.asql").write_text("from orders", encoding="utf-8")
        
        # Create a .sql file (should be ignored)
        (models_dir / "other.sql").write_text("SELECT 1", encoding="utf-8")
        
        result = discover_asql_files(str(models_dir))
        
        assert len(result) == 2
        names = {p.name for p in result}
        assert names == {"orders.asql", "revenue.asql"}


class TestValidateDialect:
    """Tests for dialect validation."""
    
    def test_valid_dialects(self):
        """All valid dialects should pass."""
        for dialect in ["postgres", "snowflake", "bigquery", "mysql"]:
            validate_dialect(dialect)  # Should not raise
    
    def test_invalid_dialect(self):
        """Invalid dialect should raise."""
        with pytest.raises(InvalidDialectError) as exc_info:
            validate_dialect("invalid_dialect")
        
        assert "invalid_dialect" in str(exc_info.value)
        assert "postgres" in str(exc_info.value)  # Shows valid options
    
    def test_valid_dialects_set(self):
        """VALID_DIALECTS should contain expected dialects."""
        assert "postgres" in VALID_DIALECTS
        assert "snowflake" in VALID_DIALECTS
        assert "bigquery" in VALID_DIALECTS


class TestCompileProject:
    """Tests for project compilation."""
    
    def test_no_asql_files(self, tmp_path: Path):
        """Returns empty list when no .asql files."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        result = compile_project(str(models_dir), verbose=False)
        
        assert result == []
    
    def test_compiles_asql_to_sql(self, tmp_path: Path):
        """Compiles .asql files to .sql files."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        asql_content = """SET materialized = table;

from orders
  select id, amount"""
        
        (models_dir / "revenue.asql").write_text(asql_content, encoding="utf-8")
        
        result = compile_project(str(models_dir), verbose=False)
        
        assert len(result) == 1
        asql_path, sql_path = result[0]
        assert asql_path.name == "revenue.asql"
        assert sql_path.name == "revenue.sql"
        
        # Check the generated SQL
        sql_content = sql_path.read_text(encoding="utf-8")
        assert "config(materialized='table')" in sql_content
        assert "SELECT" in sql_content
    
    def test_resolves_refs_from_manifest(self, tmp_path: Path):
        """Uses manifest to resolve model references."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        # Create manifest
        manifest = {
            "nodes": {
                "model.project.stg_orders": {
                    "resource_type": "model",
                    "name": "stg_orders",
                }
            }
        }
        manifest_path = tmp_path / "target" / "manifest.json"
        manifest_path.parent.mkdir()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        
        # Create ASQL file that references the model
        (models_dir / "orders.asql").write_text("from stg_orders select *", encoding="utf-8")
        
        result = compile_project(
            str(models_dir),
            manifest_path=str(manifest_path),
            verbose=False,
        )
        
        assert len(result) == 1
        sql_content = result[0][1].read_text(encoding="utf-8")
        assert "ref('stg_orders')" in sql_content
    
    def test_invalid_dialect_raises(self, tmp_path: Path):
        """Invalid dialect raises InvalidDialectError."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "test.asql").write_text("from orders", encoding="utf-8")
        
        with pytest.raises(InvalidDialectError):
            compile_project(str(models_dir), dialect="invalid", verbose=False)
    
    def test_compilation_error_includes_file_path(self, tmp_path: Path):
        """Compilation error includes which file failed."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        # Create file with invalid ASQL syntax
        (models_dir / "bad.asql").write_text("INVALID SYNTAX @@@@", encoding="utf-8")
        
        with pytest.raises(AsqlCompilationError) as exc_info:
            compile_project(str(models_dir), verbose=False)
        
        # Error should mention the file
        assert "bad.asql" in str(exc_info.value)
    
    def test_utf8_encoding(self, tmp_path: Path):
        """Handles UTF-8 characters correctly."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        # File with UTF-8 characters
        asql_content = """-- Comment with émojis: 🎉
from orders
  where name = 'Müller'"""
        
        (models_dir / "utf8.asql").write_text(asql_content, encoding="utf-8")
        
        result = compile_project(str(models_dir), verbose=False)
        
        assert len(result) == 1
        sql_content = result[0][1].read_text(encoding="utf-8")
        assert "Müller" in sql_content


class TestCleanProject:
    """Tests for project cleanup."""
    
    def test_removes_generated_sql(self, tmp_path: Path):
        """Removes .sql files that have matching .asql files."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        # Create .asql and corresponding .sql file
        (models_dir / "orders.asql").write_text("from orders", encoding="utf-8")
        (models_dir / "orders.sql").write_text("SELECT * FROM orders", encoding="utf-8")
        
        # Create .sql file without .asql (should NOT be removed)
        (models_dir / "other.sql").write_text("SELECT 1", encoding="utf-8")
        
        result = clean_project(str(models_dir), verbose=False)
        
        assert len(result) == 1
        assert result[0].name == "orders.sql"
        
        # Verify other.sql still exists
        assert (models_dir / "other.sql").exists()
        assert not (models_dir / "orders.sql").exists()


class TestAsqlExtension:
    """Tests for the Jinja extension."""
    
    def test_extension_tags(self):
        """Extension registers correct tags."""
        assert AsqlExtension.tags == {"asql"}
    
    def test_compile_asql(self):
        """Extension compiles ASQL to SQL."""
        ext = AsqlExtension(environment=None)
        
        def caller():
            return "from orders select id, amount"
        
        result = ext._compile_asql([], caller)
        
        assert "SELECT" in result
        assert "FROM orders" in result
        # Original ASQL should be in comments
        assert "from orders" in result


class TestGetJinjaDialect:
    """Tests for Jinja dialect configuration."""
    
    def test_default_dialect(self):
        """Default dialect is postgres."""
        # Temporarily remove env var if set
        old_value = os.environ.pop("DBT_ASQL_DIALECT", None)
        try:
            assert _get_jinja_dialect() == "postgres"
        finally:
            if old_value is not None:
                os.environ["DBT_ASQL_DIALECT"] = old_value
    
    def test_custom_dialect_from_env(self):
        """Reads dialect from environment variable."""
        old_value = os.environ.get("DBT_ASQL_DIALECT")
        try:
            os.environ["DBT_ASQL_DIALECT"] = "snowflake"
            assert _get_jinja_dialect() == "snowflake"
        finally:
            if old_value is not None:
                os.environ["DBT_ASQL_DIALECT"] = old_value
            else:
                os.environ.pop("DBT_ASQL_DIALECT", None)
    
    def test_invalid_dialect_falls_back(self):
        """Invalid dialect falls back to postgres."""
        old_value = os.environ.get("DBT_ASQL_DIALECT")
        try:
            os.environ["DBT_ASQL_DIALECT"] = "invalid_dialect"
            assert _get_jinja_dialect() == "postgres"
        finally:
            if old_value is not None:
                os.environ["DBT_ASQL_DIALECT"] = old_value
            else:
                os.environ.pop("DBT_ASQL_DIALECT", None)


# Run with: ./venv/bin/pytest integrations/dbt-asql/tests/ -v
