import pytest
from pymongo import ASCENDING

from aiomongodel import Document, EmbeddedDocument
from aiomongodel.errors import DocumentNotFoundError, ValidationError
from aiomongodel.fields import (
    IntField, StrField, FloatField, SynonymField, BoolField)


def test_document_inheritance():
    class Parent(Document):
        name = StrField()

    class Child(Parent):
        value = IntField()

    assert Child._id is Parent._id
    assert Child.name is Parent.name
    assert Child.meta.fields == {'_id': Parent._id,
                                 'name': Parent.name,
                                 'value': Child.value}
    Child.meta.collection_name == 'child'
    Parent.meta.collection_name == 'parent'


def test_mixin_inheritance():
    class Mixin(object):
        name = StrField()

    class Child(Mixin, Document):
        value = IntField()

    assert Child.name is Mixin.name
    assert Child.meta.fields == {'_id': Child._id,
                                 'name': Mixin.name,
                                 'value': Child.value}


def test_multiple_inheritance():
    class Mixin:
        name = StrField()

    class Parent(Document):
        value = IntField()

    class Child(Mixin, Parent):
        pass

    assert Child._id is Parent._id
    assert Child.name is Mixin.name
    assert Child.value is Parent.value
    assert Child.meta.fields == {'_id': Parent._id,
                                 'name': Mixin.name,
                                 'value': Child.value}


def test_override_field():
    class Parent(Document):
        value = IntField()

    class Child(Parent):
        value = FloatField()

    assert Child._id is Parent._id
    assert isinstance(Child.value, FloatField)
    assert Child.meta.fields == {'_id': Parent._id, 'value': Child.value}


def test_complex_inheritance_override_field():
    class Root(Document):
        value = IntField()

    class Parent1(Root):
        value = FloatField()
        name = StrField()

    class Parent2(Root):
        value = IntField()
        slug = StrField()

    class Child1(Parent1, Parent2):
        pass

    assert Child1._id is Parent1._id
    assert Child1.value is Parent1.value
    assert Child1.name is Parent1.name
    assert Child1.slug is Parent2.slug

    assert Child1.meta.fields == {'_id': Parent1._id,
                                  'value': Parent1.value,
                                  'name': Parent1.name,
                                  'slug': Parent2.slug}

    class Child2(Parent2, Parent1):
        pass

    assert Child2._id is Parent2._id
    assert Child2.value is Parent2.value
    assert Child2.name is Parent1.name
    assert Child2.slug is Parent2.slug

    assert Child2.meta.fields == {'_id': Parent2._id,
                                  'value': Parent2.value,
                                  'name': Parent1.name,
                                  'slug': Parent2.slug}

    class Child3(Parent1, Parent2):
        value = StrField()

    assert Child3._id is Parent1._id
    assert isinstance(Child3.value, StrField)
    assert Child3.name is Parent1.name
    assert Child3.slug is Parent2.slug

    assert Child3.meta.fields == {'_id': Parent1._id,
                                  'value': Child3.value,
                                  'name': Parent1.name,
                                  'slug': Parent2.slug}


def test_inheritance_synonym_field():
    class Parent(Document):
        _id = StrField()
        name = SynonymField(_id)

    class Child(Parent):
        value = IntField()

    assert Child._id is Parent._id
    assert Child.name is Parent._id
    assert Child.meta.fields == {'_id': Parent._id, 'value': Child.value}
    assert Child.meta.fields_synonyms == {'_id': 'name'}


def test_emb_doc_inheritance():
    class Parent(EmbeddedDocument):
        value = IntField()

    class Child(Parent):
        name = StrField()

    assert Child.value is Parent.value
    assert Child.meta.fields == {'value': Parent.value, 'name': Child.name}


def test_emb_doc_mixin_inheritance():
    class Parent:
        value = IntField()

    class Child(Parent, EmbeddedDocument):
        name = StrField()

    assert Child.value is Parent.value
    assert Child.meta.fields == {'value': Parent.value, 'name': Child.name}


def test_emb_doc_override_field():
    class Parent1:
        value = IntField()

    class Parent2(EmbeddedDocument):
        value = FloatField()

    class Child1(Parent1, Parent2):
        pass

    assert Child1.value is Parent1.value
    assert Child1.meta.fields == {'value': Parent1.value}

    class Child2(Parent2, Parent1):
        pass

    assert Child2.value is Parent2.value
    assert Child2.meta.fields == {'value': Parent2.value}

    class Child3(Parent1, Parent2):
        value = StrField()

    assert isinstance(Child3.value, StrField)
    assert Child3.meta.fields == {'value': Child3.value}


async def test_document_inheritance_same_collection(db):
    class User(Document):
        _id = StrField()
        role = StrField(default='user')

        name = SynonymField(_id)

        class Meta:
            collection = 'users'

        @classmethod
        def from_mongo(cls, data):
            return super(User, cls.get_class(data['role'])).from_mongo(data)

        @classmethod
        def get_class(cls, role):
            if role == 'user':
                return User
            if role == 'admin':
                return Admin
            if role == 'customer':
                return Customer

    class Admin(User):
        role = StrField(default='admin')

        class Meta:
            collection = 'users'
            default_query = {User.role.s: 'admin'}

    class Customer(User):
        role = StrField(default='customer')
        address = StrField()

        class Meta:
            collection = 'users'
            default_query = {User.role.s: 'customer'}

    await User(name='User').save(db)
    await Admin(name='Admin').save(db)
    await Customer(name='Customer', address='Address').save(db)

    with pytest.raises(DocumentNotFoundError):
        await Customer.q(db).get('Admin')

    customers = await Customer.q(db).find({}).to_list(10)
    assert len(customers) == 1

    users = await User.q(db).find({})\
                      .sort([(User.name.s, ASCENDING)]).to_list(10)
    assert len(users) == 3
    assert isinstance(users[0], Admin)
    assert users[0].name == 'Admin'
    assert isinstance(users[1], Customer)
    assert users[1].name == 'Customer'
    assert isinstance(users[2], User)
    assert users[2].name == 'User'


def test_validate_document_with_subclass_validation_rules():
    class Doc(Document):
        name = StrField(allow_blank=False)
        draft = BoolField(default=False)

        class Meta:
            collection = 'docs'

    class DraftDoc(Doc):
        name = StrField(allow_blank=True)
        draft = BoolField(default=True)

        class Meta:
            collection = 'docs'
            default_query = {'draft': False}

    doc = Doc(name='', draft=True)
    with pytest.raises(ValidationError):
        doc.validate()

    with pytest.raises(ValidationError):
        Doc.validate_document(doc)

    # should not raise any exception
    DraftDoc.validate_document(doc)
