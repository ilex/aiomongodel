import pytest

from datetime import datetime

from bson import ObjectId

from aiomongodel import Document, EmbeddedDocument
from aiomongodel.errors import ValidationError
from aiomongodel.fields import (
    AnyField, StrField, IntField, FloatField, BoolField, DateTimeField,
    ObjectIdField, EmbDocField, ListField, RefField, SynonymField)
from aiomongodel.utils import _Empty


class EmbDoc(EmbeddedDocument):
    int_field = IntField(required=True)


class WrongEmbDoc(EmbeddedDocument):
    wrong = StrField(required=True)


class RefDoc(Document):
    str_field = StrField(required=False)


class WrongRefDoc(Document):
    wrong = IntField(required=False)


dt = datetime.strptime('1985-09-14 12:00:00', '%Y-%m-%d %H:%M:%S')
ref_doc = RefDoc(_id=ObjectId('58ce6d537e592254b67a503d'), str_field='xxx')
emb_doc = EmbDoc(int_field=1)


FIELD_DEFAULT = [
    (AnyField, 'xxx'),
    (StrField, 'xxx'),
    (IntField, 13),
    (FloatField, 1.3),
    (BoolField, True),
    (DateTimeField, dt),
    (ObjectIdField, ObjectId('58ce6d537e592254b67a503d'))
]


@pytest.mark.parametrize('field, wrong_value', [
    (StrField(required=True, default=''), 1),
    (IntField(required=True, default=0), 'xxx'),
    (IntField(required=True, default=0), 1.3),
    (FloatField(required=True, default=0.0), 'xxx'),
    (BoolField(required=True, default=True), 5),
    (DateTimeField(required=True, default=datetime.utcnow()), 'xxx'),
    (ObjectIdField(required=True, default=ObjectId()), 'xxx'),
    (RefField(RefDoc, required=True, default=ObjectId()), 'xxx'),
    (EmbDocField(EmbDoc, required=True, default=EmbDoc(int_field=1)), 1),
    (EmbDocField(EmbDoc, required=True, default=EmbDoc(int_field=1)), {}),
    (EmbDocField(EmbDoc, required=True, default=EmbDoc(int_field=1)),
        RefDoc()),
    (ListField(IntField(), required=True, default=[]), 1),
    (ListField(IntField(), required=True, default=[]), 'xxx'),
    (ListField(IntField(), required=True, default=[]), ['xxx'])
])
def test_field_init_and_assign_wrong_value(field, wrong_value):
    class Doc(Document):
        value = field

    with pytest.raises(ValidationError):
        Doc(value=wrong_value)

    d = Doc()
    with pytest.raises(ValidationError):
        d.value = wrong_value


@pytest.mark.parametrize('field, expected', [
    (StrField(required=False), None),
    (IntField(required=False), None),
    (FloatField(required=False), None),
    (BoolField(required=False), None),
    (DateTimeField(required=False), None),
    (ObjectIdField(required=False), None),
    (EmbDocField(EmbDoc, required=False), None),
    (ListField(EmbDocField(EmbDoc), required=False), None),
    (RefField(RefDoc, required=False), None),
])
def test_field_not_exist_get_value(field, expected):
    class Doc(Document):
        value = field

    assert Doc().value is expected


@pytest.mark.parametrize('field, default', FIELD_DEFAULT)
def test_field_attributes(field, default):
    class Doc(Document):
        value = field(required=False)

    assert isinstance(Doc.value, field)
    assert Doc.value.name == 'value'
    assert Doc.value.mongo_name == 'value'
    assert Doc.value.s == 'value'
    assert Doc.value.required is False
    assert Doc.value.default is _Empty

    class DocWithMongo(Document):
        value = field(required=True, default=default, mongo_name='val')

    assert isinstance(DocWithMongo.value, field)
    assert DocWithMongo.value.name == 'value'
    assert DocWithMongo.value.mongo_name == 'val'
    assert DocWithMongo.value.s == 'val'
    assert DocWithMongo.value.required is True
    assert DocWithMongo.value.default == default


