import re
from datetime import datetime
from decimal import Decimal

import pytest
from bson import ObjectId, Decimal128

from aiomongodel import Document, EmbeddedDocument
from aiomongodel.errors import ValidationError
from aiomongodel.fields import (
    AnyField, StrField, IntField, FloatField, BoolField, DateTimeField,
    ObjectIdField, EmbDocField, ListField, RefField, EmailField,
    DecimalField, SynonymField)
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
wrong_ref_doc = RefDoc(_id=ObjectId('58ce6d537e592254b67a503d'), wrong=1)
wrong_emb_doc = EmbDoc(wrong='xxx')


FIELD_DEFAULT = [
    (AnyField, 'xxx'),
    (StrField, 'xxx'),
    (IntField, 13),
    (FloatField, 1.3),
    (BoolField, True),
    (DateTimeField, dt),
    (ObjectIdField, ObjectId('58ce6d537e592254b67a503d')),
    (EmailField, 'totti@example.com'),
    (DecimalField, Decimal('0.005')),
]


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
    (EmailField(required=False), None),
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
    assert Doc.value.choices is None
    assert Doc.value.allow_none is False

    class DocWithMongo(Document):
        value = field(required=True, default=default, mongo_name='val',
                      choices=[default], allow_none=True)

    assert isinstance(DocWithMongo.value, field)
    assert DocWithMongo.value.name == 'value'
    assert DocWithMongo.value.mongo_name == 'val'
    assert DocWithMongo.value.s == 'val'
    assert DocWithMongo.value.required is True
    assert DocWithMongo.value.default == default
    assert DocWithMongo.value.choices == {default}
    assert DocWithMongo.value.allow_none is True


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
    (AnyField(), None, None),
    (StrField(), 'xxx', 'xxx'),
    (StrField(), None, None),
    (IntField(), 1, 1),
    (IntField(), None, None),
    (FloatField(), 13.0, pytest.approx(13.0)),
    (FloatField(), None, None),
    (BoolField(), True, True),
    (BoolField(), False, False),
    (BoolField(), None, None),
    (DateTimeField(), dt, dt),
    (DateTimeField(), None, None),
    (ObjectIdField(),
        ObjectId('58ce6d537e592254b67a503d'),
        ObjectId('58ce6d537e592254b67a503d')),
    (ObjectIdField(), None, None),
    (EmbDocField(EmbDoc), emb_doc, {'int_field': 1}),
    (EmbDocField(EmbDoc), None, None),
    (ListField(IntField()), [], []),
    (ListField(IntField()), [1, 2, 3], [1, 2, 3]),
    (ListField(IntField()), None, None),
    (ListField(EmbDocField(EmbDoc)), [emb_doc], [{'int_field': 1}]),
    (ListField(EmbDocField(EmbDoc)), None, None),
    (RefField(RefDoc),
        ObjectId('58ce6d537e592254b67a503d'),
        ObjectId('58ce6d537e592254b67a503d')),
    (RefField(RefDoc), ref_doc, ref_doc._id),
    (RefField(RefDoc), None, None),
    (EmailField(), 'totti@example.com', 'totti@example.com'),
    (EmailField(), None, None),
    (DecimalField(), Decimal('0.005'), Decimal128(Decimal('0.005'))),
    (DecimalField(), None, None),
])
def test_field_to_mongo(field, value, expected):
    class Doc(Document):
        value = field

    assert Doc.value.to_mongo(value) == expected


