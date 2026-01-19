"""Code quality and consistency tests."""

import ast
import inspect
from pathlib import Path
import pytest


def test_all_functions_have_docstrings() -> None:
    """Test that all public functions in compiler module have docstrings."""
    from asql import compiler
    
    for name, obj in inspect.getmembers(compiler):
        if inspect.isfunction(obj) and not name.startswith("_"):
            assert obj.__doc__ is not None, f"compiler.{name} missing docstring"


def test_error_classes_exist() -> None:
    """Test that all error classes are defined."""
    from asql.errors import (
        ASQLError,
        ASQLSyntaxError,
        ASQLCompilationError,
        ASQLResolutionError,
    )
    
    assert issubclass(ASQLSyntaxError, ASQLError)
    assert issubclass(ASQLCompilationError, ASQLError)
    assert issubclass(ASQLResolutionError, ASQLError)


def test_transpile_function_signature() -> None:
    """Test that transpile function has correct signature."""
    import inspect
    from asql import transpile
    
    sig = inspect.signature(transpile)
    params = list(sig.parameters.keys())
    
    assert "sql" in params
    assert "read" in params or "write" in params  # Can have either dialect param
    assert "pretty" in params
    
    # Check return type annotation if present
    if sig.return_annotation != inspect.Signature.empty:
        ret_ann = sig.return_annotation
        # Allow List[str] or list type annotations
        assert "List" in str(ret_ann) or "list" in str(ret_ann).lower()


def test_no_syntax_errors_in_code() -> None:
    """Test that all Python files have valid syntax."""
    # Path goes: tests/quality/test_code_quality.py -> tests/quality -> tests -> repo root -> asql/
    asql_dir = Path(__file__).parent.parent.parent / "asql"
    
    for py_file in asql_dir.glob("**/*.py"):
        if "__pycache__" in str(py_file):
            continue
        
        with open(py_file, "r") as f:
            code = f.read()
        
        try:
            ast.parse(code)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {py_file}: {e}")


def test_imports_work() -> None:
    """Test that all imports work correctly."""
    from tests.fixtures import transpile, parse_one
    from asql.errors import ASQLSyntaxError, ASQLCompilationError
    from asql.dialect import ASQL
    
    # Test that imports don't raise errors
    assert transpile is not None
    assert parse_one is not None
    assert ASQLSyntaxError is not None
    assert ASQLCompilationError is not None
    assert ASQL is not None
