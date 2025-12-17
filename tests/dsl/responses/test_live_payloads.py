import asyncio
import traceback
from typing import Any

import aiohttp
import pytest

from kmock import RawHandler

pytestmark = [pytest.mark.kmock(cls=RawHandler), pytest.mark.looptime]


async def test_lazy_content_without_streaming(kmock: RawHandler, looptime: int) -> None:
    kmock['/'] << ...
    loop = asyncio.get_running_loop()
    loop.call_later(11, lambda: kmock['/'][...] << {'hello': 'world'})
    resp = await kmock.get('/', timeout=aiohttp.ClientTimeout(33))
    text = await resp.read()
    content_type = resp.headers['Content-Type']
    assert content_type.startswith('application/json')  # not application/octet-stream!
    assert resp.headers['Content-Length'] == '18' # it is known in the first place
    assert text == b'{"hello": "world"}'
    assert looptime == 11


async def test_batch_formation(kmock: RawHandler, looptime: int) -> None:
    kmock['/'] << ...
    loop = asyncio.get_running_loop()
    loop.call_later(11, lambda: kmock['/'][...] << b"hello" << b"world")  # not continued
    loop.call_later(22, lambda: kmock['/'][...] << b"never" << b"again")
    resp = await kmock.get('/', timeout=aiohttp.ClientTimeout(33))
    text = await resp.read()
    assert text == b"helloworld"
    assert looptime == 11


# We cannot check that they were squashed, but this does not matter. Just check that it works.
# Mainly for the coverage of the tuple-squashing branches in `Stream.__lshift__`.
@pytest.mark.parametrize('arg1, arg2', [
    pytest.param((b'hello',), (b'world',), id='tuple2tuple'),
    pytest.param((b'hello',), b'world', id='tuple2other'),
    pytest.param(b'hello', (b'world',), id='other2tuple'),
    pytest.param(b'hello', b'world', id='other2other'),
])
async def test_batch_optimization(kmock: RawHandler, looptime: int, arg1: Any, arg2: Any) -> None:
    kmock['/'] << ...
    loop = asyncio.get_running_loop()
    loop.call_later(11, lambda: kmock['/'][...] << arg1 << arg2)
    resp = await kmock.get('/', timeout=aiohttp.ClientTimeout(33))
    text = await resp.read()
    assert text == b"helloworld"
    assert looptime == 11


async def test_batch_prohibition_after_consumed(kmock: RawHandler, looptime: int) -> None:
    kmock['/'] << ...
    live = kmock['/'][...]  # reuse the same instance!
    loop = asyncio.get_running_loop()
    loop.call_later(11, lambda: live << b"hello" << b"world")
    resp = await kmock.get('/', timeout=aiohttp.ClientTimeout(33))
    await resp.read()
    assert looptime == 11
    with pytest.raises(RuntimeError, match=r".*already consumed.*"):
        live << b"too late"


@pytest.mark.parametrize('payload', [
    pytest.param(..., id='direct-ellipsis'),
    pytest.param((...,), id='stream-tuple'),
    pytest.param((x for x in [...]), id='stream-generator'),
])
async def test_blocking_without_feeding(kmock: RawHandler, looptime: int, payload) -> None:
    kmock['/'] << payload
    with pytest.raises(asyncio.TimeoutError):
        resp = await kmock.get('/', timeout=aiohttp.ClientTimeout(33))
        await resp.read()
    assert looptime == 33


@pytest.mark.parametrize('payload', [
    pytest.param(..., id='direct-ellipsis'),
    pytest.param((...,), id='stream-tuple'),
    pytest.param((x for x in [...]), id='stream-generator'),
])
async def test_closing_without_continuation(kmock: RawHandler, looptime: int, payload) -> None:
    stream = kmock['/'] << payload
    loop = asyncio.get_running_loop()
    loop.call_later(11, lambda: stream[...] << None)
    resp = await kmock.get('/', timeout=aiohttp.ClientTimeout(33))
    await resp.read()
    assert looptime == 11


