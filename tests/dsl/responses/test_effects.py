import asyncio
import concurrent.futures
import io
import queue
import sys
import threading
from typing import Any, AsyncIterator, Iterator

import pytest

from kmock import Bus, RawHandler, Request, Response, SinkBox

pytestmark = [pytest.mark.kmock(cls=RawHandler), pytest.mark.looptime]


@pytest.mark.parametrize('arg', [
    pytest.param(123, id='int'),
    pytest.param('hello', id='str'),
    pytest.param(b'hello', id='bytes'),
    pytest.param(True, id='bytes'),
    pytest.param(False, id='bytes'),
    # pytest.param({}, id='dict'),  # TODO: test it together with sets & lists
    pytest.param(frozenset(), id='frozenset'),
])
async def test_unsupported_effects(kmock: RawHandler, arg: Any) -> None:
    with pytest.raises(ValueError, match=r"Unsupported type.*"):
        kmock['/'] >> arg
    with pytest.raises(ValueError, match=r"Unsupported type.*"):
        arg << kmock['/']

    # But if forced:
    kmock['/'] << Response(payload=SinkBox(lambda: arg))  # wrapped to avoid the validation/guessing
    resp = await kmock.get('/')
    text = await resp.read()
    assert resp.status == 500
    assert b'ValueError: Unsupported side-effect type' in text


async def test_nones_ignored_in_effects(kmock: RawHandler) -> None:
    kmock['/'] >> None << b'hello'
    resp = await kmock.get('/')
    text = await resp.read()
    assert text == b'hello'


async def test_callables_with_no_args_invocation(kmock: RawHandler) -> None:
    called = False

    def fn() -> None:
        nonlocal called
        called = True
        return

    kmock['/'] >> fn << b'hello'
    resp = await kmock.get('/')
    text = await resp.read()
    assert called
    assert text == b'hello'


async def test_callables_with_one_arg_invocation(kmock: RawHandler) -> None:
    called = False

    def fn(req: kmock.Request) -> None:
        nonlocal called
        called = True
        return

    kmock['/'] >> fn << b'hello'
    resp = await kmock.get('/')
    text = await resp.read()
    assert called
    assert text == b'hello'


async def test_awaitables(kmock: RawHandler) -> None:
    reqs: list[Request] = []

    async def fn() -> list[Request]:
        return reqs

    kmock['/'] >> fn() << b'hello'
    resp = await kmock.get('/')
    text = await resp.read()
    assert text == b'hello'
    assert len(reqs) == 1
    assert isinstance(reqs[0], Request)


def sync_gen(count: int, reqs: list[Request]) -> Iterator[None]:
    for _ in range(count):
        result = yield
        reqs.append(result)


async def async_gen(count: int, reqs: list[Request]) -> AsyncIterator[None]:
    for _ in range(count):
        result = yield
        reqs.append(result)


@pytest.mark.parametrize('count, fn', [
    pytest.param(0, sync_gen, id='zero-step-sync'),
    pytest.param(0, async_gen, id='zero-step-async'),
    pytest.param(1, sync_gen, id='single-step-sync'),
    pytest.param(1, async_gen, id='single-step-async'),
    pytest.param(2, sync_gen, id='double-step-sync'),
    pytest.param(2, async_gen, id='double-step-async'),
])
async def test_generators(kmock: RawHandler, count: int, fn: Any) -> None:
    reqs: list[Request] = []
    kmock['/'] >> fn(count, reqs) << b'hello'
    for _ in range(9):  # both the initial & repeated injections, including after the exit
        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'hello'
    assert len(reqs) == count
    assert all(isinstance(req, Request) for req in reqs)


async def test_generators_escalate(kmock: RawHandler) -> None:
    async def fn() -> AsyncIterator[None]:
        yield
        raise TypeError("boo!")

    kmock['/'] >> fn() << b'hello'
    resp = await kmock.get('/')
    text = await resp.read()
    assert b'TypeError: boo!' in text


async def test_lists_population(kmock: RawHandler) -> None:
    reqs: list[Request] = []
    kmock['/'] >> reqs << b'hello'
    await kmock.get('/')
    assert len(reqs) == 1
    assert isinstance(reqs[0], Request)


async def test_sets_population(kmock: RawHandler) -> None:
    reqs: set[Request] = set()
    kmock['/'] >> reqs << b'hello'
    await kmock.get('/')
    assert len(reqs) == 1
    assert isinstance(list(reqs)[0], Request)


@pytest.mark.parametrize('event_cls', [asyncio.Event, threading.Event])
async def test_events_setting(kmock: RawHandler, event_cls: Any) -> None:
    event = event_cls()
    kmock['/'] >> event << b'hello'
    await kmock.get('/')
    assert event.is_set()


@pytest.mark.parametrize('future_cls', [asyncio.Future, concurrent.futures.Future])
async def test_futures_setting(kmock: RawHandler, future_cls: Any) -> None:
    future = future_cls()
    kmock['/'] >> future << b'hello'
    await kmock.get('/')
    assert future.done()
    request = future.result()
    assert isinstance(request, Request)


