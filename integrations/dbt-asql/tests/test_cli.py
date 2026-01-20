"""Tests for the dbt-asql CLI."""

import subprocess
import sys
from pathlib import Path


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
        assert "dbt-asql" in result.stdout
    
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
    
    def test_compile_shows_dialect_choices(self):
        """compile --help shows valid dialect choices."""
        result = subprocess.run(
            [sys.executable, "-m", "dbt_asql.cli", "compile", "--help"],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        # Should list valid dialects
        assert "postgres" in result.stdout
        assert "snowflake" in result.stdout
    
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
        asql_file.write_text("from orders select id, amount", encoding="utf-8")
        
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
        
        sql_content = sql_file.read_text(encoding="utf-8")
        assert "SELECT" in sql_content
    
    def test_compile_with_dialect(self, tmp_path: Path):
        """compile with --dialect option works."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        asql_file = models_dir / "orders.asql"
        asql_file.write_text("from orders select id", encoding="utf-8")
        
        result = subprocess.run(
            [
                sys.executable, "-m", "dbt_asql.cli",
                "compile",
                "--models-dir", str(models_dir),
                "--dialect", "snowflake",
            ],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
    
    def test_clean_removes_sql(self, tmp_path: Path):
        """clean removes generated .sql files."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        # Create .asql and .sql pair
        (models_dir / "orders.asql").write_text("from orders", encoding="utf-8")
        (models_dir / "orders.sql").write_text("SELECT * FROM orders", encoding="utf-8")
        
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
        # Output should be empty in quiet mode
        assert result.stdout.strip() == ""
    
    def test_compilation_error_returns_nonzero(self, tmp_path: Path):
        """Compilation error returns non-zero exit code."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        # Create file with invalid ASQL
        (models_dir / "bad.asql").write_text("INVALID @@@@", encoding="utf-8")
        
        result = subprocess.run(
            [
                sys.executable, "-m", "dbt_asql.cli",
                "compile",
                "--models-dir", str(models_dir),
            ],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode != 0
        assert "Error" in result.stderr or "error" in result.stderr.lower()


# Run with: ./venv/bin/pytest integrations/dbt-asql/tests/ -v
