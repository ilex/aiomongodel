"""Document fields."""

import abc
import re
from datetime import datetime
from decimal import Decimal

import bson.errors
from bson import ObjectId, Decimal128

from aiomongodel.errors import ValidationError, StopValidation
from aiomongodel.utils import _Empty, import_class


__all__ = ['AnyField', 'StrField', 'EmailField', 'IntField',
           'FloatField', 'DecimalField', 'DateTimeField',
           'EmbDocField', 'ListField', 'RefField', 'SynonymField',
           'ObjectIdField']


class Field(abc.ABC):
    """Base class for all fields.

    Attributes:
        name (str): Name of the field.
        mongo_name (str): Name of the field in mongodb.
        required (bool): Is field required.
        allow_none (bool): Can field be assigned with ``None``.
        default: Default value for field.
        verbose_name (str): Verbose field name for met information about field.
        choices (dict, set): Dict or set of choices for a field. If it is a
            ``dict`` keys are used as choices.

    """

    def __init__(self, *, required=True, default=_Empty, mongo_name=None,
                 name=None, allow_none=False, choices=None, field_type=None,
                 verbose_name=None):
        """Create field.

        Args:
            required (bool): Is field required. Defaults to ``True``.
            default: Default value for a field. When document has no value for
                field in ``__init__`` it try to use default value (if it is
                not ``_Empty``). Defaults to ``_Empty``.

                .. note::
                    Default value is ignored if field is not required.

                .. note::
                    Default can be a value or a callable with no arguments.

            mongo_name (str): Name of the field in MongoDB.
                Defaults to ``None``.

                .. note::
                    If ``mongo_name`` is None it is set to ``name`` of the
                    field.

            name (str): Name of the field. Should not be used explicitly as
                it is set by metaclass. Defaults to ``None``.
            allow_none (bool): Can field be assign with ``None``. Defaults
                to ``False``.
            verbose_name (str): Verbose field name for met information about field.
                Defaults to ``None``.
            choices (dict, set): Possible values for field. If it is a
                ``dict``, keys should be possible values. To preserve values
                order use ``collections.OrderedDict``. Defaults to ``None``.

        .. note::
            If ``choices`` are given then other constraints are ignored.

        """
        self.field_type = field_type
        self.mongo_name = mongo_name
        self.name = name
        self.required = required
        self.allow_none = allow_none
        self._default = default
        self.verbose_name = verbose_name
        if choices is None or isinstance(choices, dict):
            self.choices = choices
        else:
            self.choices = set(choices)

        self.validators = [self._validate_none,
                           self._validate_type]

        if self.choices is not None:
            self.validators.append(self._validate_choices)

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

    def to_mongo(self, value):
        """Convert value to mongo format."""
        return value

    def from_mongo(self, value):
        """Convert value from mongo format to python field format."""
        return value

    def from_data(self, value):
        """Convert value from user provided data to field type.

        Args:
            value: Value provided by user.

        Returns:
            Converted value or value as is if error occured. If value is
            ``None`` return ``None``.
        """
        try:
            return None if value is None else self.field_type(value)
        except (ValueError, TypeError):
            return value

    @property
    def s(self):
        """Return mongodb name of the field.

        This property can be used wherever mongodb field's name is required.

        Example:

        .. code-block:: python

            User.q(db).find({User.name.s: 'Francesco', User.is_admin.s: True},
                            {User.posts.s: 1, User._id.s: 0})

        .. note::
            Field's ``name`` and ``mongo_name`` could be different so
            ``User.is_admin.s`` could be for example ``'isadm'``.

        """
        return self.mongo_name

    def _validate_none(self, value):
        if value is None:
            if self.allow_none:
                raise StopValidation()
            raise ValidationError('none value is not allowed')

    def _validate_type(self, value):
        if not isinstance(value, self.field_type):
            raise ValidationError('invalid value type')

    def _validate_choices(self, value):
        if value in self.choices:
            raise StopValidation()
        raise ValidationError("value does not match any variant")

    def validate(self, value):
        try:
            for func in self.validators:
                func(value)
        except StopValidation:
            return


