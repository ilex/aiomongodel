"""Base document class."""
import contextlib
from collections import OrderedDict

import trafaret as t

from bson import ObjectId, SON

from aiomongodel.errors import ValidationError
from aiomongodel.queryset import MotorQuerySet
from aiomongodel.fields import Field, ObjectIdField, SynonymField, _Empty
from aiomongodel.utils import snake_case


class Meta:
    """Storage for Document meta info."""

    OPTIONS = {'query_class', 'collection_name',
               'default_query', 'default_sort',
               'fields', 'fields_synonyms', 'indexes',
               'codec_options', 'read_preference', 'read_concern',
               'write_concern'}

    def __init__(self, **kwargs):
        self._validate_options(kwargs)

        self.query_class = kwargs.get('query_class', None)
        self.collection_name = kwargs.get('collection_name', None)
        self.default_query = kwargs.get('default_query', {})
        self.default_sort = kwargs.get('default_sort', None)
        self.fields = kwargs.get('fields', None)
        self.fields_synonyms = kwargs.get('fields_synonyms', None)
        self._trafaret = None
        self.indexes = kwargs.get('indexes', None)

        self.codec_options = kwargs.get('codec_options', None)
        self.read_preference = kwargs.get('read_preference', None)
        self.read_concern = kwargs.get('read_concern', None)
        self.write_concern = kwargs.get('write_concern', None)

    def _validate_options(self, kwargs):
        keys = set(kwargs.keys())
        diff = keys - self.__class__.OPTIONS
        if diff:
            # TODO: change Exception type
            raise ValueError(
                'Unrecognized Meta options: {0}.'.format(', '.join(diff)))

    def collection(self, db):
        return db.get_collection(
            self.collection_name,
            read_preference=self.read_preference,
            read_concern=self.read_concern,
            write_concern=self.write_concern,
            codec_options=self.codec_options)

    @property
    def trafaret(self):
        if self._trafaret is not None:
            return self._trafaret

        doc_trafaret = {}
        for key, item in self.fields.items():
            t_key = t.Key(key, optional=(not item.required))
            doc_trafaret[t_key] = item.trafaret

        self._trafaret = t.Dict(doc_trafaret)
        return self._trafaret


class BaseDocumentMeta(type):
    """Base metaclass for documents."""

    meta_options_class = Meta

    def __new__(mcls, name, bases, namespace):
        """Create new Document class.

        Gather fields, create trafaret, set document meta.
        """
        new_class = super().__new__(mcls, name, bases, namespace)

        if name in {'Document', 'EmbeddedDocument'}:
            return new_class

        # prepare meta options from Meta class of the new_class if any.
        options = mcls._get_meta_options(new_class)

        # gather fields
        (options['fields'],
         options['fields_synonyms']) = mcls._get_fields(new_class)

        setattr(new_class, 'meta', mcls.meta_options_class(**options))

        return new_class

    @classmethod
    def _get_fields(mcls, new_class):
        # we should search for fields in all bases classes in reverse order
        # than python search for attributes so that fields could be
        # overwritten in subclasses.
        # As bases we use __mro__.
        fields = OrderedDict()
        synonyms = dict()
        # there are no fields in base classes.
        ignore_bases = {'object', 'BaseDocument',
                        'Document', 'EmbeddedDocument'}
        mro_ns_gen = (cls.__dict__
                      for cls in reversed(new_class.__mro__)
                      if cls.__name__ not in ignore_bases)

        for ns in mro_ns_gen:
            for name, item in ns.items():
                if isinstance(item, Field):
                    if not item.name:
                        item.name = name
                    fields[name] = item
                elif isinstance(item, SynonymField):
                    synonyms[item] = name

        return fields, {item.origin_field_name: name
                        for item, name in synonyms.items()}

    @classmethod
    def _get_meta_options(mcls, new_class):
        # get meta options from Meta class attribute
        doc_meta_options = {}
        doc_meta = new_class.__dict__.get('Meta', None)
        if doc_meta:
            doc_meta_options = {key: doc_meta.__dict__[key]
                                for key in doc_meta.__dict__
                                if not key.startswith('__')}

        return doc_meta_options


