"""Document fields."""

import functools
from datetime import datetime
from decimal import Decimal

import trafaret as t
from bson import ObjectId, Decimal128

from .errors import ValidationError
from .utils import _Empty, import_class


class Field(object):
    """Base class for all fields.

    Attributes:
        name (str): Name of the field.
        mongo_name (str): Name of the field in mongodb.
        required (bool): Is field required.
        default: Default value for field.
        trafaret: Trafaret of the field.
        choices (list): List of choices for a field.
    """

    def __init__(self, trafaret, *, required=True, default=_Empty,
                 mongo_name=None, name=None, choices=None):
        """Create field.

        Args:
            trafaret: Trafaret for field. Can be ``None`` if trafaret would be
                a property in subclass.
            required (bool): Is field required. Defaults to ``True``.
            default: Default value for a field. When document has no value for
                field in ``__init__`` it try to use default value (if it is
                not ``_Empty``). Defaults to ``_Empty``.
                Note:: Default value is ignored if field is not required.
                Note:: Default can be a value or a callable with no arguments.
            mongo_name (str): Name of the field in MongoDB. Defaults to None.
                Note:: If ``mongo_name`` is None it is set to ``name`` of the
                    field.
            name (str): Name of the field. Should not be used explicitly as
                it is set by metaclass. Defaults to ``None``.
            choices (list): List of possible values for field. Defaults
                to ``None``.
        """
        self.mongo_name = mongo_name
        self.name = name
        self.required = required
        self._default = default
        if trafaret:
            self.trafaret = trafaret
            if choices:
                self.trafaret = trafaret >> t.Enum(*choices)
        self.choices = choices

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        if self.mongo_name is None:
            self.mongo_name = value

    @property
    def default(self):
        try:
            return self._default()
        except TypeError:  # is not callable
            return self._default

    def __get__(self, instance, instance_type):
        if instance is None:
            return self
        try:
            return instance._data[self.name]
        except KeyError:
            # TODO: should we try to return default here?
            return None

    def __set__(self, instance, value):
        instance._data[self.name] = self.from_data(value)

    def to_son(self, value):
        """Convert value to mongo format."""
        return value

    def from_son(self, value):
        """Convert value from mongo format to python field format."""
        return value

    def from_data(self, value):
        """Convert value from user provided data.

        This method performs a validation according to field
        format.

        Args:
            value: Value provided by user.

        Returns:
            Validated value.

        Raises:
            ValidationError: If validation failed.
        """
        try:
            return self.trafaret.check(value)
        except t.DataError as e:
            raise ValidationError(error=str(e))

    @property
    def s(self):
        """Return mongodb name of the field.

        This property can be used wherever mongodb field's name is required.

        Example:

        .. code-block:: python

            User.q(db).find({User.name.s: 'Francesco', User.is_admin.s: True},
                            {User.posts.s: 1, User._id.s: 0})

        Note:: Field's ``name`` and ``mongo_name`` could be different so
            ``User.is_admin.s`` could be for example ``'isadm'``.
        """
        return self.mongo_name


class AnyField(Field):
    """Any type field.

    Validation and compatibility to strore in mongodb is up to developer.
    """

    def __init__(self, **kwargs):
        super().__init__(t.Any(), **kwargs)


class StrField(Field):
    """String field."""

    def __init__(self, *, allow_blank=True, regexp=None, min_length=None,
                 max_length=None, **kwargs):
        """Create string field.

        Args:
            allow_blank (bool): Is empty string allowed. Defaults to ``True``.
            regexp (str): Regular expression for field's values.
                Defaults to ``None``.
            min_length (int): Minimum length of field's values.
                Defaults to ``None``
            max_length (int): Maximum length of field's values.
                Defaults to ``None``
            **kwargs: Other arguments from ``Field``.

        Note:: If ``regex`` is given ``allow_blank``, ``min_length`` and
            ``max_length`` are ignored.
        """
        if regexp is None:
            trafaret = t.String(allow_blank=allow_blank,
                                min_length=min_length,
                                max_length=max_length)
        else:
            trafaret = t.Regexp(regexp=regexp)
        super().__init__(trafaret, **kwargs)


class BoolField(Field):
    """Boolean field."""

    def __init__(self, **kwargs):
        super().__init__(t.Bool(), **kwargs)


class IntField(Field):
    """Integer field."""

    def __init__(self, *, gte=None, lte=None, gt=None, lt=None, **kwargs):
        """Create int field.

        Args:
            gte (int): Greater than or equal limit. Defaults to ``None``.
            lte (int): Less than or equal limit. Defaults to ``None``.
            gt (int): Greater than limit. Defaults to ``None``.
            lt (int): Less than limit. Defaults to ``None``.
            **kwargs: Other arguments from ``Field``.
        """
        super().__init__(t.Int(gte, lte, gt, lt), **kwargs)


