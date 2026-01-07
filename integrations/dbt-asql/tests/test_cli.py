"""Tests for the dbt-asql CLI."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


class TestCLI:
    """Tests for CLI commands."""
    
    def test_help(self):
        """--help shows usage information."""
        result = subprocess.run(
            [sys.executable, "-m", "dbt_asql.cli", "--help"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert "dbt-asql" in result.stdout or "usage" in result.stdout.lower()
    
    def test_compile_help(self):
        """compile --help shows command options."""
        result = subprocess.run(
            [sys.executable, "-m", "dbt_asql.cli", "compile", "--help"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert "--models-dir" in result.stdout
        assert "--dialect" in result.stdout
    
    def test_compile_no_files(self, tmp_path: Path):
        """compile with no .asql files reports 0 compiled."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        result = subprocess.run(
            [
                sys.executable, "-m", "dbt_asql.cli",
                "compile",
                "--models-dir", str(models_dir),
            ],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert "0 file" in result.stdout or "No .asql" in result.stdout
    
    def test_compile_creates_sql(self, tmp_path: Path):
        """compile creates .sql files from .asql files."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        asql_file = models_dir / "orders.asql"
        asql_file.write_text("from orders select id, amount")
        
        result = subprocess.run(
            [
                sys.executable, "-m", "dbt_asql.cli",
                "compile",
                "--models-dir", str(models_dir),
            ],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        
        sql_file = models_dir / "orders.sql"
        assert sql_file.exists()
        
        sql_content = sql_file.read_text()
        assert "SELECT" in sql_content
    
    def test_clean_removes_sql(self, tmp_path: Path):
        """clean removes generated .sql files."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        # Create .asql and .sql pair
        (models_dir / "orders.asql").write_text("from orders")
        (models_dir / "orders.sql").write_text("SELECT * FROM orders")
        
        result = subprocess.run(
            [
                sys.executable, "-m", "dbt_asql.cli",
                "clean",
                "--models-dir", str(models_dir),
            ],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert not (models_dir / "orders.sql").exists()
        # Original .asql should still exist
        assert (models_dir / "orders.asql").exists()
    
    def test_quiet_mode(self, tmp_path: Path):
        """--quiet suppresses output."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        result = subprocess.run(
            [
                sys.executable, "-m", "dbt_asql.cli",
                "compile",
                "--models-dir", str(models_dir),
                "--quiet",
            ],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        # Output should be minimal in quiet mode
        assert len(result.stdout.strip()) < 50


# Run with: ./venv/bin/pytest integrations/dbt-asql/tests/ -v
