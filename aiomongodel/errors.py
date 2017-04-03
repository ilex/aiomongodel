"""Aiomongodel errors and exceptions."""


class AioMongodelException(Exception):
    """Base AioMongodel Exception class."""


class Error(AioMongodelException):
    """Base AioMongodel Error class."""


class ValidationError(Error):
    """Validation Error.

    Attributes:
        error: Can contain a simple error string or
            dict of nested validation errors.
    """

    def __init__(self, error=None):
        """Create Validation Error.

        Args:
            error: Can be string or dict of {key => ValidationError}
        """
        self.error = error

    def as_dict(self):
        """Extract all errors from ``self.error`` attribute.

        Returns:
            If ``self.error`` is not a dict return as is, else return
            dict of {key => ValidationError.as_dict()}
        """
        if not isinstance(self.error, dict):
            return self.error

        return {key: item.as_dict() for key, item in self.error.items()}

    def __str__(self):
        return str(self.error)

    def __repr__(self):
        return 'ValidationError({0})'.format(str(self))
