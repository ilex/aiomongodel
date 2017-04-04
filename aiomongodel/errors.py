"""Aiomongodel errors and exceptions."""
import re

import pymongo.errors


class AioMongodelException(Exception):
    """Base AioMongodel Exception class."""


class Error(AioMongodelException):
    """Base AioMongodel Error class."""


class ValidationError(Error):
    """Raised on model validation error.

    Attributes:
        error: Can contain a simple error string or
            dict of nested validation errors.
    """

    def __init__(self, error=None):
        """Create validation error.

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


class DocumentNotFoundError(Error):
    """Raised when document is not found in db."""


class DuplicateKeyError(Error, pymongo.errors.DuplicateKeyError):
    """Raised on unique key constraint error."""

    index_name_regexp = re.compile(r': ([^ ]+) dup key:')

    def __init__(self, message):
        """Create error.

        Args:
            message (str): String representation of
                ``pymongo.errors.DuplicateKeyError``.
        """
        self.message = message

    @property
    def index_name(self):
        """Name of the unique index which raised error."""
        m = self.index_name_regexp.search(self.message)
        try:
            return m.group(1)
        except Exception:
            return None
