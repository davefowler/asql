"""Code quality and consistency tests."""

import ast
import inspect
from pathlib import Path
from typing import get_type_hints
import pytest


def test_all_functions_have_docstrings() -> None:
    """Test that all public functions have docstrings."""
    from asql import preparser, compiler, errors
    
    modules = [preparser, compiler]
    
    for module in modules:
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and not name.startswith("_"):
                assert obj.__doc__ is not None, f"{module.__name__}.{name} missing docstring"


def test_preparser_class_methods_have_docstrings() -> None:
    """Test that preparser class methods have docstrings."""
    from asql.preparser import ASQLPreParser
    
    for name, method in inspect.getmembers(ASQLPreParser, predicate=inspect.isfunction):
        if not name.startswith("__"):
            assert method.__doc__ is not None, f"ASQLPreParser.{name} missing docstring"


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


def test_compile_function_signature() -> None:
    """Test that compile function has correct signature."""
    from asql import compile
    import inspect
    
    sig = inspect.signature(compile)
    params = list(sig.parameters.keys())
    
    assert "asql_query" in params
    assert "dialect" in params
    assert "pretty" in params
    
    # Check return type annotation if present
    if sig.return_annotation != inspect.Signature.empty:
        assert sig.return_annotation == str


def test_preparser_initialization() -> None:
    """Test that preparser initializes correctly."""
    from asql.preparser import ASQLPreParser
    
    preparser = ASQLPreParser("from users")
    assert preparser.text == "from users"


def test_no_syntax_errors_in_code() -> None:
    """Test that all Python files have valid syntax."""
    asql_dir = Path(__file__).parent.parent / "asql"
    
    for py_file in asql_dir.glob("*.py"):
        if py_file.name == "__pycache__":
            continue
        
        with open(py_file, "r") as f:
            code = f.read()
        
        try:
            ast.parse(code)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {py_file}: {e}")


def test_imports_work() -> None:
    """Test that all imports work correctly."""
    from asql import compile
    from asql.preparser import ASQLPreParser
    from asql.compiler import compile as compile_func
    from asql.errors import ASQLSyntaxError, ASQLCompilationError
    from asql.dialect import ASQLDialect
    
    # Test that imports don't raise errors
    assert compile is not None
    assert ASQLPreParser is not None
    assert compile_func is not None
    assert ASQLSyntaxError is not None
    assert ASQLCompilationError is not None
    assert ASQLDialect is not None
