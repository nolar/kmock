import asyncio
import functools
import io
from typing import Any, AsyncIterator, Iterator

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
        kmock['/'] << (arg,)
    with pytest.raises(ValueError):
        (arg,) >> kmock['/']

    # But if forced:
    kmock['/'] << Response(payload=(arg,))  # wrapped/pre-parsed to avoid the validation/guessing
    resp = await kmock.get('/')
    text = await resp.read()
    assert resp.status == 500
    assert b'ValueError' in text


@pytest.mark.parametrize('content', [
    pytest.param((), id='empty'),
    pytest.param((None,), id='none'),
    pytest.param((lambda: None,), id='callable'),
    pytest.param((lambda: (),), id='callable-empty'),
    pytest.param((lambda: (None,),), id='callable-tuple'),
])
async def test_nones_are_ignored_in_streams(kmock: RawHandler, content: Any) -> None:
    spy = kmock['/'] << content
    end = kmock['/'] << b'fin!'
    resp = await kmock.get('/')
    text = await resp.read()
    assert text == b'fin!'
    assert len(spy) == 1
    assert len(end) == 1


async def test_depleted_source_skips_the_response_for_spying(kmock: RawHandler) -> None:
    stream1 = kmock['/'] << iter([b'1st'])
    stream2 = kmock['/'] << (b'2nd',)
    resp1 = await kmock.get('/')
    text1 = await resp1.read()
    resp2 = await kmock.get('/')
    text2 = await resp2.read()
    assert text1 == b'1st'
    assert text2 == b'2nd'
    assert len(stream1) == 2  # the 2nd time: caught, but not served
    assert len(stream2) == 1


def sync_gen(source: list[Any]) -> Iterator[Any]:
    for item in source:
        yield item


async def async_gen(source: list[Any]) -> AsyncIterator[Any]:
    for item in source:
        yield item


@pytest.mark.parametrize('item, expected', [
    pytest.param(b'', b'', id='empty'),
    pytest.param(b'world', b'world', id='bytes'),
    pytest.param('', b'""\n', id='emptystr'),
    pytest.param('world', b'"world"\n', id='str'),
    pytest.param(123, b'123\n', id='int'),
    pytest.param(123.456, b'123.456\n', id='float'),
    pytest.param(True, b'true\n', id='true'),
    pytest.param(False, b'false\n', id='false'),
    pytest.param([], b'[]\n', id='list-empty'),
    pytest.param({}, b'{}\n', id='dict-empty'),
    pytest.param(['item'], b'["item"]\n', id='list-full'),
    pytest.param({'key': 'value'}, b'{"key": "value"}\n', id='dict-full'),
])
async def test_json_encoding(kmock: RawHandler, item: Any, expected: bytes) -> None:
    kmock['/single'] << (item,)
    kmock['/double'] << (item, item)
    kmock['/syncgen'] << sync_gen([item, item])
    kmock['/asyncgen'] << async_gen([item, item])

    resp = await kmock.get('/single')
    text = await resp.read()
    assert text == expected

    resp = await kmock.get('/double')
    text = await resp.read()
    assert text == expected + expected

    resp = await kmock.get('/syncgen')
    text = await resp.read()
    assert text == expected + expected

    resp = await kmock.get('/asyncgen')
    text = await resp.read()
    assert text == expected + expected


@pytest.mark.kmock(strict=False)
@pytest.mark.parametrize('arg', [
    pytest.param(ZeroDivisionError, id='class'),
    pytest.param(ZeroDivisionError(), id='value'),
])
async def test_exceptions(kmock: RawHandler, arg: Any) -> None:
    kmock['/'] << 222 << (b"", arg)
    resp = await kmock.get('/')
    text = await resp.read()
    assert resp.status == 222  # not 500: the status cannot be changed after the streaming starts
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
    root = kmock['/'] << (arg,)
    resp = await kmock.get('/?q=world')
    text = await resp.read()
    assert text == b'world'
    assert len(root) == 1


# The future must be created inside an event loop, so it cannot go to params.
# Otherwise, the test is identical to the one above.
async def test_asyncio_future(kmock: RawHandler) -> None:
    arg = create_async_future()
    root = kmock['/'] << (arg,)
    resp = await kmock.get('/?q=world')
    text = await resp.read()
    assert text == b'world'
    assert len(root) == 1


async def test_binary_streams_from_path(kmock: RawHandler, tmp_path: Any) -> None:
    path = tmp_path / "test.txt"
    path.write_bytes(b'world')
    kmock['/'] << (b'hello', path)
    resp = await kmock.get('/')
    text = await resp.read()
    assert text == b'helloworld'


async def test_binary_streams_from_raw_io(kmock: RawHandler, tmp_path: Any) -> None:
    path = tmp_path / "test.txt"
    path.write_bytes(b'world')
    file = io.FileIO(str(path))  # io.RawBaseIO
    kmock['/'] << (b'hello', file)
    resp = await kmock.get('/')
    text = await resp.read()
    assert text == b'helloworld'


async def test_binary_streams_from_text_io(kmock: RawHandler, tmp_path: Any) -> None:
    path = tmp_path / "test.txt"
    path.write_bytes(b'world')
    file = io.TextIOWrapper(io.FileIO(str(path)), encoding='utf-8')  # io.TextIOBase
    kmock['/'] << (b'hello', file)
    resp = await kmock.get('/')
    text = await resp.read()
    assert text == b'helloworld'


async def test_binary_streams_from_buffered_io(kmock: RawHandler, tmp_path: Any) -> None:
    path = tmp_path / "test.txt"
    path.write_bytes(b'world')
    file = io.BufferedReader(io.FileIO(str(path)))  # io.BufferedIOBase
    kmock['/'] << (b'hello', file)
    resp = await kmock.get('/')
    text = await resp.read()
    assert text == b'helloworld'


async def test_binary_streams_from_bytes_io(kmock: RawHandler) -> None:
    file = io.BytesIO(b'world')  # io.BufferedIOBase
    kmock['/'] << (b'hello', file)
    resp = await kmock.get('/')
    text = await resp.read()
    assert text == b'helloworld'


async def test_binary_streams_from_string_io(kmock: RawHandler) -> None:
    file = io.StringIO('world')  # io.TextIOBase
    kmock['/'] << (b'hello', file)
    resp = await kmock.get('/')
    text = await resp.read()
    assert text == b'helloworld'
