Changelog
=========

0.2.0 (2018-09-12)
------------------

Move requirements to motor>=2.0.

Remove ``count`` method from ``MotorQuerySetCursor``.

Add session support to ``MotorQuerySet`` and ``Document``.

Add ``create_collection`` method to ``Document``.

Fix ``__aiter__`` of ``MotorQuerySetCursor`` for python 3.7.

Deprecate ``count`` method of ``MotorQuerySet``.

Deprecate ``create`` method of ``Document``.

0.1.0 (2017-05-19)
------------------

The first ``aiomongodel`` release.
