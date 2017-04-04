import pytest
from datetime import datetime

import trafaret as t
from bson import ObjectId
from pymongo import IndexModel, ASCENDING, WriteConcern

from aiomongodel import Document
from aiomongodel.document import Meta
from aiomongodel.errors import DocumentNotFoundError
from aiomongodel.fields import StrField, ObjectIdField, SynonymField, IntField
from aiomongodel.queryset import MotorQuerySet

from models import User, Post, Comment


async def test_create(db):
    u = await User.create(db, name='francesco')
    assert u._id == 'francesco'
    assert u.name == 'francesco'
    assert u.active is True
    assert u.posts == []
    assert u.data is None

    data = await db.user.find_one({'_id': 'francesco'})
    assert u.to_son() == data


async def test_save(db):
    u = await User(name='francesco').save(db)
    assert u._id == 'francesco'
    assert u.name == 'francesco'
    assert u.active is True
    assert u.posts == []
    assert u.data is None

    data = await db.user.find_one({'_id': 'francesco'})
    assert u.to_son() == data


async def test_save_do_insert(db):
    u = await User(name='francesco').save(db, do_insert=True)
    assert u._id == 'francesco'
    assert u.name == 'francesco'
    assert u.active is True
    assert u.posts == []
    assert u.data is None

    data = await db.user.find_one({'_id': 'francesco'})
    assert u.to_son() == data


async def test_modify_and_save(db):
    u = await User(name='francesco').save(db)
    _id = u._id

    u.active = False
    u.data = 10

    await u.save(db)
    assert u.name == 'francesco'
    assert u.active is False
    assert u.data == 10

    await u.reload(db)
    assert u.name == 'francesco'
    assert u.active is False
    assert u.data == 10

    data = await db.user.find_one({'_id': _id})
    assert u.to_son() == data


async def test_get(db):
    await User(name='francesco').save(db)
    await User(name='totti', active=False, data=10).save(db)
    await User(name='xxx').save(db)

    u = await User.q(db).get('totti')
    assert u.name == 'totti'
    assert u.active is False
    assert u.data == 10


async def test_reload(db):
    u = await User(name='francesco', active=True).save(db)

    u.active = False
    u.data = 10
    assert u.data == 10
    assert u.active is False

    await u.reload(db)
    assert u.data is None
    assert u.active is True


async def test_update(db):
    u = await User(name='totti').save(db)

    post = await Post(title='Francesco Totti', author=u).save(db)

    assert isinstance(post._id, ObjectId)
    assert post.title == 'Francesco Totti'
    assert post.author == u

    await post.reload(db)
    assert post.author == 'totti'

    await u.update(db, {'$push': {User.posts.s: post._id}})
    assert u.posts == [post._id]


async def test_delete(db):
    await User(name='totti').save(db)
    await User(name='francesco').save(db)

    u = await User.q(db).get('totti')
    assert u._id == 'totti'

    await u.delete(db)
    with pytest.raises(DocumentNotFoundError):
        u = await User.q(db).get('totti')

    u = await User.q(db).get('francesco')
    assert u._id == 'francesco'


async def test_raw_collection(db):
    await User(name='totti', data=10).save(db)

    u = await User.coll(db).find_one({'_id': 'totti'})
    assert u == {'_id': 'totti', 'active': True, 'posts': [], 'data': 10}


def test_document_with_implicit_id():
    class Doc(Document):
        pass

    assert isinstance(Doc._id, ObjectIdField)
    assert Doc._id.required is True
    doc = Doc()
    assert isinstance(doc._id, ObjectId)


def test_document_with_explicit_id():
    class Doc(Document):
        _id = ObjectIdField(required=True, default=lambda: ObjectId())

    assert isinstance(Doc._id, ObjectIdField)
    doc = Doc()
    assert isinstance(doc._id, ObjectId)