@pytest.mark.parametrize('field, value, expected', [
    (AnyField(), '1', '1'),
    (AnyField(), 1, 1),
    (AnyField(), True, True),
    (AnyField(), None, None),
    (StrField(), 'xxx', 'xxx'),
    (StrField(), None, None),
    (IntField(), 1, 1),
    (IntField(), None, None),
    (FloatField(), 13.0, pytest.approx(13.0)),
    (FloatField(), None, None),
    (BoolField(), True, True),
    (BoolField(), False, False),
    (BoolField(), None, None),
    (DateTimeField(), dt, dt),
    (DateTimeField(), None, None),
    (ObjectIdField(),
        ObjectId('58ce6d537e592254b67a503d'),
        ObjectId('58ce6d537e592254b67a503d')),
    (ObjectIdField(), None, None),
    (ListField(IntField()), [], []),
    (ListField(IntField()), [1, 2, 3], [1, 2, 3]),
    (ListField(IntField()), None, None),
    (ListField(IntField()), [None], [None]),
    (RefField(RefDoc),
        ObjectId('58ce6d537e592254b67a503d'),
        ObjectId('58ce6d537e592254b67a503d')),
    (RefField(RefDoc), None, None),
    (EmailField(), 'totti@example.com', 'totti@example.com'),
    (EmailField(), None, None),
    (DecimalField(), Decimal128(Decimal('0.005')), Decimal('0.005')),
    (DecimalField(), float(0.005), Decimal('0.005')),
    (DecimalField(), str(0.005), Decimal('0.005')),
    (DecimalField(), None, None),
    (EmbDocField(EmbDoc, allow_none=True), None, None)
])
def test_field_from_mongo(field, value, expected):
    class Doc(Document):
        value = field

    assert Doc.value.from_mongo(value) == expected


FROM_DATA = [
    (AnyField(), '1', '1'),
    (AnyField(), 1, 1),
    (AnyField(), True, True),
    (StrField(), '', ''),
    (StrField(), 'xxx', 'xxx'),
    (StrField(choices=('xxx', 'yyy')), 'xxx', 'xxx'),
    (StrField(), 1, '1'),
    (StrField(), True, 'True'),
    (StrField(allow_blank=False), '', ''),
    (StrField(choices=('xxx', 'yyy')), 'zzz', 'zzz'),
    (StrField(choices=('xxx', 'yyy')), 1, '1'),
    (IntField(), 1, 1),
    (IntField(), '1', 1),
    (IntField(choices=[*range(10)]), 5, 5),
    (IntField(choices=[*range(10)]), 'xxx', 'xxx'),
    (IntField(choices=[*range(10)]), 100, 100),
    (IntField(), 'xxx', 'xxx'),
    (IntField(), 1.3, 1),
    (IntField(gte=1, lte=13), 1, 1),
    (IntField(gte=1, lte=13), 13, 13),
    (IntField(gte=1, lte=13), 10, 10),
    (IntField(gte=1, lte=13), 0, 0),
    (IntField(gte=1, lte=13), 20, 20),
    (IntField(gt=1, lt=13), 10, 10),
    (IntField(gt=1, lt=13), 1, 1),
    (IntField(gt=1, lt=13), 13, 13),
    (IntField(gt=1, lt=13), 0, 0),
    (IntField(gt=1, lt=13), 20, 20),
    (FloatField(), 1, pytest.approx(1.0)),
    (FloatField(), 1.0, pytest.approx(1.0)),
    (FloatField(), '1.0', pytest.approx(1.0)),
    (FloatField(), '1', pytest.approx(1.0)),
    (FloatField(), 'x', 'x'),
    (FloatField(gt=1.0, lt=13.0), 10.0, pytest.approx(10.0)),
    (FloatField(gt=1.0, lt=13.0), 0.0, pytest.approx(0.0)),
    (FloatField(gt=1.0, lt=13.0), 20.0, pytest.approx(20.0)),
    (BoolField(), True, True),
    (BoolField(), False, False),
    (BoolField(), 13, True),
    (DateTimeField(), dt, dt),
    (DateTimeField(), True, True),
    (ObjectIdField(),
        ObjectId('58ce6d537e592254b67a503d'),
        ObjectId('58ce6d537e592254b67a503d')),
    (ObjectIdField(), '58ce6d537e592254b67a503d',
        ObjectId('58ce6d537e592254b67a503d')),
    (ListField(IntField()), [], []),
    (ListField(IntField()), [1, 2, 3], [1, 2, 3]),
    (ListField(IntField()), ['1', '2', '3'], [1, 2, 3]),
    (ListField(IntField()), [0, 'xxx', 1], [0, 'xxx', 1]),
    (ListField(IntField(), min_length=3, max_length=5), [0, 1], [0, 1]),
    (ListField(IntField(), min_length=3, max_length=5), [0, 1, 2], [0, 1, 2]),
    (ListField(IntField(), min_length=3, max_length=5),
        [0, 1, 2, 3, 4, 5], [0, 1, 2, 3, 4, 5]),
    (ListField(RefField(RefDoc)), [ref_doc], [ref_doc]),
    (ListField(RefField(RefDoc)), [1], [1]),
    (ListField(EmbDocField(EmbDoc)), [emb_doc], [emb_doc]),
    (ListField(EmbDocField(EmbDoc)), [1], [1]),
    (RefField(RefDoc),
        ObjectId('58ce6d537e592254b67a503d'),
        ObjectId('58ce6d537e592254b67a503d')),
    (RefField(RefDoc), ref_doc, ref_doc),
    (RefField(RefDoc), wrong_ref_doc, wrong_ref_doc),
    (RefField(RefDoc), 'xxx', 'xxx'),
    (EmbDocField(EmbDoc), emb_doc, emb_doc),
    (EmbDocField(EmbDoc), wrong_emb_doc, wrong_emb_doc),
    (EmbDocField(EmbDoc), 1, 1),
    (EmbDocField(EmbDoc), ref_doc, ref_doc),
    (EmailField(), 'totti@example.com', 'totti@example.com'),
    (EmailField(), 'example.com', 'example.com'),
    (EmailField(), '@example.com', '@example.com'),
    (EmailField(), 'totti@example', 'totti@example'),
    (EmailField(), 1, '1'),
    (DecimalField(), Decimal(1), Decimal(1)),
    (DecimalField(), '0.005', Decimal('0.005')),
    (DecimalField(gte=1, lte=13), '1.0', Decimal('1.0')),
    (DecimalField(gte=1, lte=13), '13', Decimal('13')),
    (DecimalField(gte=1, lte=13), '10.5', Decimal('10.5')),
    (DecimalField(gte=Decimal(1), lte=13), 0, 0),
    (DecimalField(gte=1, lte=13), Decimal('20.5'), Decimal('20.5')),
    (DecimalField(gt=1, lt=13), 10, Decimal(10)),
    (DecimalField(gt=1, lt=13), 1, 1),
    (DecimalField(gt=1, lt=Decimal('13.0')), 13, 13),
    (DecimalField(gt=1, lt=Decimal('13.0')), Decimal('0'), Decimal('0')),
    (DecimalField(gt=1, lt=13), Decimal('20'), Decimal('20'))
]


