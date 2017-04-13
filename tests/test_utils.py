import pytest

import aiomongodel
from aiomongodel import utils

CAMEL_TO_SNAKE = (
    ('EmbDocLoad', 'emb_doc_load'),
    ('EmbDocDBLoader', 'emb_doc_db_loader'),
    ('Emb', 'emb'),
    ('GPS', 'gps'),
    ('Emb100', 'emb100'),
    ('Emb100Doc', 'emb100_doc'),
    ('EmbDoc100', 'emb_doc100'),
    ('EmbDocGPS100Loader', 'emb_doc_gps100_loader')
)


@pytest.mark.parametrize('camel, snake', CAMEL_TO_SNAKE)
def test_snake_case(camel, snake):
    assert utils.snake_case(camel) == snake


def test_import_class():
    utils.CLASSES_CACHE = {}

    Document = utils.import_class('aiomongodel.document.Document')
    assert Document is aiomongodel.Document
    assert 'aiomongodel.document.Document' in utils.CLASSES_CACHE

    OtherDocument = utils.import_class('aiomongodel.document.Document')
    assert OtherDocument is Document

    utils.CLASSES_CACHE = {}


def test_import_class_invalid_value():
    with pytest.raises(ImportError) as excinfo:
        utils.import_class('Xxx')

    expected = "Import path should be absolute string, not 'Xxx'"
    assert str(excinfo.value) == expected

    with pytest.raises(ImportError) as excinfo:
        utils.import_class(1)

    expected = "Import path should be absolute string, not '1'"
    assert str(excinfo.value) == expected


def test_import_class_invalid_class_name():
    with pytest.raises(ImportError) as excinfo:
        utils.import_class('aiomongodel.WrongNameClass')

    expected = "No class named 'aiomongodel.WrongNameClass'"
    assert str(excinfo.value) == expected

    assert 'aiomongodel.WrongNameClass' not in utils.CLASSES_CACHE


def test_import_class_invalid_module_name():
    with pytest.raises(ImportError) as excinfo:
        utils.import_class('wrong.module.Document')

    expected = "No module named 'wrong'"
    assert str(excinfo.value) == expected

    assert 'wrong.module.Document' not in utils.CLASSES_CACHE