class DateTimeField(Field):
    """Date and time field based on datetime.datetime."""

    def __init__(self, **kwargs):
        super().__init__(t.Type(datetime), **kwargs)


class FloatField(Field):
    """Float field."""

    def __init__(self, *, gte=None, lte=None, gt=None, lt=None, **kwargs):
        """Create float field.

        Args:
            gte (float): Greater than or equal limit. Defaults to ``None``.
            lte (float): Less than or equal limit. Defaults to ``None``.
            gt (float): Greater than limit. Defaults to ``None``.
            lt (float): Less than limit. Defaults to ``None``.
            **kwargs: Other arguments from ``Field``.
        """
        super().__init__(t.Float(gte, lte, gt, lt), **kwargs)


class ObjectIdField(Field):
    """ObjectId field."""

    def __init__(self, **kwargs):
        super().__init__(t.Type(ObjectId), **kwargs)


class CompoundFieldNameBuilder:
    """Helper class to encapsulate compound name join."""

    __slots__ = ['_obj', '_prefix']

    def __init__(self, obj, prefix):
        self._obj = obj
        self._prefix = prefix

    def __getattr__(self, name):
        document_class = getattr(self._obj, 'document_class', None)
        if not document_class:
            raise AttributeError(
                "'{0}' has no attribute {1}".format(
                    self._obj.__class__.__name__, name))

        return CompoundFieldNameBuilder(getattr(self._obj, name),
                                        self._prefix)

    @property
    def s(self):
        return self._prefix + '.' + self._obj.s


class CompoundField(Field):
    """Base class for complex fields.

    This class should be base for embedded document fields or list fields
    which could contain embedded documents as their elements.
    This class makes it possible to build a complex fields name using
    attribute syntax and `s` property, i.e.:
        assert Comment.author.name.s == 'author.name'
        assert Article.tags._id.s == 'tags._id'
        assert Hotel.rooms.category.s == 'rooms.category'
        assert Hotel.rooms.category.name.s == 'rooms.category.name'

    so you can use them to build queries:
        Hotel.q(db).find({Hotel.rooms.category.name.s: 'Lux'})
    """

    def __init__(self, document_class, base_document_class, **kwargs):
        if (isinstance(document_class, str) or
                document_class is None
                or issubclass(document_class, base_document_class)):
            self._document_class = document_class
        else:
            raise TypeError(
                ("document_class should be a "
                 "subclass of '{0}' or str, not a '{1}'").format(
                     base_document_class, document_class))
        self._base_document_class = base_document_class
        super().__init__(None, **kwargs)

    @property
    def document_class(self):
        if isinstance(self._document_class, str):
            self._document_class = import_class(self._document_class)
            if not issubclass(self._document_class, self._base_document_class):
                raise TypeError(
                    ("document_class should be a "
                     "subclass of '{0}', not a '{1}'").format(
                         self._base_document_class, self._document_class))

        return self._document_class

    def __getattr__(self, name):
        if self.document_class is None:
            raise AttributeError(
                "'{0}' has no attribute '{1}'".format(
                    self.__class__.__name__, name))

        return CompoundFieldNameBuilder(
            getattr(self.document_class, name), self.mongo_name)


class EmbDocField(CompoundField):
    """Embedded Document Field."""

    def __init__(self, document_class, **kwargs):
        """Create Embedded Document field.

        Args:
            document_class: A subclass of the
                ``aiomongodel.EmbeddedDocument`` class or string with
                absolute path to such class.
            **kwargs: Other arguments from ``Field``.
        """
        EmbeddedDocument = import_class('aiomongodel.EmbeddedDocument')
        super().__init__(document_class, EmbeddedDocument, **kwargs)

    @property
    def trafaret(self):
        return self.document_class.meta.trafaret

    def to_son(self, value):
        return value.to_son()

    def from_son(self, value):
        return self.document_class.from_son(value)

    def from_data(self, value):
        if isinstance(value, self.document_class):
            return value

        return self.document_class.from_data(value)


