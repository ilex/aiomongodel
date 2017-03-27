===========
aiomongodel
===========

An asynchronous ODM similar to `PyMODM`_ on top of `Motor`_ an asynchronous 
Python `MongoDB`_ driver. Works on ``Python 3.5`` and up. Some features
such as asynchronous comprehensions require at least ``Python 3.6``. ``aiomongodel``
can be used with `asyncio`_ as well as with `Tornado`_.

.. _PyMODM: http://pymodm.readthedocs.io/en/stable
.. _Motor: https://pypi.python.org/pypi/motor
.. _MongoDB: https://www.mongodb.com/
.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _Tornado: https://pypi.python.org/pypi/tornado
.. _AIOHTTP: https://pypi.python.org/pypi/aiohttp

Install
=======

Install `aiomongodel` using `pip`::

    pip install https://github.com/ilex/aiomongodel/archive/master.zip

Getting Start
=============

Modeling
--------

    .. code-block:: python

        # models.py

        from datetime import datetime

        from pymongo import IndexModel, DESCENDING 

        from aiomongodel import Document, EmbeddedDocument
        from aiomongodel.fields import StrField, BoolField, ListField, EmbDocField

        class User(Document):
            _id = StrField(regex=r'[a-zA-Z0-9_]{3, 20}')
            is_active = BoolField(default=True)
            posts = ListField(RefField('models.Post'), default=lambda: list())
            quote = StrField(required=False)

            # create a synonym field
            name = SynonymField(_id)

            class Meta:
                collection_name = 'users'

        class Post(Document):
            # _id field will be added automatically as 
            # _id = ObjectIdField(defalut=lambda: ObjectId())
            title = StrField(allow_blank=False, max_length=50)
            body = StrField()
            created = DateTimeField(default=lambda: datetime.utcnow())
            views = IntField(default=0)
            rate = FloatField(default=0.0)
            author = RefField(User, mongo_name='user')
            comments = ListField(EmbDocField('models.Comment'), default=lambda: list())

            class Meta:
                collection_name = 'posts'
                indexes = [IndexModel([('created', DESCENDING)])]
                default_sort = [('created', DESCENDING)]

        class Comment(EmbeddedDocument):
            _id = ObjectIdField(default=lambda: ObjectId())
            author = RefField(User)
            body = StrField()

        # `s` property of the fields can be used to get a mongodb string name
        # to use in queries
        assert User._id.s == '_id'
        assert User.name.s == '_id'  # name is synonym
        assert Post.title.s == 'title'
        assert Post.author.s == 'user'  # field has mongo_name
        assert Post.comments.body.s == 'comments.body'  # compound name

CRUD
----

    .. code-block:: python

        from motor.motor_asyncio import AsyncIOMotorClient
        
        async def go(db):
            # create model's indexes 
            await User.q(db).create_indexes()

            # CREATE
            # create using save
            u = await User(name='Alexandro').save(db)
            assert u.name == 'Alexandro'
            assert u._id == 'Alexandro'
            assert u.is_active is True
            assert u.posts == []
            assert u.quote is None
            # create using create
            u = await User.create(db, name='Francesco')
            # using query
            u = await User.q(db).create(name='Ihor', is_active=False)

            # READ
            # get by id
            u = await User.q(db).get('Alexandro')
            assert u.name == 'Alexandro'
            # find
            users = await User.q(db).find({User.is_active.s: True}).to_list(10)
            assert len(users) == 2
            # using for loop
            users = []
            async for user in User.q(db).find({User.is_active.s: False}):
                users.append(user)
            assert len(users) == 1
            # in Python 3.6 an up use async comprehensions
            users = [user async for user in User.q(db).find({})]
            assert len(users) == 3

            # UPDATE
            u = await User.q(db).get('Ihor')
            u.is_active = True
            await u.save(db)
            assert (await User.q(db).get('Ihor')).is_active is True
            # using update (without data validation)
            u.update(db, {'$push': {User.posts.s: ObjectId()}})

            # DELETE
            u = await User.q(db).get('Ihor')
            await u.delete(db)


        loop = asyncio.get_event_loop()
        client = AsyncIOMotorClient(io_loop=loop)
        db = client.aiomongodel_test
        loop.run_until_complete(go(db))

Querying
--------

    .. code-block:: python

        async def go(db):
            # find returns a cursor 
            cursor = User.q(db).find({}, {'_id': 1}).skip(1).limit(2)
            async for user in cursor:
                print(user.name)
                assert user.is_active is None

            # find one
            user = await User.q(db).find_one({User.name.s: 'Alexandro'})
            assert user.name == 'Alexandro'

            # update
            await User.q(db).update_many(
                {User.is_active.s: True},
                {'$set': {User.is_active.s: False}})

            # delete 
            await User.q(db).delete_many({})


Models Inheritance With Same Collection
---------------------------------------

    .. code-block:: python

        class Mixin:
            is_active = BoolField(default=True)

        class User(Mixin, Document):
            _id = StrField() 
            role = StrField()
            name = SynonymField(_id)

            class Meta:
                collection_name = 'users'
            
            @classmethod
            def from_son(cls, data):
                # create appropriate model when loading from db
                if data['role'] == 'customer':
                    return Customer.from_son(data)
                if data['role'] == 'admin':
                    return Admin.from_son(data)

        class Customer(User):
            role = StrField(default='customer')
            address = StrField()

            class Meta:
                collection_name = 'users'
                default_query = {User.role.s: 'customer'}

        class Admin(User):
            role = StrField(default='admin')
            rights = ListField(StrField(), default=lambda: list())

            class Meta:
                collection_name = 'users'
                default_query = {User.role.s: 'admin'}

License
=======

The library is licensed under MIT License.
