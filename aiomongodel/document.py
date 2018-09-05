"""Base document class."""
import contextlib
import warnings
from collections import OrderedDict

from bson import ObjectId, SON

from aiomongodel.errors import ValidationError
from aiomongodel.queryset import MotorQuerySet
from aiomongodel.fields import Field, ObjectIdField, SynonymField, _Empty
from aiomongodel.utils import snake_case


class Meta:
    """Storage for Document meta info.

    Attributes:
        collection_name: Name of the document's db collection (note that
            it should be specified as ``collection`` Meta class attribute).
        indexes: List of ``pymongo.IndexModel`` for collection.
        queryset: Query set class to query documents.
        default_query: Each query in query set will be extended using this
            query through ``$and`` operator.
        default_sort: Default sort expression to order documents in ``find``.
        fields: OrderedDict of document fields as ``{field_name => field}``.
        fields_synonyms: Dict of synonyms for field
            as ``{field_name => synonym_name}``.
        codec_options: Collection's codec options.
        read_preference: Collection's read preference.
        write_concern: Collection's write concern.
        read_concern: Collection's read concern.

    """

    OPTIONS = {'queryset', 'collection',
               'default_query', 'default_sort',
               'fields', 'fields_synonyms', 'indexes',
               'codec_options', 'read_preference', 'read_concern',
               'write_concern'}

    def __init__(self, **kwargs):
        self._validate_options(kwargs)

        self.queryset = kwargs.get('queryset', None)
        self.collection_name = kwargs.get('collection', None)
        self.default_query = kwargs.get('default_query', {})
        self.default_sort = kwargs.get('default_sort', None)
        self.fields = kwargs.get('fields', None)
        self.fields_synonyms = kwargs.get('fields_synonyms', None)
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
        """Get collection for documents.

        Args:
            db: Database object.

        Returns:
            Collection object.
        """
        return db.get_collection(
            self.collection_name,
            read_preference=self.read_preference,
            read_concern=self.read_concern,
            write_concern=self.write_concern,
            codec_options=self.codec_options)


class BaseDocumentMeta(type):
    """Base metaclass for documents."""

    meta_options_class = Meta

    def __new__(mcls, name, bases, namespace):
        """Create new Document class.

        Gather meta options, gather fields, set document's meta.
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
        """Gather fields and fields' synonyms."""
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

        return fields, {item.original_field_name: name
                        for item, name in synonyms.items()}

    @classmethod
    def _get_meta_options(mcls, new_class):
        """Get meta options from Meta class attribute."""
        doc_meta_options = {}
        doc_meta = new_class.__dict__.get('Meta', None)
        if doc_meta:
            doc_meta_options = {key: doc_meta.__dict__[key]
                                for key in doc_meta.__dict__
                                if not key.startswith('__')}

        return doc_meta_options