@pytest.mark.parametrize('payload', [
    pytest.param(..., id='direct-ellipsis'),
    pytest.param((...,), id='stream-tuple'),
    pytest.param((x for x in [...]), id='stream-generator'),
])
async def test_timing(kmock: RawHandler, looptime: int, payload) -> None:
    stream = kmock['/'] << payload
    loop = asyncio.get_running_loop()
    loop.call_later(11, lambda: stream[...] << (b'1st ', lambda: loop.time(), b' ', ...))
    loop.call_later(22, lambda: stream[...] << (b'2nd ', lambda: loop.time()))

    resp = await kmock.get('/')
    text = await resp.read()

    assert looptime == 22
    assert text == b'1st 11.0\n 2nd 22.0\n'


async def test_suffixing(kmock: RawHandler, looptime: int) -> None:
    stream = kmock['/'] << (b'main-pre', ..., b' main-post')
    loop = asyncio.get_running_loop()
    loop.call_later(11, lambda: stream[...] << (b' 1st-pre', ..., b' 1st-post'))
    loop.call_later(22, lambda: stream[...] << (b' 2nd-pre', ..., b' 2nd-post'))
    loop.call_later(33, lambda: stream[...] << (b' fin'))

    resp = await kmock.get('/')
    text = await resp.read()

    assert looptime == 33
    assert text == b'main-pre 1st-pre 2nd-pre fin 2nd-post 1st-post main-post'


async def test_feeding_without_entering() -> None:
    kmock = RawHandler()
    with pytest.raises(RuntimeError, match=r".*only possible if the mock handler is entered."):
        kmock[...] << b''


@pytest.mark.parametrize('ellipsis', [
    pytest.param(..., id='direct'),
    pytest.param((b'', ...), id='nested1'),
    pytest.param((b'', (b'', ...)), id='nested2'),
    pytest.param((b'', (b'', (...,))), id='nested3'),
])
async def test_tail_optimization_in_deterministic_cases(kmock: RawHandler, ellipsis: Any) -> None:
    base_depth: int | None = None
    depths: list[int] = []

    def remember_stack_depth() -> None:
        nonlocal base_depth, depths
        stack = traceback.extract_stack()
        if base_depth is None:
            base_depth = len(stack)
        depths.append(len(stack) - base_depth)

    stream = kmock['/'] << (b"hello", ...)
    loop = asyncio.get_running_loop()
    loop.call_later(11, lambda: stream[...] >> remember_stack_depth << ellipsis)
    loop.call_later(22, lambda: stream[...] >> remember_stack_depth << ellipsis)
    loop.call_later(33, lambda: stream[...] >> remember_stack_depth)

    resp = await kmock.get('/')
    await resp.read()

    assert set(depths) == {0}


@pytest.mark.parametrize('ellipsis', [
    pytest.param(lambda: ..., id='direct'),
    pytest.param((b'', lambda: ...), id='nested1'),
    pytest.param((b'', (b'', lambda: ...)), id='nested2'),
    pytest.param((b'', (b'', (lambda: ...,))), id='nested3'),
    pytest.param((b'', (b'', ..., b'')), id='suffixed1'),
    pytest.param((b'', (b'', ...), b''), id='suffixed2'),
])
async def test_callstack_diving_in_nondeterministic_cases(kmock: RawHandler, ellipsis: Any) -> None:
    base_depth: int | None = None
    depths: list[int] = []

    def remember_stack_depth() -> None:
        nonlocal base_depth, depths
        stack = traceback.extract_stack()
        if base_depth is None:
            base_depth = len(stack)
        depths.append(len(stack) - base_depth)

    stream = kmock['/'] << (b"hello", ...)
    loop = asyncio.get_running_loop()

    loop.call_later(11, lambda: stream[...] >> remember_stack_depth << ellipsis)
    loop.call_later(22, lambda: stream[...] >> remember_stack_depth << ellipsis)
    loop.call_later(33, lambda: stream[...] >> remember_stack_depth)

    resp = await kmock.get('/')
    await resp.read()

    assert set(depths) != {0}  # typically [0, 2, 4] or [0, 1, 2]
