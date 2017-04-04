"""Common utils."""
import contextlib
import importlib
import re

__all__ = ['_Empty', 'snake_case', 'import_class']

CAMEL_TO_SNAKE = re.compile(r'((?<=[a-z0-9])[A-Z]|(?<!^)[A-Z](?=[a-z]))')
CLASSES_CACHE = {}
_Empty = object()
"""Empty object.

Used as default value for arguments.
"""


def snake_case(camel_case):
    """Turn CamelCase string to snake_case."""
    return CAMEL_TO_SNAKE.sub(r'_\1', camel_case).lower()


def import_class(absolute_import_path):
    """Import class by its path.

    Class is stored in cache after importing.

    Example:

    .. code-block:: python

        Document = import_class('aiomongodel.document.Document')


    Args:
        absolute_import_path (str): Absolute path for class to import.

    Returns:
        type: Class object.

    Raises:
        ImportError: If class can't be imported by its path.
    """
    global CLASSES_CACHE

    with contextlib.suppress(KeyError):
        return CLASSES_CACHE[absolute_import_path]

    # class is missed in cache so try to import it
    try:
        module_path, class_name = absolute_import_path.rsplit('.', 1)
    except (ValueError, AttributeError):
        raise ImportError(
            "Import path should be absolute string, not '{}'".format(
                absolute_import_path))
    module = importlib.import_module(module_path)
    try:
        CLASSES_CACHE[absolute_import_path] = module.__dict__[class_name]
    except KeyError:
        raise ImportError(
            "No class named '{0}'".format(absolute_import_path))

    return CLASSES_CACHE[absolute_import_path]