class ListField(CompoundField):
    """List field."""

    def __init__(self, item_field, *,
                 min_length=0, max_length=None, **kwargs):
        """Create List field.

        Args:
            item_field (Field): Instance of the field to reflect list
                items' type.
            min_length (int): Minimum length of the list. Default to ``0``.
            max_length (int): Maximum length of the list. Defaults to ``None``.
            **kwargs: Other arguments from ``Field``.

        Raises:
            TypeError: If item_field is not instance of the ``Field`` subclass.
        """
        if not isinstance(item_field, Field):
            raise TypeError(
                ('item_field should be an instance of the `Field` '
                 'subclass, not of the `{0}`').format(type(item_field)))

        EmbeddedDocument = import_class('aiomongodel.EmbeddedDocument')
        document_class, base_document_class = (
            (item_field._document_class, EmbeddedDocument)
            if isinstance(item_field, EmbDocField)
            else (None, None))
        super().__init__(document_class, base_document_class, **kwargs)

        self.item_field = item_field
        self.min_length = min_length
        self.max_length = max_length
        self._partial_trafaret = functools.partial(
            t.List, min_length=min_length, max_length=max_length)

    @property
    def trafaret(self):
        return self._partial_trafaret(
            self.item_field.trafaret)

    def to_son(self, value):
        return [self.item_field.to_son(item) for item in value]

    def from_son(self, value):
        return [self.item_field.from_son(item) for item in value]

    def from_data(self, value):
        if not isinstance(value, list):
            raise ValidationError('value is not a list')
        if len(value) < self.min_length:
            raise ValidationError(
                'list length is less than {0}'.format(self.min_length))
        if self.max_length is not None and len(value) > self.max_length:
            raise ValidationError(
                'list length is greater than {0}'.format(self.max_length))

        errors = {}
        lst = []
        for index, item in enumerate(value):
            try:
                lst.append(self.item_field.from_data(item))
            except ValidationError as e:
                errors[index] = e

        if errors:
            raise ValidationError(error=errors)

        return lst


class RefField(CompoundField):
    """Reference field."""

    def __init__(self, document_class, **kwargs):
        """Create Reference field.

        Args:
            document_class: A subclass of the ``aiomongodel.Document`` class
                or string with absolute path to such class.
            **kwargs: Other arguments from ``Field``.
        """
        Document = import_class('aiomongodel.Document')
        super().__init__(document_class, Document, **kwargs)

    @property
    def trafaret(self):
        return self.document_class._id.trafaret

    def to_son(self, value):
        if isinstance(value, self.document_class):
            return self.document_class._id.to_son(value._id)
        return self.document_class._id.to_son(value)

    def from_son(self, value):
        return self.document_class._id.from_son(value)

    def from_data(self, value):
        if isinstance(value, self.document_class):
            return value

        return self.document_class._id.from_data(value)


class EmailField(Field):
    """Email field."""

    def __init__(self, *, allow_blank=False, **kwargs):
        """Create Email field.

        Args:
            allow_blank (bool): Is empty string allowed.
                Defaults to ``False``.
            **kwargs: Other arguments from ``Field``.
        """
        super().__init__(t.Email(allow_blank=allow_blank), **kwargs)

    def from_data(self, value):
        try:
            return super().from_data(value)
        except TypeError:
            raise ValidationError(error='value is not a valid email address')


class URLField(Field):
    """URL field."""

    def __init__(self, *, allow_blank=False, **kwargs):
        """Create URL field.

        Args:
            allow_blank (bool): Is empty string allowed.
                Defaults to ``False``.
            **kwargs: Other arguments from ``Field``.
        """
        super().__init__(t.URL(allow_blank=allow_blank), **kwargs)

    def from_data(self, value):
        try:
            return super().from_data(value)
        except AttributeError:
            raise ValidationError(error='value is not URL')


class DecimalTrafaret(t.Int):
    """Trafaret class to check decimals."""

    value_type = Decimal


class DecimalField(Field):
    """Decimal number field.

    This field can be used only with MongoDB 3.4+.
    """

    def __init__(self, *, gt=None, lt=None, gte=None, lte=None, **kwargs):
        """Create Decimal field.

        Args:
            gte: Greater than or equal limit. Defaults to ``None``.
            lte: Less than or equal limit. Defaults to ``None``.
            gt: Greater than limit. Defaults to ``None``.
            lt: Less than limit. Defaults to ``None``.
            **kwargs: Other arguments from ``Field``.
        """
        super().__init__(DecimalTrafaret(gt=gt, lt=lt, gte=gte, lte=lte),
                         **kwargs)

    def to_son(self, value):
        return Decimal128(value)

    def from_son(self, value):
        return value.to_decimal()


class SynonymField(object):
    """Create synonym name for real field."""

    def __init__(self, origin_field):
        """Create synonym for real document's field.

        Args:
            origin_field: Field instance or string name of field.

        Example:

        .. code-block:: python

            class Doc(Document):
                _id = StrField()
                name = SynonymField(_id)

            class OtherDoc(Document):
                # _id field will be added automaticly.
                obj_id = SynonymField('_id')

        """
        self._origin_field = origin_field

    def __get__(self, instance, instance_type):
        if not instance:
            return instance_type.meta.fields[self.origin_field_name]
        return getattr(instance, self.origin_field_name)

    def __set__(self, instance, value):
        setattr(instance, self.origin_field_name, value)

    @property
    def origin_field_name(self):
        try:
            return self._origin_field.name
        except AttributeError:  # origin field is a string name of the field
            return self._origin_field