class AnyField(Field):
    """Any type field.

    Can store any type of value. Store a value as is.
    It's up to developer if a value can be stored in mongodb.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validators = [self._validate_none]
        if self.choices is not None:
            self.validators.append(self._validate_choices)

    def from_data(self, value):
        return value


class StrField(Field):
    """String field."""

    def __init__(self, *, regex=None, allow_blank=False,
                 min_length=None, max_length=None, **kwargs):
        """Create string field.

        Args:
            regex (str): Regular expression for field's values.
                Defaults to ``None``.
            allow_blank (bool): Can field be assigned with blank string.
                Defaults to ``False``.
            min_length (int): Minimum length of field's values.
                Defaults to ``None``.
            max_length (int): Maximum length of field's values.
                Defaults to ``None``.
            **kwargs: Other arguments from ``Field``.
        """
        super().__init__(field_type=str, **kwargs)
        self.regex = re.compile(regex) if isinstance(regex, str) else regex
        self.allow_blank = allow_blank
        self.min_length = min_length
        self.max_length = max_length

        if self.regex is not None:
            self.validators.append(self._validate_regex)
        self.validators.append(self._validate_blank)
        if self.min_length:
            self.validators.append(self._validate_min_length)
        if self.max_length is not None:
            self.validators.append(self._validate_max_length)

    def _validate_max_length(self, value):
        if len(value) > self.max_length:
            raise ValidationError('length is greater than {constraint}',
                                  constraint=self.max_length)

    def _validate_min_length(self, value):
        if len(value) < self.min_length:
            raise ValidationError('length is less than {constraint}',
                                  constraint=self.min_length)

    def _validate_blank(self, value):
        if value == '':
            if self.allow_blank:
                raise StopValidation()
            raise ValidationError('blank value is not allowed')

    def _validate_regex(self, value):
        if not self.regex.match(value):
            raise ValidationError(
                'value does not match pattern {constraint}',
                constraint=self.regex.pattern)


class BoolField(Field):
    """Boolean field."""

    def __init__(self, **kwargs):
        super().__init__(field_type=bool, **kwargs)


class NumberField(Field, metaclass=abc.ABCMeta):
    """Base class for number fields."""

    def __init__(self, *, gte=None, lte=None, gt=None, lt=None, **kwargs):
        """Create number field.

        Args:
            gte: Greater than or equal limit. Defaults to ``None``.
            lte: Less than or equal limit. Defaults to ``None``.
            gt: Greater than limit. Defaults to ``None``.
            lt: Less than limit. Defaults to ``None``.
            **kwargs: Other arguments from ``Field``.
        """
        super().__init__(**kwargs)
        self.gte = gte
        self.lte = lte
        self.gt = gt
        self.lt = lt
        if gte is not None:
            self.validators.append(self._validate_gte)
        if lte is not None:
            self.validators.append(self._validate_lte)
        if gt is not None:
            self.validators.append(self._validate_gt)
        if lt is not None:
            self.validators.append(self._validate_lt)

    def _validate_gte(self, value):
        if value < self.gte:
            raise ValidationError('value is less than {constraint}',
                                  constraint=self.gte)

    def _validate_lte(self, value):
        if value > self.lte:
            raise ValidationError('value is greater than {constraint}',
                                  constraint=self.lte)

    def _validate_gt(self, value):
        if value <= self.gt:
            raise ValidationError('value should be greater than {constraint}',
                                  constraint=self.gt)

    def _validate_lt(self, value):
        if value >= self.lt:
            raise ValidationError('value should be less than {constraint}',
                                  constraint=self.lt)


class IntField(NumberField):
    """Integer field."""

    def __init__(self, **kwargs):
        """Create int field."""
        super().__init__(field_type=int, **kwargs)


class FloatField(NumberField):
    """Float field."""

    def __init__(self, **kwargs):
        """Create float field."""
        super().__init__(field_type=float, **kwargs)


class DateTimeField(Field):
    """Date and time field based on datetime.datetime."""

    def __init__(self, **kwargs):
        super().__init__(field_type=datetime, **kwargs)

    def from_data(self, value):
        return value


class ObjectIdField(Field):
    """ObjectId field."""

    def __init__(self, **kwargs):
        super().__init__(field_type=ObjectId, **kwargs)

    def from_data(self, value):
        """Convert value to ObjectId.

        Args:
            value (ObjectId, str): ObjectId value or 24-character hex string.

        Returns:
            None or ObjectId value. If value is not ObjectId and can't
            be converted return as is.
        """
        if value is None or isinstance(value, ObjectId):
            return value

        try:
            return ObjectId(value)
        except (bson.errors.InvalidId, TypeError):
            return value


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

    .. code-block:: python

        assert Comment.author.name.s == 'author.name'
        assert Article.tags._id.s == 'tags._id'
        assert Hotel.rooms.category.s == 'rooms.category'
        assert Hotel.rooms.category.name.s == 'rooms.category.name'

    so you can use them to build queries:

    .. code-block:: python

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
        super().__init__(**kwargs)

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
        self.validators.append(lambda value: value.validate())

    def validate(self, value):
        self.field_type = self.document_class
        super().validate(value)

    def to_mongo(self, value):
        if value is None:
            return None
        return value.to_mongo()

    def from_mongo(self, value):
        if value is None:
            return None
        return self.document_class.from_mongo(value)

    def from_data(self, value):
        if value is None or isinstance(value, self.document_class):
            return value

        try:
            return self.document_class.from_data(value)
        except (TypeError, ValueError):
            return value


class ListField(CompoundField):
    """List field."""

    def __init__(self, item_field, *,
                 min_length=None, max_length=None, **kwargs):
        """Create List field.

        Args:
            item_field (Field): Instance of the field to reflect list
                items' type.
            min_length (int): Minimum length of the list. Defaults to ``None``.
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
        super().__init__(document_class, base_document_class,
                         field_type=list, **kwargs)

        self.item_field = item_field
        self.min_length = min_length
        self.max_length = max_length

        if min_length is not None:
            self.validators.append(self._validate_min_length)
        if max_length is not None:
            self.validators.append(self._validate_max_length)
        self.validators.append(self._validate_items)

    def _validate_min_length(self, value):
        if len(value) < self.min_length:
            raise ValidationError('list length is less than {constraint}',
                                  constraint=self.min_length)

    def _validate_max_length(self, value):
        if len(value) > self.max_length:
            raise ValidationError('list length is greater than {constraint}',
                                  constraint=self.max_length)

    def _validate_items(self, value):
        errors = {}
        for index, item in enumerate(value):
            try:
                self.item_field.validate(item)
            except ValidationError as e:
                errors[index] = e

        if errors:
            raise ValidationError(errors)

    def to_mongo(self, value):
        if value is None:
            return None
        return [self.item_field.to_mongo(item) for item in value]

    def from_mongo(self, value):
        if value is None:
            return None
        return [self.item_field.from_mongo(item) for item in value]

    def from_data(self, value):
        # if value not a list just return as is as well as None
        if value is None or not isinstance(value, list):
            return value
        return [self.item_field.from_data(item) for item in value]


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
        self.validators = [self._validate_none, self._validate_ref]

    def _validate_ref(self, value):
        # ref value could be reference instance
        _id = value._id if isinstance(value, self.document_class) else value
        self.document_class._id.validate(_id)

    def to_mongo(self, value):
        if isinstance(value, self.document_class):
            return self.document_class._id.to_mongo(value._id)
        return self.document_class._id.to_mongo(value)

    def from_mongo(self, value):
        return self.document_class._id.from_mongo(value)

    def from_data(self, value):
        if isinstance(value, self.document_class):
            return value

        return self.document_class._id.from_data(value)