@pytest.mark.parametrize('queue_cls', [asyncio.Queue, queue.Queue])
async def test_queues_feeding(kmock: RawHandler, queue_cls: Any) -> None:
    queue = queue_cls()
    kmock['/'] >> queue << b'hello'
    await kmock.get('/')
    request = queue.get_nowait()
    assert isinstance(request, Request)


@pytest.mark.looptime
@pytest.mark.skipif(sys.version_info < (3, 11), reason="asyncio.timeout() is available since 3.11+")
async def test_feeding_buses(kmock: RawHandler, looptime: int) -> None:
    bus = Bus()
    mark = await bus.mark()
    kmock['/'] >> bus << b'hello'
    await kmock.get('/')
    assert bus.streamed_count == 1
    assert bus.buffer_size == 1
    reqs: list[Request] = []
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(1):
            async for request in mark:
                reqs.append(request)
    await bus.unmark(mark)
    assert looptime == 1
    assert len(reqs) == 1
    assert all(isinstance(request, Request) for request in reqs)


async def test_async_condition_notifying(kmock: RawHandler) -> None:
    counter = 0
    condition = asyncio.Condition()
    kmock['/'] >> condition << b'hello'

    async def wait() -> None:
        nonlocal counter
        while True:
            async with condition:
                await condition.wait()
                counter += 1

    task = asyncio.create_task(wait())
    await kmock.get('/')
    assert counter == 1
    await kmock.post('/')
    assert counter == 2

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def test_sync_condition_notifying(kmock: RawHandler) -> None:
    exited = False
    counter = 0
    ready = threading.Event()
    condition = threading.Condition()
    kmock['/'] >> condition << b'hello'

    def wait() -> None:
        nonlocal counter, condition, ready
        while not exited:
            with condition:
                ready.set()
                condition.wait()
                counter += 1

    thread = threading.Thread(target=wait)
    thread.start()
    ready.wait()

    await kmock.get('/')
    assert counter == 1
    await kmock.post('/')
    assert counter == 2

    exited = True
    with condition:
        condition.notify_all()
    thread.join()


async def test_paths_writing(kmock: RawHandler, tmp_path: Any) -> None:
    path = tmp_path / "test.txt"
    path.write_bytes(b'it should be overwritten')
    kmock['/'] >> path << b'hello'
    resp = await kmock.get('/', data=b'world')
    text = await resp.read()
    assert text == b'hello'
    dump = path.read_text()
    assert dump == 'world'


async def test_raw_io_writing(kmock: RawHandler, tmp_path: Any) -> None:
    path = tmp_path / "test.txt"
    path.write_bytes(b'world')
    file = io.FileIO(str(path), 'wb')  # io.RawBaseIO
    kmock['/'] >> file << b'hello'
    resp = await kmock.get('/', data=b'world')
    text = await resp.read()
    assert text == b'hello'
    dump = path.read_text()
    assert dump == 'world'


async def test_text_io_writing(kmock: RawHandler, tmp_path: Any) -> None:
    path = tmp_path / "test.txt"
    path.write_bytes(b'world')
    file = io.TextIOWrapper(io.FileIO(str(path), 'w'), encoding='utf-8')  # io.TextIOBase
    kmock['/'] >> file << b'hello'
    resp = await kmock.get('/', data=b'world')
    text = await resp.read()
    assert text == b'hello'
    file.flush()
    dump = path.read_text()
    assert dump == 'world'


async def test_buffered_io_writing(kmock: RawHandler, tmp_path: Any) -> None:
    path = tmp_path / "test.txt"
    path.write_bytes(b'world')
    file = io.BufferedWriter(io.FileIO(str(path), 'w'))  # io.BufferedIOBase
    kmock['/'] >> file << b'hello'
    resp = await kmock.get('/', data=b'world')
    text = await resp.read()
    assert text == b'hello'
    file.flush()
    dump = path.read_text()
    assert dump == 'world'


async def test_bytes_io_writing(kmock: RawHandler, tmp_path: Any) -> None:
    file = io.BytesIO(b'world')  # io.BufferedIOBase
    kmock['/'] >> file << b'hello'
    resp = await kmock.get('/', data=b'world')
    text = await resp.read()
    assert text == b'hello'
    dump = file.getvalue()
    assert dump == b'world'


async def test_string_io_writing(kmock: RawHandler, tmp_path: Any) -> None:
    file = io.StringIO('world')  # io.BufferedIOBase
    kmock['/'] >> file << b'hello'
    resp = await kmock.get('/', data=b'world')
    text = await resp.read()
    assert text == b'hello'
    dump = file.getvalue()
    assert dump == 'world'


# Assume that if it works for one effect this way, it works for all of them.
# Mind that it is impossible to chain 2+ items, since << & >> go left-to-right.
async def test_reversed_effects(kmock: RawHandler) -> None:
    reqs: list[Request] = []
    reqs << kmock['/']
    await kmock.get('/')
    assert len(reqs) == 1
    assert isinstance(reqs[0], Request)
