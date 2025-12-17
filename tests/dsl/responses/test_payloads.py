import asyncio
import functools
import io
from typing import Any

import pytest

from kmock import Payload, RawHandler, Request, Response

pytestmark = [pytest.mark.kmock(cls=RawHandler), pytest.mark.looptime]


@pytest.mark.parametrize('arg', [
    frozenset({'item'}),
    {'item'},
    object(),
])
async def test_unsupported_content(kmock: RawHandler, arg: Any) -> None:
    with pytest.raises(ValueError):
        kmock['/'] << arg
    with pytest.raises(ValueError):
        arg >> kmock['/']

    # But if forced:
    kmock['/'] << Response(payload=arg)  # wrapped/pre-parsed to avoid the validation/guessing
    resp = await kmock.get('/')
    text = await resp.read()
    assert resp.status == 500
    assert b'ValueError' in text


@pytest.mark.parametrize('arg', [None, lambda: None])
async def test_nones_in_content_is_skipped_for_spying(kmock: RawHandler, arg: Any) -> None:
    spy = kmock['/'] << arg
    end = kmock['/'] << b'fin!'
    resp = await kmock.get('/')
    text = await resp.read()
    assert resp.status == 200
    assert text == b'fin!'
    assert len(spy) == 1
    assert len(end) == 1


@pytest.mark.parametrize('content, expected', [
    pytest.param(b'', b'', id='empty'),
    pytest.param(b'world', b'world', id='bytes'),
    pytest.param('', b'""', id='emptystr'),
    pytest.param('world', b'"world"', id='str'),
    pytest.param(1234, b'1234', id='int'),  # NB: if used as a status, it hangs for all 1xx
    pytest.param(123.456, b'123.456', id='float'),
    pytest.param(True, b'true', id='true'),
    pytest.param(False, b'false', id='false'),
    pytest.param([], b'[]', id='list-empty'),
    pytest.param({}, b'{}', id='dict-empty'),
    pytest.param(['item'], b'["item"]', id='list-full'),
    pytest.param({'key': 'value'}, b'{"key": "value"}', id='dict-full'),
])
async def test_simple_json_encoding(kmock: RawHandler, content: Any, expected: bytes) -> None:
    kmock['/'] << content
    resp = await kmock.get('/')
    text = await resp.read()
    assert resp.status == 200
    assert text == expected


@pytest.mark.parametrize('arg', [
    pytest.param(ZeroDivisionError, id='class'),
    pytest.param(ZeroDivisionError(), id='value'),
])
async def test_exceptions(kmock: RawHandler, arg: Any) -> None:
    kmock['/'] << arg
    resp = await kmock.get('/')
    text = await resp.read()
    assert resp.status == 500
    assert b'ZeroDivisionError' in text
    assert b'Traceback (most recent call last):' in text


def create_async_future() -> asyncio.Future:
    future = asyncio.Future()
    future.set_result(b'world')
    return future


def sync_no_args() -> Payload:
    return b'world'


def sync_one_arg(request: Request) -> Payload:
    return request.params.get('q').encode()


async def async_no_args() -> Payload:
    return b'world'


async def async_one_arg(request: Request) -> Payload:
    return request.params.get('q').encode()


@pytest.mark.parametrize('arg', [
    # Simple functions.
    pytest.param(sync_no_args, id='fn-sync-no-args'),
    pytest.param(sync_one_arg, id='fn-sync-one-arg'),
    pytest.param(async_no_args, id='fn-async-no-args'),
    pytest.param(async_one_arg, id='fn-async-one-arg'),

    # Partials.
    pytest.param(functools.partial(sync_no_args), id='partial-sync-no-args'),
    pytest.param(functools.partial(sync_one_arg), id='partial-sync-one-args'),
    pytest.param(functools.partial(async_no_args), id='partial-async-no-args'),
    pytest.param(functools.partial(async_one_arg), id='partial-async-one-args'),

    # Lambdas.
    pytest.param(lambda: b'world', id='lambda-no-args'),
    pytest.param(lambda req: req.params.get('q').encode(), id='lambda-one-arg'),
    pytest.param(lambda: (lambda: (lambda: b'world')), id='lambda-nested'),

    # Coroutines (NB: coros cannot be awaited twice like futures/tasks).
    pytest.param(async_no_args, id='coro-no-args'),
    pytest.param(async_one_arg, id='coro-one-arg'),

    # Callables that return coroutines/awaitables.
    pytest.param(lambda: create_async_future(), id='fn-future-no-args'),
    pytest.param(lambda req: create_async_future(), id='fn-future-one-arg'),
    pytest.param(lambda: async_no_args(), id='fn-coro-no-args'),
    pytest.param(lambda req: async_one_arg(req), id='fn-coro-no-args'),
    pytest.param(lambda: asyncio.create_task(async_no_args()), id='fn-task-no-args'),
    pytest.param(lambda req: asyncio.create_task(async_one_arg(req)), id='fn-task-one-arg'),
])
async def test_callables_awaitables(kmock: RawHandler, arg: Any) -> None:
    # Test only how callables/awaitables unfold into types, which are pre-tested elsewhere.
    root = kmock['/'] << arg
    resp = await kmock.get('/?q=world')
    text = await resp.read()
    assert text == b'world'
    assert len(root) == 1


