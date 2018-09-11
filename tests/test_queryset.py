import sys
import textwrap

import pytest
from pymongo import ASCENDING, DESCENDING, WriteConcern
import pymongo.errors

from aiomongodel.errors import DocumentNotFoundError, DuplicateKeyError
from aiomongodel.queryset import MotorQuerySet, MotorQuerySetCursor

from models import User, Post

PY_36 = sys.version_info >= (3, 6)


class ActiveUser(User):
    class Meta:
        collection = User.meta.collection_name
        default_query = {User.active.s: True}
        default_sort = [(User.name.s, ASCENDING)]


@pytest.fixture
def users(loop, db):
    loop.run_until_complete(User(name='totti', active=True, data=10).save(db))
    loop.run_until_complete(User(name='francesco',
                                 active=False, data=7).save(db))
    loop.run_until_complete(User(name='admin', active=True, data=3).save(db))
    loop.run_until_complete(User(name='xxx', active=False).save(db))


def test_get_queryset(db):
    qs = User.q(db)
    assert isinstance(qs, MotorQuerySet)
    assert qs.doc_class == User
    assert qs.db == db


def test_clone(db):
    qs = User.q(db)
    clone_qs = qs.clone()
    assert isinstance(clone_qs, MotorQuerySet)
    assert qs != clone_qs
    assert qs.db == clone_qs.db
    assert qs.doc_class == clone_qs.doc_class
    assert qs.default_query == {}


async def test_create(db):
    u = await User.q(db).create(name='totti')

    assert isinstance(u, User)
    assert u.name == 'totti'
    assert u._id == 'totti'
    assert u.active is True
    assert u.posts == []
    assert 'data' not in u._data

    data = await db.user.find_one({'_id': 'totti'})
    assert u._id == data['_id']
    assert u.active == data['active']
    assert u.posts == data['posts']
    assert 'data' not in data


async def test_delete(db, users):
    assert await User.q(db).delete_one({User.name.s: 'admin'}) == 1
    assert await db.user.count_documents({}) == 3
    assert await db.user.find_one({'_id': 'admin'}) is None

    assert await User.q(db).delete_many({User.active.s: False}) == 2
    assert await db.user.count_documents({}) == 1
    assert await db.user.count_documents({'active': False}) == 0


async def test_replace(db):
    await User(name='totti', active=True, data=10).save(db)
    data = await db.user.find_one({'_id': 'totti'})
    assert data == {'_id': 'totti', 'active': True, 'posts': [], 'data': 10}

    res = await User.q(db).replace_one(
        {User.name.s: 'totti'},
        {'_id': 'totti', 'active': False, 'posts': []})
    assert res == 1
    u = await User.q(db).get('totti')
    assert u.name == 'totti'
    assert u.active is False
    assert u.posts == []
    assert u.data is None


async def test_update(db, users):
    assert await db.user.count_documents({}) == 4

    res = await User.q(db).update_one(
        {User.active.s: False}, {'$set': {User.active.s: True}})
    assert res == 1
    assert await db.user.count_documents({'active': True}) == 3

    res = await User.q(db).update_many(
        {User.active.s: True}, {'$set': {User.active.s: False}})

    assert res == 3
    assert await db.user.count_documents({'active': True}) == 0


async def test_insert_one(db):
    u = User(name='totti', active=True, data=10)
    res = await User.q(db).insert_one(u.to_mongo())
    assert res == u._id

    data = await db.user.find_one({'_id': res})
    assert data['_id'] == 'totti'
    assert data['active'] is True
    assert data['data'] == 10
    assert data['posts'] == []


async def test_insert_many(db):
    u1 = User(name='totti', active=True, data=10)
    u2 = User(name='francesco', active=False)
    res = await User.q(db).insert_many([u1.to_mongo(), u2.to_mongo()])
    assert res[0] == u1._id
    assert res[1] == u2._id

    assert await db.user.count_documents({}) == 2


