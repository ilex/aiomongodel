"""Aiomongodel errors and exceptions."""
import re

import pymongo.errors

from aiomongodel.utils import _Empty


class AioMongodelException(Exception):
    """Base AioMongodel Exception class."""


class Error(AioMongodelException):
    """Base AioMongodel Error class."""


class ValidationError(Error):
    """Raised on model validation error.

    Template for translation of error messages:

    .. code-block:: python

        translation = {
            "field is required": "",
            "none value is not allowed": "",
            "blank value is not allowed": "",
            "invalid value type": "",
            "value does not match any variant": "",
            "value does not match pattern {constraint}": "",
            "length is less than {constraint}": "",
            "length is greater than {constraint}": "",
            "value is less than {constraint}": "",
            "value is greater than {constraint}": "",
            "value should be greater than {constraint}": "",
            "value should be less than {constraint}": "",
            "list length is less than {constraint}": "",
            "list length is greater than {constraint}": "",
            "value is not a valid email address": "",
        }


    Attributes:
        error: Can contain a simple error string or
            dict of nested validation errors.
        constraint: A constraint value for validation error.
    """

    def __init__(self, error=None, constraint=_Empty):
        """Create validation error.

        Args:
            error: Can be string or dict of {key => ValidationError}
            constraint: A constraint value for the error. If it's not
                empty it is used in error message formatting as
                ``{constraint}``.
        """
        self.error = error
        self.constraint = constraint

    def as_dict(self, translation=None):
        """Extract all errors from ``self.error`` attribute.

        Args:
            translation (dict): A dict of translation for default validation
                error messages.

        Returns:
            If ``self.error`` is a string return as string.
            If ``self.error`` is a dict return
            dict of {key => ValidationError.as_dict()}
        """
        if not isinstance(self.error, dict):
            if translation:
                message = translation.get(self.error, self.error)
            else:
                message = self.error
            return self._format(message)

        return {key: item.as_dict(translation)
                for key, item in self.error.items()}

    def _format(self, message):
        if self.constraint is _Empty:
            return message
        return message.format(constraint=self.constraint)

    def __str__(self):
        if isinstance(self.error, str):
            return self._format(self.error)
        return str(self.error)

    def __repr__(self):
        return 'ValidationError({0})'.format(self)


class StopValidation(AioMongodelException):
    """Raised when validation of the field should be stopped."""


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
