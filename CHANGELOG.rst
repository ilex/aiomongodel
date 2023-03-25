Changelog
=========

0.2.2 (2020-12-14)
------------------

Bump version of motor for python 3.11 compatibility.

Add tests workflow for GitHub Actions CI.

0.2.1 (2020-12-14)
------------------

Add verbose_name to ``Field`` for meta information.

Fix ``DecimalField``'s issue to load field from float value.

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