async def test_find_one(db, users):
    user = await User.q(db).find_one({'_id': 'totti'})
    assert isinstance(user, User)
    assert user.name == 'totti'
    assert user._id == 'totti'
    assert user.active is True
    assert user.data == 10


async def test_get(db, users):
    user = await User.q(db).get('totti')
    assert isinstance(user, User)
    assert user.name == 'totti'
    assert user._id == 'totti'
    assert user.active is True
    assert user.data == 10


async def test_count(db, users):
    assert await User.q(db).count({}) == 4
    assert await User.q(db).count({'active': True}) == 2
    assert await User.q(db).count({'active': True, 'data': 10}) == 1

    with pytest.warns(
        DeprecationWarning,
        match="Use `count_documents` instead"
    ):
        await User.q(db).count({})


async def test_find(db):
    assert isinstance(User.q(db).find({}), MotorQuerySetCursor)


async def test_find_to_list(db, users):
    cur = User.q(db).find({})
    users = await cur.to_list(10)
    assert isinstance(users, list)
    assert len(users) == 4
    assert isinstance(users[0], User)
    assert isinstance(users[1], User)
    assert isinstance(users[2], User)
    assert isinstance(users[3], User)

    assert await cur.to_list(10) == []


async def test_find_limit(db, users):
    users = await User.q(db).find({}).limit(2).to_list(10)
    assert len(users) == 2


async def test_find_skip(db, users):
    users = await User.q(db).find({}).skip(1).to_list(10)
    assert len(users) == 3


async def test_find_sort(db, users):
    users = await User.q(db).find({})\
                      .sort([(User.name.s, ASCENDING)]).to_list(10)
    assert users[0].name == 'admin'
    assert users[1].name == 'francesco'
    assert users[2].name == 'totti'
    assert users[3].name == 'xxx'

    users = await User.q(db).find({})\
                      .sort([(User.name.s, DESCENDING)]).to_list(10)
    assert users[0].name == 'xxx'
    assert users[1].name == 'totti'
    assert users[2].name == 'francesco'
    assert users[3].name == 'admin'


async def test_find_sort_skip_limit(db, users):
    users = await User.q(db).find({})\
                      .sort([(User.name.s, ASCENDING)])\
                      .skip(1).limit(2).to_list(10)
    assert len(users) == 2
    assert users[0].name == 'francesco'
    assert users[1].name == 'totti'


async def test_find_projection(db, users):
    users = await User.q(db).find({}, {User.name.s: 1})\
                      .sort([(User.name.s, ASCENDING)])\
                      .to_list(10)
    assert len(users) == 4
    assert isinstance(users[0], User)
    assert users[0].name == 'admin'
    assert users[0].active is None
    assert users[0].data is None


async def test_find_for_loop(db, users):
    users = ('admin', 'francesco', 'totti', 'xxx')
    i = 0
    async for user in User.q(db).find({}).sort([('_id', ASCENDING)]):
        assert isinstance(user, User)
        assert users[i] == user.name
        i += 1


if PY_36:
    exec(textwrap.dedent("""
    async def test_async_comprehension(db, users):
        users = [user async for user in User.q(db).find({})]
        assert len(users) == 4
        assert isinstance(users[0], User)
        assert isinstance(users[1], User)
        assert isinstance(users[2], User)
        assert isinstance(users[3], User)
    """), globals(), locals())


async def test_create_indexes(db):
    await Post.q(db).create_indexes()

    indexes_info = await db.posts.index_information()
    assert 'title_index' in indexes_info
    assert 'author_created_index' in indexes_info
    assert indexes_info['title_index']['unique'] is True


async def test_aggregate(db, users):
    cursor = User.q(db).aggregate([
        {'$match': {User.active.s: True}},
        {'$group': {'_id': None, 'total': {'$sum': '$data'}}}
    ])
    await cursor.fetch_next
    data = cursor.next_object()
    assert data == {'_id': None, 'total': 13}

    cursor = User.q(db).aggregate([
        {'$group': {'_id': None, 'total': {'$sum': '$data'}}}
    ])
    await cursor.fetch_next
    data = cursor.next_object()
    assert data == {'_id': None, 'total': 20}

    cursor = User.q(db).aggregate([
        {'$match': {User.name.s: 'francesco'}},
        {'$group': {'_id': None, 'total': {'$sum': '$data'}}}
    ])
    await cursor.fetch_next
    data = cursor.next_object()
    assert data == {'_id': None, 'total': 7}


