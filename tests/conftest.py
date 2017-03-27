import asyncio
import contextlib
import gc
import os.path
import sys

import pytest
from motor.motor_asyncio import AsyncIOMotorClient


sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


@contextlib.contextmanager
def loop_context(loop_factory=asyncio.new_event_loop):
    """A contextmanager that creates an event_loop, for test purposes.

    Handles the creation and cleanup of a test loop.
    """
    loop = setup_test_loop(loop_factory)
    yield loop
    teardown_test_loop(loop)


def setup_test_loop(loop_factory=asyncio.new_event_loop):
    """Create and return an asyncio.BaseEventLoop instance.

    The caller should also call teardown_test_loop,
    once they are done with the loop.
    """
    loop = loop_factory()
    asyncio.set_event_loop(None)
    return loop


def teardown_test_loop(loop):
    """Teardown and cleanup an event_loop created by setup_test_loop."""
    closed = loop.is_closed()
    if not closed:
        loop.call_soon(loop.stop)
        loop.run_forever()
        loop.close()
    gc.collect()
    asyncio.set_event_loop(None)


@contextlib.contextmanager
def _passthrough_loop_context(loop):
    if loop:
        # loop already exists, pass it straight through
        yield loop
    else:
        # this shadows loop_context's standard behavior
        loop = setup_test_loop()
        yield loop
        teardown_test_loop(loop)


def pytest_pycollect_makeitem(collector, name, obj):
    """Fix pytest collecting for coroutines."""
    if collector.funcnamefilter(name) and asyncio.iscoroutinefunction(obj):
        return list(collector._genfunctions(name, obj))


def pytest_pyfunc_call(pyfuncitem):
    """Run coroutines in an event loop instead of a normal function call."""
    if asyncio.iscoroutinefunction(pyfuncitem.function):
        existing_loop = pyfuncitem.funcargs.get('loop', None)
        with _passthrough_loop_context(existing_loop) as _loop:
            testargs = {arg: pyfuncitem.funcargs[arg]
                        for arg in pyfuncitem._fixtureinfo.argnames}

            task = _loop.create_task(pyfuncitem.obj(**testargs))
            _loop.run_until_complete(task)

        return True


@pytest.yield_fixture
def loop():
    """Return an instance of the event loop."""
    with loop_context() as _loop:
        yield _loop


# custom fixtures
@pytest.fixture(scope='function')
def client(loop):
    return AsyncIOMotorClient(io_loop=loop)


@pytest.fixture(scope='function')
def db(loop, client):
    test_db = client['aiomongodel_test']
    yield test_db
    loop.run_until_complete(client.drop_database(test_db))
