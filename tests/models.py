from datetime import datetime

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel

from aiomongodel import Document, EmbeddedDocument
from aiomongodel.fields import (
    AnyField, StrField, IntField, FloatField, BoolField, DateTimeField,
    ObjectIdField, EmbDocField, ListField, RefField, SynonymField)


class User(Document):
    """User model."""

    _id = StrField(required=True, allow_blank=False, max_length=10)
    active = BoolField(required=True, default=True)
    posts = ListField(RefField('models.Post'),
                      required=True, default=lambda: list())
    data = AnyField(required=False)

    # synonyms
    name = SynonymField(_id)


class Post(Document):
    """Post model."""

    title = StrField(required=True, allow_blank=False)
    views = IntField(required=True, default=0)
    created = DateTimeField(required=True, default=lambda: datetime.utcnow())
    rate = FloatField(required=True, default=0.0)
    author = RefField(User, required=True)
    comments = ListField(EmbDocField('models.Comment'),
                         required=True, default=lambda: list())

    class Meta:
        """Post meta."""

        collection_name = 'posts'
        indexes = [
            IndexModel([('title', ASCENDING)],
                       unique=True, name='title_index'),
            IndexModel([('author', ASCENDING), ('created', DESCENDING)],
                       name='author_created_index')]


class Comment(EmbeddedDocument):
    """Comment model."""

    _id = ObjectIdField(required=True, default=lambda: ObjectId())
    body = StrField(required=True, allow_blank=False)
    author = RefField(User, required=True, mongo_name='user')