@pytest.mark.parametrize('field, value, expected', FROM_DATA)
def test_field_from_data(field, value, expected):
    class Doc(Document):
        value = field

    assert Doc.value.from_data(value) == expected


@pytest.mark.parametrize('field, value, expected', FROM_DATA)
def test_field_init(field, value, expected):
    class Doc(Document):
        value = field

    assert Doc(value=value).value == expected


@pytest.mark.parametrize('field, value, expected', FROM_DATA)
def test_field_assign(field, value, expected):
    class Doc(Document):
        value = field

    d = Doc(_empty=True)
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

    d = Doc.from_mongo({'emb_field': {'int_field': 1}})
    assert isinstance(d.emb_field, EmbDoc)
    assert d.emb_field.int_field == 1


def test_list_field():
    with pytest.raises(TypeError):
        class Doc(Document):
            lst_field = ListField(int)


def test_filed_choices():
    class Doc(Document):
        set_choices = StrField(choices={'xxx', 'yyy'})
        dict_choices = StrField(choices={'xxx': 'AAA', 'yyy': 'BBB'})

    d = Doc(set_choices='xxx', dict_choices='yyy')
    d.validate()

    d = Doc(set_choices='AAA', dict_choices='BBB')
    with pytest.raises(ValidationError) as excinfo:
        d.validate()

    assert excinfo.value.as_dict() == {
        'set_choices': 'value does not match any variant',
        'dict_choices': 'value does not match any variant',
    }