async def test_default_query_aggregate(db, users):
    cursor = ActiveUser.q(db).aggregate([
        {'$match': {ActiveUser.name.s: 'francesco'}},
        {'$group': {'_id': None, 'total': {'$sum': '$data'}}}
    ])
    await cursor.fetch_next
    data = cursor.next_object()
    assert data is None

    cursor = ActiveUser.q(db).aggregate([
        {'$group': {'_id': None, 'total': {'$sum': '$data'}}}
    ])
    await cursor.fetch_next
    data = cursor.next_object()
    assert data == {'_id': None, 'total': 13}


async def test_default_query_delete_one(db, users):
    res = await ActiveUser.q(db).delete_one({ActiveUser.name.s: 'xxx'})
    assert res == 0
    assert await db.user.count_documents({}) == 4

    res = await ActiveUser.q(db).delete_one({ActiveUser.name.s: 'admin'})
    assert res == 1
    assert await db.user.count_documents({}) == 3
    assert await db.user.find_one({'_id': 'admin'}) is None


async def test_default_query_delete_many(db, users):
    res = await ActiveUser.q(db).delete_many({ActiveUser.active.s: False})
    assert res == 0
    assert await db.user.count_documents({}) == 4

    res = await ActiveUser.q(db).delete_many({})
    assert res == 2
    assert await db.user.count_documents({}) == 2
    assert await db.user.count_documents({'active': True}) == 0


async def test_default_query_replace(db, users):
    res = await ActiveUser.q(db).replace_one(
        {ActiveUser.name.s: 'xxx'},
        {'_id': 'xxx', 'active': True, 'posts': [], 'data': 10})
    assert res == 0
    data = await db.user.find_one({'_id': 'xxx'})
    assert data == {'_id': 'xxx', 'active': False, 'posts': []}

    res = await ActiveUser.q(db).replace_one(
        {ActiveUser.name.s: 'totti'},
        {'_id': 'totti', 'active': False, 'posts': []})
    assert res == 1
    data = await db.user.find_one({'_id': 'totti'})
    assert data == {'_id': 'totti', 'active': False, 'posts': []}


async def test_default_query_update_one(db, users):
    res = await ActiveUser.q(db).update_one(
        {ActiveUser.active.s: False}, {'$set': {ActiveUser.active.s: True}})
    assert res == 0
    assert await db.user.count_documents({'active': True}) == 2

    res = await ActiveUser.q(db).update_one(
        {}, {'$set': {ActiveUser.active.s: False}})
    assert res == 1
    assert await db.user.count_documents({'active': True}) == 1


async def test_default_query_update_many(db, users):
    res = await ActiveUser.q(db).update_many(
        {ActiveUser.active.s: False}, {'$set': {ActiveUser.active.s: True}})
    assert res == 0
    assert await db.user.count_documents({'active': True}) == 2

    res = await ActiveUser.q(db).update_many(
        {}, {'$set': {ActiveUser.active.s: False}})
    assert res == 2
    assert await db.user.count_documents({'active': False}) == 4
    assert await db.user.count_documents({'active': True}) == 0


async def test_default_query_find_one(db, users):
    with pytest.raises(DocumentNotFoundError):
        await ActiveUser.q(db).find_one({'_id': 'xxx'})
    user = await ActiveUser.q(db).find_one({'_id': 'totti'})
    assert isinstance(user, ActiveUser)
    assert user.active is True


async def test_default_query_get(db, users):
    with pytest.raises(DocumentNotFoundError):
        await ActiveUser.q(db).get('xxx')
    user = await ActiveUser.q(db).get('totti')
    assert isinstance(user, ActiveUser)
    assert user.active is True


