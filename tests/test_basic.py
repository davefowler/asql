"""Basic tests to verify setup."""

import pytest


def test_import() -> None:
    """Test that we can import the asql module."""
    import asql
    assert asql is not None
    assert asql.__version__ == "0.1.0"


def test_basic_setup() -> None:
    """Test that basic setup works."""
    assert True