@pytest.mark.parametrize('field, value, expected', [
    # AnyField
    (AnyField(), '1', None),
    (AnyField(), 1, None),
    (AnyField(), True, None),
    (AnyField(allow_none=True), None, None),
    (AnyField(allow_none=False), None,
        ValidationError('none value is not allowed')),
    (AnyField(choices={'xxx', 'yyy'}), 'xxx', None),
    (AnyField(choices={'xxx', 'yyy'}), 1,
        ValidationError('value does not match any variant')),
    # StrField
    (StrField(), 'xxx', None),
    (StrField(allow_none=True), None, None),
    (StrField(allow_blank=True), '', None),
    (StrField(choices=('xxx', 'yyy')), 'xxx', None),
    (StrField(choices=('xxx', 'yyy'), max_length=2), 'xxx', None),
    (StrField(choices=('xxx', 'yyy'), regex=r'zzz'), 'xxx', None),
    (StrField(regex=r'[abc]+'), 'aa', None),
    (StrField(regex=re.compile(r'[abc]+')), 'aa', None),
    (StrField(min_length=2, max_length=3), 'aa', None),
    (StrField(allow_none=False), None,
        ValidationError('none value is not allowed')),
    (StrField(), 1, ValidationError("invalid value type")),
    (StrField(allow_none=True), True, ValidationError("invalid value type")),
    (StrField(allow_blank=False), '',
        ValidationError("blank value is not allowed")),
    (StrField(choices=('xxx', 'yyy')), 'zzz',
        ValidationError("value does not match any variant")),
    (StrField(choices=('xxx', 'yyy')), 1,
        ValidationError("invalid value type")),
    (StrField(regex=r'[abc]+'), 'd',
        ValidationError('value does not match pattern [abc]+')),
    (StrField(regex=re.compile(r'[abc]+')), 'd',
        ValidationError('value does not match pattern [abc]+')),
    (StrField(min_length=2, max_length=3), 'a',
        ValidationError('length is less than 2')),
    (StrField(min_length=2, max_length=3), 'aaaa',
        ValidationError('length is greater than 3')),
    # IntField
    (IntField(), 1, None),
    (IntField(allow_none=True), None, None),
    (IntField(choices=[*range(10)]), 5, None),
    (IntField(choices=[*range(10)]), 'xxx',
        ValidationError("invalid value type")),
    (IntField(choices=[*range(10)]), 100,
        ValidationError("value does not match any variant")),
    (IntField(), 'xxx', ValidationError("invalid value type")),
    (IntField(gte=1, lte=13), 1, None),
    (IntField(gte=1, lte=13), 13, None),
    (IntField(gte=1, lte=13), 10, None),
    (IntField(gte=1, lte=13), 0, ValidationError('value is less than 1')),
    (IntField(gte=1, lte=13), 20,
        ValidationError('value is greater than 13')),
    (IntField(gt=1, lt=13), 10, None),
    (IntField(gt=1, lt=13), 1,
        ValidationError('value should be greater than 1')),
    (IntField(gt=1, lt=13), 13,
        ValidationError('value should be less than 13')),
    (IntField(gt=1, lt=13), 0,
        ValidationError('value should be greater than 1')),
    (IntField(gt=1, lt=13), 20,
        ValidationError('value should be less than 13')),
    # FloatField
    (FloatField(), 1.0, None),
    (FloatField(allow_none=True), None, None),
    (FloatField(allow_none=False), None,
        ValidationError('none value is not allowed')),
    (FloatField(), 'x', ValidationError("invalid value type")),
    (FloatField(), '1.0', ValidationError("invalid value type")),
    (FloatField(gt=1.0, lt=13.0), 10.0, None),
    (FloatField(gt=1.0, lt=13.0), 0.0,
        ValidationError("value should be greater than 1.0")),
    (FloatField(gt=1.0, lt=13.0), 20.0,
        ValidationError("value should be less than 13.0")),
    # BoolField
    (BoolField(), True, None),
    (BoolField(), False, None),
    (BoolField(allow_none=True), None, None),
    (BoolField(allow_none=False), None,
        ValidationError('none value is not allowed')),
    (BoolField(), 13, ValidationError('invalid value type')),
    # DateTimeField
    (DateTimeField(), dt, None),
    (DateTimeField(allow_none=True), None, None),
    (DateTimeField(allow_none=False), None,
        ValidationError('none value is not allowed')),
    (DateTimeField(), True, ValidationError('invalid value type')),
    # ObjectIdField
    (ObjectIdField(), ObjectId('58ce6d537e592254b67a503d'), None),
    (ObjectIdField(allow_none=True), None, None),
    (ObjectIdField(allow_none=False), None,
        ValidationError('none value is not allowed')),
    (ObjectIdField(), '58ce6d537e592254b67a503d',
        ValidationError('invalid value type')),
    # ListField
    (ListField(IntField()), [], None),
    (ListField(IntField()), [1, 2, 3], None),
    (ListField(IntField(), allow_none=True), None, None),
    (ListField(IntField(), allow_none=False), None,
        ValidationError('none value is not allowed')),
    (ListField(IntField()), [0, 'xxx', 1],
        ValidationError({1: ValidationError('invalid value type')})),
    (ListField(IntField(), min_length=3, max_length=5),
        [0, 1], ValidationError('list length is less than 3')),
    (ListField(IntField(), min_length=3, max_length=5), [0, 1, 2], None),
    (ListField(IntField(), min_length=3, max_length=5),
        [0, 1, 2, 3, 4, 5], ValidationError('list length is greater than 5')),
    # (ListField(RefField(RefDoc)), [ref_doc], None),
    (ListField(RefField(RefDoc)), [1],
        ValidationError({0: ValidationError('invalid value type')})),
    (ListField(EmbDocField(EmbDoc)), [emb_doc], None),
    (ListField(EmbDocField(EmbDoc)), [1],
        ValidationError({0: ValidationError('invalid value type')})),
    # RefField
    (RefField(RefDoc), ObjectId('58ce6d537e592254b67a503d'), None),
    (RefField(RefDoc), ref_doc, None),
    (RefField(RefDoc, allow_none=True), None, None),
    (RefField(RefDoc, allow_none=False), None,
        ValidationError('none value is not allowed')),
    (RefField(RefDoc), 'xxx', ValidationError('invalid value type')),
    (RefField(RefDoc), WrongRefDoc(),
        ValidationError('invalid value type')),
    # EmbDocField
    (EmbDocField(EmbDoc), emb_doc, None),
    (EmbDocField(EmbDoc, allow_none=True), None, None),
    (EmbDocField(EmbDoc, allow_none=False), None,
        ValidationError('none value is not allowed')),
    (EmbDocField(EmbDoc), WrongEmbDoc(wrong='xxx'),
        ValidationError("invalid value type")),
    (EmbDocField(EmbDoc), 1,
        ValidationError("invalid value type")),
    (EmbDocField(EmbDoc), {'str_field': 1},
        ValidationError("invalid value type")),
    (EmbDocField(EmbDoc), EmbDoc(int_field='xxx'),
        ValidationError({'int_field': ValidationError('invalid value type')})),
    (EmbDocField(EmbDoc), RefDoc(),
        ValidationError("invalid value type")),
    # EmailField
    (EmailField(), 'totti@example.com', None),
    (EmailField(allow_none=True), None, None),
    (EmailField(allow_none=False), None,
        ValidationError('none value is not allowed')),
    (EmailField(), 'example.com',
        ValidationError("value is not a valid email address")),
    (EmailField(), '@example.com',
        ValidationError("value is not a valid email address")),
    (EmailField(), 'totti@example',
        ValidationError("value is not a valid email address")),
    (EmailField(), 1,
        ValidationError("invalid value type")),
    (EmailField(max_length=10), 'totti@example.com',
        ValidationError("length is greater than 10")),
    # DecimalField
    (DecimalField(), Decimal(1), None),
    (DecimalField(allow_none=True), None, None),
    (DecimalField(allow_none=False), None,
        ValidationError('none value is not allowed')),
    (DecimalField(gte=1, lte=13), Decimal('1.0'), None),
    (DecimalField(gte=1, lte=13), Decimal('13'), None),
    (DecimalField(gte=1, lte=13), Decimal('10.5'), None),
    (DecimalField(gte=Decimal(1), lte=13), Decimal(0),
        ValidationError('value is less than 1')),
    (DecimalField(gte=1, lte=13), Decimal('20.5'),
        ValidationError('value is greater than 13')),
    (DecimalField(gt=1, lt=13), Decimal(10), None),
    (DecimalField(gt=1, lt=13), Decimal(1),
        ValidationError('value should be greater than 1')),
    (DecimalField(gt=1, lt=Decimal('13.0')), Decimal(13),
        ValidationError('value should be less than 13.0')),
    (DecimalField(gt=1, lt=Decimal('13.0')), Decimal('0'),
        ValidationError('value should be greater than 1')),
    (DecimalField(gt=1, lt=13), Decimal('20'),
        ValidationError('value should be less than 13')),
])
def test_fields_validation(field, value, expected):
    if expected is not None:
        with pytest.raises(ValidationError) as excinfo:
            field.validate(value)
        assert excinfo.value.as_dict() == expected.as_dict()
    else:
        # should be no errors
        field.validate(value)


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
