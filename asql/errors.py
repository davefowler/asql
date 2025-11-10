"""ASQL error classes."""


class ASQLError(Exception):
    """Base exception for ASQL errors."""
    pass


class ASQLSyntaxError(ASQLError):
    """Syntax error in ASQL query."""
    pass


class ASQLCompilationError(ASQLError):
    """Error during ASQL compilation."""
    pass


class ASQLResolutionError(ASQLError):
    """Error during schema resolution."""
    pass

