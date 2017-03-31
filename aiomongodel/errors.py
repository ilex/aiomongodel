class AioMongodelException(Exception):
    """Base AioMongodel Exception class."""


class Error(AioMongodelException):
    """Base AioMongodel Error class."""


class ValidationError(Error):
    """Validation Error."""

    def __init__(self, error=None):
        self.error = error

    def as_dict(self):
        if not isinstance(self.error, dict):
            return self.error

        return {key: item.as_dict() for key, item in self.error.items()}

    def __str__(self):
        return str(self.error)

    def __repr__(self):
        return 'ValidationError({0})'.format(str(self))