# The future must be created inside an event loop, so it cannot go to params.
# Otherwise, the test is identical to the one above.
async def test_asyncio_future(kmock: RawHandler) -> None:
    arg = create_async_future()
    root = kmock['/'] << arg
    resp = await kmock.get('/?q=world')
    text = await resp.read()
    assert text == b'world'
    assert len(root) == 1


@pytest.mark.parametrize('status', [200, 444, 555, 999])
async def test_status(kmock: RawHandler, status: int) -> None:
    kmock['/'] << status
    resp = await kmock.get('/')
    assert resp.status == status


async def test_headers(kmock: RawHandler) -> None:
    kmock['/'] << b'' << {'Content-type': 'application/test', 'X-Custom': 'blah'}
    resp = await kmock.get('/')
    assert resp.headers['X-Custom'] == 'blah'
    assert resp.headers['Content-Type'] == 'application/test'


async def test_response(kmock: RawHandler) -> None:
    kmock['/'] << Response(status=234, headers={'a': 'b'}, cookies={'c': 'd'}, payload=b'hello')
    resp = await kmock.get('/')
    text = await resp.read()
    assert resp.status == 234
    assert resp.headers['a'] == 'b'
    assert resp.cookies['c'].value == 'd'
    assert text == b'hello'


@pytest.mark.parametrize('arg', [
    pytest.param(NotImplemented, id='notimpl-sentinel'),
    pytest.param(NotImplementedError, id='notimpl-class'),
    pytest.param(NotImplementedError(), id='notimpl-instance'),
])
async def test_notimplemented(kmock: RawHandler, arg: Any) -> None:
    kmock['/'] << arg
    resp = await kmock.get('/')
    text = await resp.read()
    assert resp.status == 500
    assert b'no reaction matching the request is defined' in text


# A reminder: this is the exception raised by e.g. ``lambda: next(source)``
@pytest.mark.parametrize('arg', [StopIteration, StopIteration()], ids=['class', 'instance'])
async def test_self_exclusion(kmock: RawHandler, arg: Any) -> None:
    r1 = kmock['/'] << arg
    r2 = kmock['/'] << b''
    await kmock.get('/')
    await kmock.get('/')
    await kmock.get('/')
    assert len(r1) == 1
    assert len(r2) == 3
    # assert r1.active == False


async def test_path_reading(kmock: RawHandler, tmp_path: Any) -> None:
    path = tmp_path / "test.txt"
    path.write_bytes(b'hello')
    kmock['/'] << path
    resp = await kmock.get('/')
    text = await resp.read()
    assert resp.status == 200
    assert text == b'hello'


@pytest.mark.parametrize('arg, data', [
    pytest.param(io.BytesIO, b'hello', id='binary'),
    pytest.param(io.StringIO, 'hello', id='string'),
])
async def test_io_reading(kmock: RawHandler, arg: type[io.IOBase], data: Any) -> None:
    buffer = arg(data)
    kmock['/'] << buffer
    resp = await kmock.get('/')
    text = await resp.read()
    assert resp.status == 200
    assert text == b'hello'


async def test_deactivated_reactions(kmock: RawHandler) -> None:
    r1 = kmock['get /'] << b'hello, '
    r1 << b'world!\n'
    with pytest.raises(RuntimeError, match=r"requests of a deactivated reaction is prohibited"):
        list(r1)


# Assume that if it works for one response this way, it works for all of them.
# Mind that it is impossible to chain 2+ items, since << & >> go left-to-right.
async def test_reversed_payloads(kmock: RawHandler) -> None:
    b'hello' >> kmock['/']
    resp = await kmock.get('/')
    text = await resp.read()
    assert resp.status == 200
    assert text == b'hello'
