from trafaret import DataError


class AioMongodelException(Exception):
    """Base AioMongodel Exception class."""


class Error(AioMongodelException):
    """Base AioMongodel Error class."""


class ValidationError(Error, DataError):
    """Validation Error."""
