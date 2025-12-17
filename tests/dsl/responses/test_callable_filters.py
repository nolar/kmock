import asyncio
import concurrent.futures
import threading
from typing import Any

import pytest

from kmock import RawHandler

pytestmark = [pytest.mark.kmock(cls=RawHandler), pytest.mark.looptime]


def _set_event(event: threading.Event | asyncio.Event) -> threading.Event | asyncio.Event:
    event.set()
    return event


def _set_future(future: concurrent.futures.Future | asyncio.Future, val: bool) -> concurrent.futures.Future | asyncio.Future:
    future.set_result(val)
    return future


class _TrueObject:
    def __bool__(self) -> bool:
        return True


class _FalseObject:
    def __bool__(self) -> bool:
        return False


@pytest.mark.parametrize('fn, expected', [
    pytest.param(True, b'hello', id='true-raw'),
    pytest.param(False, b'world', id='false-raw'),
    pytest.param(_TrueObject(), b'hello', id='true-obj'),
    pytest.param(_FalseObject(), b'world', id='false-obj'),
    pytest.param(lambda: True, b'hello', id='true-fn'),
    pytest.param(lambda: False, b'world', id='false-fn'),
    pytest.param(lambda: _TrueObject(), b'hello', id='true-obj-fn'),
    pytest.param(lambda: _FalseObject(), b'world', id='false-obj-fn'),
    pytest.param(lambda: (lambda: (lambda: True)), b'hello', id='true-nested'),
    pytest.param(lambda: (lambda: (lambda: False)), b'world', id='false-nested'),
    pytest.param(lambda: asyncio.Event(), b'world', id='event-async-clear'),
    pytest.param(lambda: threading.Event(), b'world', id='event-sync-clear'),
    pytest.param(lambda: _set_event(asyncio.Event()), b'hello', id='event-async-set'),
    pytest.param(lambda: _set_event(threading.Event()), b'hello', id='event-sync-se'),
    pytest.param(lambda: asyncio.Future(), b'world', id='fut-async-clear'),
    pytest.param(lambda: concurrent.futures.Future(), b'world', id='fut-sync-clear'),
    pytest.param(lambda: _set_future(asyncio.Future(), True), b'hello', id='fut-async-true'),
    pytest.param(lambda: _set_future(asyncio.Future(), False), b'world', id='fut-async-false'),
    pytest.param(lambda: _set_future(concurrent.futures.Future(), True), b'hello', id='fut-sync-trye'),
    pytest.param(lambda: _set_future(concurrent.futures.Future(), False), b'world', id='fut-sync-false'),
])
async def test_callable_filter(kmock: RawHandler, fn: Any, expected: bytes) -> None:
    kmock['/'][fn] << b'hello'
    kmock['/'] << b'world'
    resp = await kmock.get('/')
    text = await resp.read()
    assert text == expected