@pytest.mark.parametrize('field, default', FIELD_DEFAULT)
def test_field_default(field, default):
    class Doc(Document):
        value = field()

    assert Doc.value.default is _Empty

    class DocWithDefault(Document):
        value = field(required=True, default=default)

    assert DocWithDefault.value.default == default

    class DocWithCallableDefault(Document):
        value = field(required=True, default=lambda: default)

    assert DocWithCallableDefault.value.default == default


def test_compound_field_name():
    class EmbDoc(EmbeddedDocument):
        int_field = IntField(mongo_name='intf')

    class ComplexEmbDoc(EmbeddedDocument):
        emb_field = EmbDocField(EmbDoc, mongo_name='emb')

    class ComplexListDoc(EmbeddedDocument):
        lst_field = ListField(EmbDocField(ComplexEmbDoc))

    class Doc(Document):
        int_field = IntField()
        emb_field = EmbDocField(EmbDoc, mongo_name='emb')
        complex_emb_field = EmbDocField(ComplexEmbDoc, mongo_name='cmplx_emb')
        lst_field = ListField(EmbDocField(EmbDoc), mongo_name='lst')
        lst_int_field = ListField(IntField(), mongo_name='lst_int')
        complex_lst_emb_field = EmbDocField(ComplexListDoc, mongo_name='clef')

    assert EmbDoc.int_field.s == 'intf'
    assert Doc.int_field.s == 'int_field'
    assert Doc.emb_field.s == 'emb'
    assert Doc.complex_emb_field.s == 'cmplx_emb'
    assert Doc.lst_field.s == 'lst'
    assert Doc.lst_int_field.s == 'lst_int'
    assert Doc.emb_field.int_field.s == 'emb.intf'
    assert Doc.complex_emb_field.emb_field.s == 'cmplx_emb.emb'
    assert Doc.lst_field.int_field.s == 'lst.intf'
    assert Doc.complex_emb_field.emb_field.int_field.s == 'cmplx_emb.emb.intf'
    mn = 'clef.lst_field.emb.intf'
    assert (
        Doc.complex_lst_emb_field.lst_field.emb_field.int_field.s == mn)

    with pytest.raises(AttributeError):
        Doc.int_field.wrong_field.s

    with pytest.raises(AttributeError):
        Doc.emb_field.int_field.wrong_field.s

    with pytest.raises(AttributeError):
        Doc.lst_int_field.wrong_field.s

    with pytest.raises(AttributeError):
        Doc.complex_emb_field.emb_field.wrong.s

    with pytest.raises(AttributeError):
        Doc.complex_lst_emb_field.lst_field.wrong.s


def test_compound_field_document_class():
    class Doc(Document):
        emb = EmbDocField('test_fields.EmbDoc')
        ref = RefField('test_fields.RefDoc')
        lst_emb = ListField(EmbDocField('test_fields.EmbDoc'))
        lst_ref = ListField(RefField('test_fields.RefDoc'))
        lst_int = ListField(IntField())
        wrong_emb = EmbDocField('xxx')
        wrong_ref = RefField('xxx')
        wrong_lst_emb = ListField(EmbDocField('xxx'))
        wrong_emb_doc = EmbDocField('test_fields.RefDoc')
        wrong_ref_doc = RefField('test_fields.EmbDoc')

    assert Doc.emb.document_class is EmbDoc
    assert Doc.ref.document_class is RefDoc
    assert Doc.lst_emb.document_class is EmbDoc
    assert Doc.lst_ref.document_class is None
    assert Doc.lst_int.document_class is None

    with pytest.raises(ImportError):
        Doc.wrong_emb.document_class

    with pytest.raises(ImportError):
        Doc.wrong_lst_emb.document_class

    with pytest.raises(ImportError):
        Doc.wrong_ref.document_class

    with pytest.raises(TypeError):
        class WrongEmbDoc(Document):
            wrong_emb = EmbDocField(RefDoc)

    with pytest.raises(TypeError):
        class WrongRefDoc(Document):
            wrong_ref = RefField(EmbDoc)

    with pytest.raises(TypeError):
        Doc.wrong_ref_doc.document_class

    with pytest.raises(TypeError):
        Doc.wrong_emb_doc.document_class