class DocumentMeta(BaseDocumentMeta):
    """Document metaclass.

    This meta class add ``_id`` field if it is not specified in
    document class.

    Set collection name for document to snake case of the document class name
    if it is not specified in Meta class attribute of a the document class.

    Attributes:
        queryset: Default query set class.
        default_id_field: Field to use as ``_id`` field if it is not
            specified in document class.

    """

    queryset = MotorQuerySet
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

        if 'collection' not in meta_options:
            meta_options['collection'] = snake_case(new_class.__name__)

        if 'queryset' not in meta_options:
            meta_options['queryset'] = mcls.queryset

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
            **kwargs: Fields values to set. Each key should be a field name
                not a mongo name of the field.
        """
        self._data = OrderedDict()
        if _empty:
            return

        for field_name, field in self.meta.fields.items():
            try:
                value = self._get_field_value_from_data(kwargs, field_name)
            except KeyError:
                value = field.default

            if value is not _Empty:
                setattr(self, field_name, value)

    def to_data(self):
        """Return internal data of the document.

        .. note::
            Internal data can contain embedded document objects,
            lists etc.

        Returns:
            OrderedDict: Data of the document.
        """
        # TODO: Add recursive parameter
        return self._data

    def _get_field_value_from_data(self, data, field_name):
        """Retrieve value from data for given field_name.

        Try use synonym name if field's name is not in data.

        Args:
            data (dict): Data in form {field_name => value}.
            field_name (str): Field's name.

        Raises:
            KeyError: If there is no value in data for given field_name.
        """
        with contextlib.suppress(KeyError):
            return data[field_name]
        # try synonym name
        return data[self.meta.fields_synonyms[field_name]]

    def _set_mongo_data(self, data):
        """Set document's data using mongo data."""
        self._data = OrderedDict()
        for field_name, field in self.meta.fields.items():
            with contextlib.suppress(KeyError):  # ignore missed fields
                self._data[field_name] = field.from_mongo(
                    data[field.mongo_name])

        return self

    def populate_with_data(self, data):
        """Populate document object with data.

        Args:
            data (dict): Document data in form {field_name => value}.

        Returns:
            Self instance.

        Raises:
            AttributeError: On wrong field name.
        """
        # TODO: should we ignore wrong field_names?
        for field_name, value in data.items():
            setattr(self, field_name, value)
        return self

    def to_mongo(self):
        """Convert document to mongo format."""
        son = SON()
        for field_name, field in self.meta.fields.items():
            if field_name in self._data:
                son[field.mongo_name] = field.to_mongo(self._data[field_name])

        return son

    @classmethod
    def from_mongo(cls, data):
        """Create document from mongo data.

        Args:
            data (dict): SON data loaded from mongodb.

        Returns:
            Document instance.
        """
        inst = cls(_empty=True)
        inst._set_mongo_data(data)
        return inst

    @classmethod
    def from_data(cls, data):
        """Create document from user provided data.

        Args:
            data (dict): Data dict in form {field_name => value}.

        Returns:
            Document isinstance.
        """
        return cls(**data)

    def validate(self):
        """Validate data.

        Returns:
            Self instance.

        Raises:
            ValidationError: If document's data is not valid.
        """
        self.__class__.validate_document(self)
        return self

    @classmethod
    def validate_document(cls, document):
        """Validate given document.

        Args:
            document: Document instance to validate.

        Raises:
            ValidationError: If document's data is not valid.
        """
        errors = {}
        for field_name, field in cls.meta.fields.items():
            try:
                field.validate(document._data[field_name])
            except ValidationError as e:
                errors[field_name] = e
            except KeyError:
                if field.required:
                    errors[field_name] = ValidationError('field is required')

        if errors:
            raise ValidationError(errors)


