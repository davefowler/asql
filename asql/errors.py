"""ASQL error classes."""


class ASQLError(Exception):
    """Base exception for ASQL errors."""
    
    def __init__(self, message: str, position: int = None):
        """
        Initialize ASQL error.
        
        Args:
            message: Error message
            position: Optional character position where error occurred
        """
        super().__init__(message)
        self.message = message
        self.position = position
    
    def __str__(self) -> str:
        """Return formatted error message."""
        if self.position is not None:
            return f"{self.message} (at position {self.position})"
        return self.message


class ASQLSyntaxError(ASQLError):
    """Syntax error in ASQL query."""
    pass


class ASQLCompilationError(ASQLError):
    """Error during ASQL compilation."""
    pass


class ASQLResolutionError(ASQLError):
    """Error during schema resolution."""
    pass