@pytest.mark.parametrize('field, value, expected', [
    (AnyField(), '1', '1'),
    (AnyField(), 1, 1),
    (AnyField(), True, True),
    (StrField(), 'xxx', 'xxx'),
    (IntField(), 1, 1),
    (FloatField(), 13.0, pytest.approx(13.0)),
    (BoolField(), True, True),
    (BoolField(), False, False),
    (DateTimeField(), dt, dt),
    (ObjectIdField(),
        ObjectId('58ce6d537e592254b67a503d'),
        ObjectId('58ce6d537e592254b67a503d')),
    (EmbDocField(EmbDoc), emb_doc, {'int_field': 1}),
    (ListField(IntField()), [], []),
    (ListField(IntField()), [1, 2, 3], [1, 2, 3]),
    (ListField(EmbDocField(EmbDoc)), [emb_doc], [{'int_field': 1}]),
    (RefField(RefDoc),
        ObjectId('58ce6d537e592254b67a503d'),
        ObjectId('58ce6d537e592254b67a503d')),
    (RefField(RefDoc), ref_doc, ref_doc._id),
])
def test_field_to_son(field, value, expected):
    class Doc(Document):
        value = field

    assert Doc.value.to_son(value) == expected


FROM_DATA = [
    (AnyField(), '1', '1'),
    (AnyField(), 1, 1),
    (AnyField(), True, True),
    (StrField(), '', ''),
    (StrField(), 'xxx', 'xxx'),
    (StrField(), 1, ValidationError()),
    (StrField(), True, ValidationError()),
    (StrField(allow_blank=False), '', ValidationError()),
    (IntField(), 1, 1),
    (IntField(), '1', 1),
    (IntField(), 'xxx', ValidationError()),
    (IntField(), 1.3, ValidationError()),
    (IntField(gte=1, lte=13), 1, 1),
    (IntField(gte=1, lte=13), 13, 13),
    (IntField(gte=1, lte=13), 10, 10),
    (IntField(gte=1, lte=13), 0, ValidationError()),
    (IntField(gte=1, lte=13), 20, ValidationError()),
    (IntField(gt=1, lt=13), 10, 10),
    (IntField(gt=1, lt=13), 1, ValidationError()),
    (IntField(gt=1, lt=13), 13, ValidationError()),
    (IntField(gt=1, lt=13), 0, ValidationError()),
    (IntField(gt=1, lt=13), 20, ValidationError()),
    (FloatField(), 1, pytest.approx(1.0)),
    (FloatField(), 1.0, pytest.approx(1.0)),
    (FloatField(), '1.0', pytest.approx(1.0)),
    (FloatField(), '1', pytest.approx(1.0)),
    (FloatField(), 'xxx', ValidationError()),
    (FloatField(gt=1.0, lt=13.0), 10.0, pytest.approx(10.0)),
    (FloatField(gt=1.0, lt=13.0), 0.0, ValidationError()),
    (FloatField(gt=1.0, lt=13.0), 20.0, ValidationError()),
    (BoolField(), True, True),
    (BoolField(), False, False),
    (BoolField(), 13, ValidationError()),
    (DateTimeField(), dt, dt),
    (DateTimeField(), True, ValidationError()),
    (ObjectIdField(),
        ObjectId('58ce6d537e592254b67a503d'),
        ObjectId('58ce6d537e592254b67a503d')),
    (ObjectIdField(), '58ce6d537e592254b67a503d', ValidationError()),
    (ListField(IntField()), [], []),
    (ListField(IntField()), [1, 2, 3], [1, 2, 3]),
    (ListField(IntField()), ['1', '2', '3'], [1, 2, 3]),
    (ListField(IntField()), [0, 'xxx', 1], ValidationError()),
    (ListField(IntField(), min_length=3, max_length=5),
        [0, 1], ValidationError()),
    (ListField(IntField(), min_length=3, max_length=5), [0, 1, 2], [0, 1, 2]),
    (ListField(IntField(), min_length=3, max_length=5),
        [0, 1, 2, 3, 4, 5], ValidationError()),
    (ListField(RefField(RefDoc)), [ref_doc], [ref_doc]),
    (ListField(RefField(RefDoc)), [1], ValidationError()),
    (ListField(EmbDocField(EmbDoc)), [emb_doc], [emb_doc]),
    (ListField(EmbDocField(EmbDoc)), [1], ValidationError()),
    (RefField(RefDoc),
        ObjectId('58ce6d537e592254b67a503d'),
        ObjectId('58ce6d537e592254b67a503d')),
    (RefField(RefDoc), ref_doc, ref_doc),
    (RefField(RefDoc), 'xxx', ValidationError()),
    (RefField(RefDoc), WrongRefDoc(), ValidationError()),
    (EmbDocField(EmbDoc), emb_doc, emb_doc),
    (EmbDocField(EmbDoc), WrongEmbDoc(wrong='xxx'), ValidationError()),
    (EmbDocField(EmbDoc), 1, ValidationError()),
    (EmbDocField(EmbDoc), {'str_field': 1}, ValidationError()),
    (EmbDocField(EmbDoc), RefDoc(), ValidationError())
]