class DocumentMeta(BaseDocumentMeta):
    """Document metaclass."""

    query_class = MotorQuerySet
    default_id_field = ObjectIdField(name='_id', required=True,
                                     default=lambda: ObjectId())

    @classmethod
    def _get_fields(mcls, new_class):
        fields, synonyms = super()._get_fields(new_class)

        # add _id field if needed
        if '_id' not in fields:
            fields['_id'] = mcls.default_id_field
            setattr(new_class, '_id', mcls.default_id_field)
            return fields, synonyms

        if not fields['_id'].required:
            raise ValueError(
                "'{0}._id' field should be required.".format(
                    new_class.__name__))

        return fields, synonyms

    @classmethod
    def _get_meta_options(mcls, new_class):
        meta_options = super()._get_meta_options(new_class)

        if 'collection_name' not in meta_options:
            meta_options['collection_name'] = snake_case(new_class.__name__)

        if 'query_class' not in meta_options:
            meta_options['query_class'] = mcls.query_class

        return meta_options


class EmbeddedDocumentMeta(BaseDocumentMeta):
    """Embedded Document metaclass."""


class BaseDocument(object):
    """Base class for Document and EmbeddedDocument."""

    def __init__(self, *, _empty=False, **kwargs):
        """Initialize document.

        Args:
            _empty (bool): If True return an empty document without setting
                any field.
            **kwargs: Fields values to set. Keys should be fields' `name`s not
                `mongo_name`s.

        Raises:
            ValidationError: If there is an error during setting fields
                with values.
        """
        self._data = OrderedDict()
        if _empty:
            return

        meta = self.__class__.meta
        for field_name, field in meta.fields.items():
            with contextlib.suppress(KeyError):
                setattr(self, field_name, kwargs[field_name])
                continue

            # if there was a KeyError try to use a synonym name of the field
            try:
                syn_field_name = meta.fields_synonyms[field_name]
                setattr(self, field_name, kwargs[syn_field_name])
            except KeyError:
                # for required field try to use a default value
                if field.required:
                    if field.default is _Empty:
                        raise ValidationError(
                            ('A required field {0}.{1} should be provided '
                             'with an explicit value or have '
                             'a default value.').format(
                                 self.__class__.__name__, field_name))
                    setattr(self, field_name, field.default)

    def _set_son(self, data):
        self._data = OrderedDict()
        for field_name, field in self.meta.fields.items():
            with contextlib.suppress(KeyError):  # ignore missed fields
                self._data[field_name] = field.from_son(data[field.mongo_name])

        return self

    def to_son(self):
        son = SON()
        for field_name, field in self.meta.fields.items():
            if field_name in self._data:
                son[field.mongo_name] = field.to_son(self._data[field_name])

        return son

    @classmethod
    def from_son(cls, data):
        inst = cls(_empty=True)
        inst._set_son(data)
        return inst

    @classmethod
    def from_data(cls, data):
        return cls(**data)


class Document(BaseDocument, metaclass=DocumentMeta):
    """Base Document class."""

    @classmethod
    def q(cls, db):
        return cls.meta.query_class(cls, db)

    @classmethod
    def coll(cls, db):
        return cls.meta.collection(db)

    @classmethod
    async def create(cls, db, **kwargs):
        inst = cls.from_data(kwargs)
        return await inst.save(db)

    async def save(self, db):
        data = self.to_son()
        cls = self.__class__
        await cls.q(db).replace_one({'_id': data['_id']}, data, upsert=True)
        return self

    async def reload(self, db):
        cls = self.__class__
        data = await cls.coll(db).find_one(self.query_id)
        self._set_son(data)
        return self

    async def update(self, db, update_document):
        """Update current object using query.

        Usage:
            class User(Document):
                name = StrField()
                value = IntField(default=0)

            async def go(db):
                u = await User(name='xxx').save(db)
                await u.update(db,
                               {'$set': {User.name.s: 'yyy'},
                                '$inc': {User.value.s: 1}})
        """
        cls = self.__class__
        count = await cls.q(db).update_one(self.query_id, update_document)
        # TODO: maybe we should return number of updates or raise if it's 0.
        if count > 0:
            await self.reload(db)

        return self

    async def delete(self, db):
        return await self.__class__.q(db).delete_one(self.query_id)

    @property
    def query_id(self):
        return {'_id': self.__class__._id.to_son(self._id)}


class EmbeddedDocument(BaseDocument, metaclass=EmbeddedDocumentMeta):
    """Base Embedded Document class."""
