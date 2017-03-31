import pytest
from bson import ObjectId

from aiomongodel import Document, EmbeddedDocument
from aiomongodel.errors import ValidationError
from aiomongodel.fields import (
    FloatField, StrField, IntField, EmbDocField, RefField, ListField)


class EmbDoc(EmbeddedDocument):
    emb_float = FloatField()


class RefDoc(Document):
    pass


class Doc(Document):
    str_field = StrField(regexp=r'[abc]+')
    int_field = IntField(gt=0, lt=10)
    emb_field = EmbDocField(EmbDoc)
    lst_field = ListField(RefField(RefDoc), min_length=1, max_length=1)


@pytest.mark.parametrize('data, expected', [
    ({
        'str_field': 'd',
        'int_field': 15,
        'emb_field': {'emb_float': 'xxx'},
        'lst_field': []
    }, {
        'str_field': "does not match pattern [abc]+",
        'int_field': 'value should be less than 10',
        'emb_field': {'emb_float': "value can't be converted to float"},
        'lst_field': 'list length is less than 1'
    }),
    ({
        'str_field': 'a',
        'int_field': 5,
        'emb_field': {'wrong': 1.6},
        'lst_field': 1
    }, {
        'emb_field': {'emb_float': 'field is required'},
        'lst_field': 'value is not a list'
    }),
    ({
        'str_field': 'a',
        'int_field': 5,
        'emb_field': 1,
        'lst_field': [1]
    }, {
        'emb_field': "value can't be converted to EmbDoc",
        'lst_field': {0: 'value is not ObjectId'}
    }),
    ({
        'int_field': 5,
        'emb_field': {'emb_float': 1.6},
        'lst_field': [ObjectId()]
    }, {
        'str_field': 'field is required',
    }),
])
def test_validation_errors(data, expected):
    with pytest.raises(ValidationError) as excinfo:
        Doc.from_data(data)

    err = excinfo.value.as_dict()
    assert err == expected
