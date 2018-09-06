===========
aiomongodel
===========

.. image:: https://travis-ci.org/ilex/aiomongodel.svg?branch=master
    :target: https://travis-ci.org/ilex/aiomongodel

.. image:: https://readthedocs.org/projects/aiomongodel/badge/?version=latest
    :target: http://aiomongodel.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

An asynchronous ODM similar to `PyMODM`_ on top of `Motor`_ an asynchronous 
Python `MongoDB`_ driver. Works on ``Python 3.5`` and up. Some features
such as asynchronous comprehensions require at least ``Python 3.6``. ``aiomongodel``
can be used with `asyncio`_ as well as with `Tornado`_.

Usage of ``session`` requires at least MongoDB version 4.0.

.. _PyMODM: http://pymodm.readthedocs.io/en/stable
.. _Motor: https://pypi.python.org/pypi/motor
.. _MongoDB: https://www.mongodb.com/
.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _Tornado: https://pypi.python.org/pypi/tornado

Install
=======

Install `aiomongodel` using `pip`::

    pip install aiomongodel

Documentation
=============

Read the `docs`_.

.. _docs: http://aiomongodel.readthedocs.io/

Getting Start
=============

Modeling
--------

To create a model just create a new model class, inherit it from 
``aiomongodel.Document`` class, list all the model fields and place 
a ``Meta`` class with model meta options. To create a subdocument, create
a class with fields and inherit it from ``aiomongodel.EmbeddedDocument``.

.. code-block:: python

    # models.py

    from datetime import datetime

    from pymongo import IndexModel, DESCENDING 

    from aiomongodel import Document, EmbeddedDocument
    from aiomongodel.fields import (
        StrField, BoolField, ListField, EmbDocField, RefField, SynonymField, 
        IntField, FloatField, DateTimeField, ObjectIdField)

    class User(Document):
        _id = StrField(regex=r'[a-zA-Z0-9_]{3, 20}')
        is_active = BoolField(default=True)
        posts = ListField(RefField('models.Post'), default=lambda: list())
        quote = StrField(required=False)

        # create a synonym field
        name = SynonymField(_id)

        class Meta:
            collection = 'users'

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
            collection = 'posts'
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
        # Note: if do_insert=False (default) save performs a replace
        # with upsert=True, so it does not raise if _id already exists
        # in db but replace document with that _id.
        u = await User(name='Alexandro').save(db, do_insert=True)
        assert u.name == 'Alexandro'
        assert u._id == 'Alexandro'
        assert u.is_active is True
        assert u.posts == []
        assert u.quote is None
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
        # object is reloaded from db after update.
        await u.update(db, {'$push': {User.posts.s: ObjectId()}})

        # DELETE
        u = await User.q(db).get('Ihor')
        await u.delete(db)


    loop = asyncio.get_event_loop()
    client = AsyncIOMotorClient(io_loop=loop)
    db = client.aiomongodel_test
    loop.run_until_complete(go(db))

Validation
----------
Use model's ``validate`` method to validate model's data. If
there are any invalid data an ``aiomongodel.errors.ValidationError``
will raise.

.. note:: 

    Creating model object or assigning it with invalid data does
    not raise errors! Be careful while saving model without validation.

.. code-block:: python

    class Model(Document):
        name = StrField(max_length=7)
        value = IntField(gt=5, lte=13)
        data = FloatField()

    def go():
        m = Model(name='xxx', value=10, data=1.6)
        # validate data
        # should not raise any error
        m.validate()

        # invalid data
        # note that there are no errors while creating
        # model with invalid data
        invalid = Model(name='too long string', value=0)
        try:
            invalid.validate()
        except aiomongodel.errors.ValidationError as e:
            assert e.as_dict() == {
                'name': 'length is greater than 7',
                'value': 'value should be greater than 5',
                'data': 'field is required'
            }
            
            # using translation - you can translate messages
            # to your language or modify them
            translation = {
                "field is required": "This field is required",
                "length is greater than {constraint}": ("Length of the field "
                                                        "is greater than "
                                                        "{constraint} characters"),
                # see all error messages in ValidationError docs
                # for missed messages default messages will be used
            }
            assert e.as_dict(translation=translation) == {
                'name': 'Length of the field is greater than 7 characters',
                'value': 'value should be greater than 5',
                'data': 'This field is required'
            }
 

Querying
--------

.. code-block:: python

    async def go(db):
        # find returns a cursor 
        cursor = User.q(db).find({}, {'_id': 1}).skip(1).limit(2)
        async for user in cursor:
            print(user.name)
            assert user.is_active is None  # we used projection

        # find one
        user = await User.q(db).find_one({User.name.s: 'Alexandro'})
        assert user.name == 'Alexandro'

        # update
        await User.q(db).update_many(
            {User.is_active.s: True},
            {'$set': {User.is_active.s: False}})

        # delete 
        await User.q(db).delete_many({})

Models Inheritance
------------------

A hierarchy of models can be built by inheriting one model from another.
A ``aiomongodel.Document`` class should be somewhere in hierarchy for model
adn ``aiomongodel.EmbeddedDocument`` for subdocuments. 
Note that fields are inherited but meta options are not. 

.. code-block:: python
    
    class Mixin:
        value = IntField()

    class Parent(Document):
        name = StrField()

    class Child(Mixin, Parent):
        # also has value and name fields
        rate = FloatField()

    class OtherChild(Child):
        # also has rate and name fields
        value = FloatField() # overwrite value field from Mixin

    class SubDoc(Mixin, EmbeddedDocument):
        # has value field
        pass

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
            collection = 'users'
        
        @classmethod
        def from_mongo(cls, data):
            # create appropriate model when loading from db
            if data['role'] == 'customer':
                return super(User, Customer).from_mongo(data)
            if data['role'] == 'admin':
                return super(User, Admin).from_mongo(data)

    class Customer(User):
        role = StrField(default='customer', choices=['customer'])  # overwrite role field
        address = StrField()

        class Meta:
            collection = 'users'
            default_query = {User.role.s: 'customer'}

    class Admin(User):
        role = StrField(default='admin', choices=['admin'])  # overwrite role field
        rights = ListField(StrField(), default=lambda: list())

        class Meta:
            collection = 'users'
            default_query = {User.role.s: 'admin'}


Transaction
-----------

.. code-block:: python

    from motor.motor_asyncio import AsyncIOMotorClient
    
    async def go(db):
        # create collection before using transaction
        await User.create_collection(db)

        async with await db.client.start_session() as session:
            try:
                async with s.start_transaction():
                    # all statements that use session inside this block
                    # will be executed in one transaction

                    # pass session to QuerySet
                    await User.q(db, session=session).create(name='user')  # note session param
                    # pass session to QuerySet method 
                    await User.q(db).update_one(
                        {User.name.s: 'user'},
                        {'$set': {User.is_active.s: False}},
                        session=session)  # note session usage
                    assert await User.q(db, session).count_documents({User.name.s: 'user'}) == 1

                    # session could be used in document crud methods
                    u = await User(name='user2').save(db, session=session)
                    await u.delete(db, session=session)

                    raise Exception()  # simulate error in transaction block
             except Exception:
                 # transaction was not committed 
                 assert await User.q(db).count_documents({User.name.s: 'user'}) == 0
                    
        
    loop = asyncio.get_event_loop()
    client = AsyncIOMotorClient(io_loop=loop)
    db = client.aiomongodel_test
    loop.run_until_complete(go(db))


License
=======

The library is licensed under MIT License.