@pytest.mark.parametrize('field, value, expected', FROM_DATA)
def test_field_from_data(field, value, expected):
    class Doc(Document):
        value = field

    if isinstance(expected, Exception):
        with pytest.raises(type(expected)):
            Doc.value.from_data(value)
    else:
        assert Doc.value.from_data(value) == expected


@pytest.mark.parametrize('field, value, expected', FROM_DATA)
def test_field_init(field, value, expected):
    class Doc(Document):
        value = field

    if isinstance(expected, Exception):
        with pytest.raises(type(expected)):
            Doc(value=value)
    else:
        assert Doc(value=value).value == expected


@pytest.mark.parametrize('field, value, expected', FROM_DATA)
def test_field_assign(field, value, expected):
    class Doc(Document):
        value = field

    d = Doc(_empty=True)
    if isinstance(expected, Exception):
        with pytest.raises(type(expected)):
            d.value = value
    else:
        d.value = value
        assert d.value == expected


def test_emb_doc_field():
    class Doc(Document):
        emb_field = EmbDocField(EmbDoc)

    assert isinstance(Doc(emb_field={'int_field': 1}).emb_field, EmbDoc)

    d = Doc(_empty=True)
    d.emb_field = {'int_field': 1}
    assert isinstance(d.emb_field, EmbDoc)

    assert isinstance(Doc.emb_field.from_data({'int_field': 1}), EmbDoc)

    d = Doc.from_son({'emb_field': {'int_field': 1}})
    assert isinstance(d.emb_field, EmbDoc)
    assert d.emb_field.int_field == 1


def test_list_field():
    with pytest.raises(TypeError):
        class Doc(Document):
            lst_field = ListField(int)


class DocWithSynonym(Document):
    _id = StrField(required=True, allow_blank=False)
    name = SynonymField(_id)


class DocWithSynonymStr(Document):
    _id = StrField(required=True, allow_blank=False)
    name = SynonymField('_id')


@pytest.mark.parametrize('Doc', [DocWithSynonym, DocWithSynonymStr])
def test_synonym_field(Doc):
    assert Doc.name is Doc._id
    assert Doc.name.name == '_id'
    assert Doc.name.s == '_id'

    assert Doc.meta.fields == {'_id': Doc._id}

    d = Doc(_id='totti')
    assert d.name == 'totti'

    d.name = 'francesco'
    assert d._id == 'francesco'