class EmailField(StrField):
    """Email field."""

    EMAIL_REGEX = re.compile(
        r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

    def __init__(self, *, regex=EMAIL_REGEX, **kwargs):
        """Create Email field.

        Args:
            regex (str, re.regex): Pattern for email address.
            **kwargs: Other arguments from ``Field`` and ``StrField``.
        """
        super().__init__(regex=regex, **kwargs)

    def _validate_regex(self, value):
        try:
            super()._validate_regex(value)
        except ValidationError:
            raise ValidationError('value is not a valid email address')


class DecimalField(NumberField):
    """Decimal number field.

    This field can be used only with MongoDB 3.4+.
    """

    def __init__(self, **kwargs):
        """Create Decimal field."""
        super().__init__(field_type=Decimal, **kwargs)

    def to_mongo(self, value):
        if value is None:
            return None
        return Decimal128(value)

    def from_mongo(self, value):
        if value is None:
            return None

        if not isinstance(value, Decimal128):
            value = Decimal128(str(value))

        return value.to_decimal()


class SynonymField(object):
    """Create synonym name for real field."""

    def __init__(self, original_field):
        """Create synonym for real document's field.

        Args:
            original_field: Field instance or string name of field.

        Example:

        .. code-block:: python

            class Doc(Document):
                _id = StrField()
                name = SynonymField(_id)

            class OtherDoc(Document):
                # _id field will be added automaticly.
                obj_id = SynonymField('_id')

        """
        self._original_field = original_field

    def __get__(self, instance, instance_type):
        if not instance:
            return instance_type.meta.fields[self.original_field_name]
        return getattr(instance, self.original_field_name)

    def __set__(self, instance, value):
        setattr(instance, self.original_field_name, value)

    @property
    def original_field_name(self):
        try:
            return self._original_field.name
        except AttributeError:  # original field is a string name of the field
            return self._original_field