class Document(BaseDocument, metaclass=DocumentMeta):
    """Base class for documents.

    Each document class should be defined by inheriting from this
    class and specifying fields and optionally meta options using internal
    Meta class.

    Fields are inherited from base classes and can be overwritten.

    Meta options are NOT inherited.

    Possible meta options for ``class Meta``:

    - ``collection``: Name of the document's db collection.
    - ``indexes``: List of ``pymongo.IndexModel`` for collection.
    - ``queryset``: Query set class to query documents.
    - ``default_query``: Each query in query set will be extended using
      this query through ``$and`` operator.
    - ``default_sort``: Default sort expression to order documents in
      ``find``.
    - ``codec_options``: Collection's codec options.
    - ``read_preference``: Collection's read preference.
    - ``write_concern``: Collection's write concern.
    - ``read_concern``: Collection's read concern.

    .. note::
        Indexes are not created automatically. Use
        ``MotorQuerySet.create_indexes`` method to create document's indexes.

    Example:

    .. code-block:: python

        from pymongo import IndexModel, ASCENDING, DESCENDING

        class User(Document):
            name = StrField(regex=r'^[a-zA-Z]{6,20}$')
            is_active = BoolField(default=True)
            created = DateTimeField(default=lambda: datetime.utcnow())

            class Meta:
                # define a collection name
                collection = 'users'
                # define collection indexes. Use
                # await User.q(db).create_indexes()
                # to create them on application startup.
                indexes = [
                    IndexModel([('name', ASCENDING)], unique=True),
                    IndexModel([('created', DESCENDING)])]
                # order by `created` field by default
                default_sort = [('created', DESCENDING)]

        class ActiveUser(User):
            is_active = BoolField(default=True, choices=[True])

            class Meta:
                collection = 'users'
                # specify a default query to work ONLY with
                # active users. So for example
                # await ActiveUser.q(db).count({})
                # will count ONLY active users.
                default_query = {'is_active': True}

    """

    @classmethod
    def q(cls, db, session=None):
        """Return queryset object.

        Args:
            db: Motor database object.
            session: Motor client session object.

        Returns:
            MotorQuerySet: Queryset object.
        """
        return cls.meta.queryset(cls, db, session=session)

    @classmethod
    def coll(cls, db):
        """Return raw collection object.

        Args:
            db: Motor database object.

        Returns:
            MotorCollection: Raw Motor collection object.
        """
        return cls.meta.collection(db)

    @classmethod
    async def create(cls, db, session=None, **kwargs):
        """Create document in mongodb.

        Args:
            db: Database instance.
            session: Motor session object.
            **kwargs: Document's fields values.

        Returns:
            Created document instance.

        Raises:
            ValidationError: If some fields are not valid.
        """
        warnings.warn("Use `create` method of `queryset` instead",
                      DeprecationWarning,
                      stacklevel=2)

        inst = cls.from_data(kwargs)
        return await inst.save(db, do_insert=True, session=session)

    async def save(self, db, do_insert=False, session=None):
        """Save document in mongodb.

        Args:
            db: Database instance.
            do_insert (bool): If ``True`` always perform ``insert_one``, else
                perform ``replace_one`` with ``upsert=True``.
            session: Motor session object.
        """
        data = self.to_mongo()
        if do_insert:
            await self.__class__.q(db, session=session).insert_one(data)
        else:
            await self.__class__.q(db, session=session).replace_one(
                    {'_id': data['_id']},
                    data, upsert=True)

        return self

    async def reload(self, db, session=None):
        """Reload current object from mongodb."""
        cls = self.__class__
        data = await cls.coll(db).find_one(self.query_id, session=session)
        self._set_mongo_data(data)
        return self

    async def update(self, db, update_document, session=None):
        """Update current object using query.

        Usage:

        .. code-block:: python

            class User(Document):
                name = StrField()
                value = IntField(default=0)

            async def go(db):
                u = await User(name='xxx').save(db)
                await u.update(db,
                               {'$set': {User.name.s: 'yyy'},
                                '$inc': {User.value.s: 1}})

        """
        qs = self.__class__.q(db, session=session)
        count = await qs.update_one(self.query_id, update_document)
        # TODO: maybe we should return number of updates or raise if it's 0.
        if count > 0:
            await self.reload(db, session=session)

        return self

    async def delete(self, db, session=None):
        """Delete current object from db."""
        qs = self.__class__.q(db, session=session)
        return await qs.delete_one(self.query_id)

    @property
    def query_id(self):
        return {'_id': self.__class__._id.to_mongo(self._id)}

    @classmethod
    async def create_collection(self, db, session=None):
        """Create collection for documents.

        Args:
            db: Database object.

        Returns:
            Collection object.
        """
        return await db.create_collection(
            self.meta.collection_name,
            read_preference=self.meta.read_preference,
            read_concern=self.meta.read_concern,
            write_concern=self.meta.write_concern,
            codec_options=self.meta.codec_options,
            session=session)


class EmbeddedDocument(BaseDocument, metaclass=EmbeddedDocumentMeta):
    """Base class for embedded documents."""
