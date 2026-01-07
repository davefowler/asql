"""Tests for the dbt-asql plugin functionality."""

import json
from pathlib import Path


from dbt_asql.plugin import (
    AsqlExtension,
    compile_project,
    clean_project,
    discover_asql_files,
    get_manifest_models,
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
        manifest_path.write_text(json.dumps(manifest))
        
        result = get_manifest_models(str(manifest_path))
        
        assert result == {"orders", "customers"}
        # Tests should not be included
        assert "test_orders" not in result


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
        (models_dir / "orders.asql").write_text("from orders")
        (models_dir / "marts").mkdir()
        (models_dir / "marts" / "revenue.asql").write_text("from orders")
        
        # Create a .sql file (should be ignored)
        (models_dir / "other.sql").write_text("SELECT 1")
        
        result = discover_asql_files(str(models_dir))
        
        assert len(result) == 2
        names = {p.name for p in result}
        assert names == {"orders.asql", "revenue.asql"}


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
        
        (models_dir / "revenue.asql").write_text(asql_content)
        
        result = compile_project(str(models_dir), verbose=False)
        
        assert len(result) == 1
        asql_path, sql_path = result[0]
        assert asql_path.name == "revenue.asql"
        assert sql_path.name == "revenue.sql"
        
        # Check the generated SQL
        sql_content = sql_path.read_text()
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
        manifest_path.write_text(json.dumps(manifest))
        
        # Create ASQL file that references the model
        (models_dir / "orders.asql").write_text("from stg_orders select *")
        
        result = compile_project(
            str(models_dir),
            manifest_path=str(manifest_path),
            verbose=False,
        )
        
        assert len(result) == 1
        sql_content = result[0][1].read_text()
        assert "ref('stg_orders')" in sql_content


class TestCleanProject:
    """Tests for project cleanup."""
    
    def test_removes_generated_sql(self, tmp_path: Path):
        """Removes .sql files that have matching .asql files."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        # Create .asql and corresponding .sql file
        (models_dir / "orders.asql").write_text("from orders")
        (models_dir / "orders.sql").write_text("SELECT * FROM orders")
        
        # Create .sql file without .asql (should NOT be removed)
        (models_dir / "other.sql").write_text("SELECT 1")
        
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


# Run with: ./venv/bin/pytest integrations/dbt-asql/tests/ -v