async def test_default_query_count(db, users):
    assert await ActiveUser.q(db).count_documents({}) == 2


async def test_default_query_find(db, users):
    users = await ActiveUser.q(db).find({})\
                            .sort([('_id', ASCENDING)]).to_list(10)
    assert len(users) == 2
    assert users[0].name == 'admin'
    assert users[1].name == 'totti'


async def test_with_options(db, users):
    res = await User.q(db).delete_one({User.name.s: 'xxx'})
    assert res == 1

    res = await User.q(db)\
                    .with_options(write_concern=WriteConcern(w=0))\
                    .delete_one({User.name.s: 'totti'})
    assert res is None


async def test_custom_queryset(db, users):
    class CustomUserQuerySet(MotorQuerySet):
        def active(self):
            qs = self.clone()
            qs.default_query = {'active': True}
            return qs

    class CustomUser(User):
        class Meta:
            collection = 'user'
            queryset = CustomUserQuerySet

    assert isinstance(CustomUser.q(db), CustomUserQuerySet)

    users = await CustomUser.q(db).active().find({}).to_list(10)
    assert len(users) == 2
    assert users[0].active is True
    assert users[1].active is True


async def test_default_sort_find(db, users):
    users = await ActiveUser.q(db).find({}).to_list(10)
    assert len(users) == 2
    assert users[0].name == 'admin'
    assert users[1].name == 'totti'

    users = await ActiveUser.q(db)\
                            .find({}, sort=[(User.name.s, DESCENDING)])\
                            .to_list(10)
    assert len(users) == 2
    assert users[0].name == 'totti'
    assert users[1].name == 'admin'

    users = await ActiveUser.q(db)\
                            .find({}).sort([(User.name.s, DESCENDING)])\
                            .to_list(10)
    assert len(users) == 2
    assert users[0].name == 'totti'
    assert users[1].name == 'admin'


async def test_queryset_cursor_clone(db):
    cursor = User.q(db).find({}, limit=10)
    clone = cursor.clone()
    assert cursor.doc_class == clone.doc_class
    assert cursor.cursor != clone.cursor
    assert clone.cursor.collection == clone.cursor.collection


async def test_unique_key_error(db):
    await Post.q(db).create_indexes()

    await Post(title='xxx', author='totti').save(db, do_insert=True)
    yyy = await Post(title='yyy', author='totti').save(db, do_insert=True)

    data = Post(title='xxx', author='totti').to_mongo()

    with pytest.raises(pymongo.errors.DuplicateKeyError):
        await Post.q(db).insert_one(data)
    with pytest.raises(DuplicateKeyError) as excinfo:
        await Post.q(db).insert_one(data)
    assert excinfo.value.index_name == 'title_index'

    yyy_data = yyy.to_mongo()
    yyy_data['title'] = 'xxx'
    with pytest.raises(pymongo.errors.DuplicateKeyError):
        await Post.q(db).replace_one({Post.title.s: 'yyy'}, yyy_data)
    with pytest.raises(DuplicateKeyError) as excinfo:
        await Post.q(db).replace_one({Post.title.s: 'yyy'}, yyy_data)
    assert excinfo.value.index_name == 'title_index'

    with pytest.raises(pymongo.errors.DuplicateKeyError):
        await Post.q(db).update_one({Post.title.s: 'yyy'},
                                    {'$set': {Post.title.s: 'xxx'}})
    with pytest.raises(DuplicateKeyError) as excinfo:
        await Post.q(db).update_one({Post.title.s: 'yyy'},
                                    {'$set': {Post.title.s: 'xxx'}})
    assert excinfo.value.index_name == 'title_index'

    with pytest.raises(pymongo.errors.DuplicateKeyError):
        await Post.q(db).update_many({}, {'$set': {Post.title.s: 'xxx'}})
    with pytest.raises(DuplicateKeyError) as excinfo:
        await Post.q(db).update_many({}, {'$set': {Post.title.s: 'xxx'}})
    assert excinfo.value.index_name == 'title_index'