def test_document_with_explicit_str_id():
    class Doc(Document):
        _id = StrField(required=True, allow_blank=False)

    assert isinstance(Doc._id, StrField)

    with pytest.raises(ValueError) as excinfo:
        class DocWrongId(Document):
            _id = StrField(required=False)
    expected = "'DocWrongId._id' field should be required."
    assert str(excinfo.value) == expected


def test_to_son():
    u = User(name='totti')
    assert u.to_son() == {'_id': 'totti', 'active': True, 'posts': []}

    comment = Comment(_id=ObjectId('58ce6d537e592254b67a503d'),
                      body='Comment',
                      author=u)
    assert comment.to_son() == {'_id': ObjectId('58ce6d537e592254b67a503d'),
                                'body': 'Comment',
                                'user': 'totti'}

    post = Post(title='Title', author='totti', comments=[comment])
    son = post.to_son()
    assert isinstance(son['_id'], ObjectId)
    assert son['title'] == 'Title'
    assert son['views'] == 0
    assert isinstance(son['created'], datetime)
    assert son['rate'] == pytest.approx(0.0)
    assert son['author'] == 'totti'
    assert son['comments'] == [{'_id': ObjectId('58ce6d537e592254b67a503d'),
                                'body': 'Comment',
                                'user': 'totti'}]


def test_document_meta():
    class DocWithoutMeta(Document):
        _id = StrField(required=True)
        name = SynonymField(_id)

    meta = DocWithoutMeta.meta
    assert isinstance(meta, Meta)
    assert meta.query_class is MotorQuerySet
    assert meta.collection_name == 'doc_without_meta'
    assert len(meta.fields) == 1
    assert isinstance(meta.fields['_id'], StrField)
    assert meta.fields_synonyms == {'_id': 'name'}
    assert meta.indexes is None
    assert meta.codec_options is None
    assert meta.read_preference is None
    assert meta.read_concern is None
    assert meta.write_concern is None
    assert meta.default_query == {}

    class DocWithMeta(Document):
        _id = StrField(required=True)
        value = IntField(required=True)
        name = SynonymField(_id)

        class Meta:
            collection_name = 'docs'
            indexes = [IndexModel([('value', ASCENDING)], name='value_index')]
            default_query = {'value': 1}
            write_concern = WriteConcern(w=0)

    meta = DocWithMeta.meta
    assert isinstance(meta, Meta)
    assert meta.query_class is MotorQuerySet
    assert meta.collection_name == 'docs'
    assert len(meta.fields) == 2
    assert isinstance(meta.fields['_id'], StrField)
    assert isinstance(meta.fields['value'], IntField)
    assert meta.fields_synonyms == {'_id': 'name'}
    assert len(meta.indexes) == 1
    assert meta.indexes[0].document['name'] == 'value_index'
    assert meta.codec_options is None
    assert meta.read_preference is None
    assert meta.read_concern is None
    assert isinstance(meta.write_concern, WriteConcern)
    assert meta.default_query == {'value': 1}


def test_document_meta_wrong_option():
    with pytest.raises(ValueError) as excinfo:
        class Doc(Document):
            class Meta:
                wrong = 'xxx'
                some = 1

    assert str(excinfo.value).startswith("Unrecognized Meta options:")


def test_validate():
    data = User.meta.trafaret.check(
        {'_id': 'totti', 'active': True, 'posts': [], 'data': 10})
    assert data == {'_id': 'totti', 'active': True, 'posts': [], 'data': 10}

    with pytest.raises(t.DataError):
        User.meta.trafaret.check({'_id': 'totti', 'posts': 4})

    post_data = {
        '_id': ObjectId(),
        'title': 'Title',
        'views': 1,
        'created': datetime.utcnow(),
        'rate': 1.6,
        'author': 'totti',
        'comments': [{'_id': ObjectId(), 'body': 'Comment', 'author': 'xxx'}]
    }
    assert Post.meta.trafaret.check(post_data) == post_data

    post_data['author'] = 1
    post_data['views'] = 'xxx'
    post_data['comments'][0]['_id'] = 'wrong'
    with pytest.raises(t.DataError):
        Post.meta.trafaret.check(post_data)
