from models import User


async def test_get_queryset(db):
    client = db.client
    async with await client.start_session() as s:
        qs = User.q(db, session=s)
        assert qs.session == s


async def test_clone(db):
    client = db.client
    async with await client.start_session() as s:
        qs = User.q(db, session=s)
        clone_qs = qs.clone()
        assert clone_qs.session == s


async def test_queryset_operations(db):
    client = db.client
    # TODO: mock collection methods and check call params include session
    async with await client.start_session() as s:
        await User.q(db, session=s).delete_one({})
        await User.q(db, session=s).delete_many({})
        await User.q(db, session=s).insert_one({User.name.s: 'user'})
        await User.q(db, session=s).replace_one(
            {User.name.s: 'user'}, {User.active.s: False})
        await User.q(db, session=s).update_one(
                {User.name.s: 'user'}, {'$set': {User.active.s: True}})
        await User.q(db, session=s).update_many(
            {User.name.s: 'user'}, {'$set': {User.active.s: False}})
        await User.q(db, session=s).find_one({})
        await User.q(db, session=s).find({}).to_list(10)


async def test_transaction_commit(db):
    # create collection before using transaction
    await User.create_collection(db)
    client = db.client
    async with await client.start_session() as s:
        async with s.start_transaction():
            await User.q(db, session=s).insert_one({User.name.s: 'user'})
            assert await User.q(db, session=s).count_documents() == 1
            assert await User.q(db).count_documents() == 0

    assert await User.q(db).count_documents() == 1


async def test_transaction_rollback(db):
    # create collection before using transaction
    await User.create_collection(db)
    client = db.client
    try:
        async with await client.start_session() as s:
            async with s.start_transaction():
                await User.q(db, session=s).insert_one({User.name.s: 'user'})
                assert await User.q(db, session=s).count_documents() == 1
                assert await User.q(db).count_documents() == 0
                raise Exception()
    except Exception:
        pass

    assert await User.q(db).count_documents() == 0
