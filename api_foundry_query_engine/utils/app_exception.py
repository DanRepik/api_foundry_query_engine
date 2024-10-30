class ApplicationException(Exception):
    """Custom exception class for application errors."""

    def __init__(self, status_code: int, message: str):
        """
        Initialize the ApplicationException.

        Args:
        - status_code (int): The HTTP status code associated with the
            exception.
        - message (str): The error message.
        """
        super().__init__(message)
        self.status_code = status_code
        self.message = message

    def __str__(self):
        """Return a string representation of the exception."""
        return (
            f"ApplicationException(status_code={self.status_code}, "
            + f"message='{self.message}')"
        )
