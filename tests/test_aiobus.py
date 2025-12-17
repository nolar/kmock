import asyncio
import sys
from typing import Any

import pytest

import kmock
from kmock import Bus, BusMark


async def test_bus_marking() -> None:
    bus: Bus[Any] = Bus()
    assert bus.consumer_count == 0
    assert bus.streamed_count == 0
    assert bus.removed_count == 0
    assert bus.buffer_size == 0

    mark = await bus.mark()
    assert bus.consumer_count == 1
    assert bus.streamed_count == 0
    assert bus.removed_count == 0
    assert bus.buffer_size == 0

    await bus.put('hello')
    assert bus.consumer_count == 1
    assert bus.streamed_count == 1
    assert bus.removed_count == 0
    assert bus.buffer_size == 1

    item = await bus.get(since=mark)
    assert item == 'hello'
    assert bus.consumer_count == 1
    assert bus.streamed_count == 1
    assert bus.removed_count == 1
    assert bus.buffer_size == 0

    await bus.unmark(mark)
    assert bus.consumer_count == 0
    assert bus.streamed_count == 1
    assert bus.removed_count == 1
    assert bus.buffer_size == 0


async def test_bus_with_unknown_mark() -> None:
    bus = Bus()
    mark = BusMark(bus)  # created not via bus.mark()
    with pytest.raises(ValueError, match=r"Unknown bus marker:"):
        await bus.unmark(mark)
    with pytest.raises(ValueError, match=r"Unknown bus marker:"):
        async for _ in bus.stream(mark):
            pass


async def test_bus_with_alien_mark() -> None:
    bus = Bus()
    mark = await Bus().mark()  # created from an alien bus
    with pytest.raises(RuntimeError, match=r"A marker is from another bus."):
        await bus.unmark(mark)
    with pytest.raises(RuntimeError, match=r"A marker is from another bus."):
        async for _ in bus.stream(mark):
            pass


async def test_bus_flushing_on_producing_with_no_consumers() -> None:
    bus: Bus[Any] = Bus(flush_threshold=3)
    assert bus.removed_count == 0
    assert bus.buffer_size == 0

    await bus.put('hello')
    assert bus.removed_count == 0
    assert bus.buffer_size == 1

    await bus.put('world')
    assert bus.removed_count == 0
    assert bus.buffer_size == 2

    await bus.put('FLUSH')
    assert bus.removed_count == 3  # flushed!
    assert bus.buffer_size == 0

    await bus.put('hello')
    assert bus.removed_count == 3
    assert bus.buffer_size == 1

    await bus.put('again')
    assert bus.removed_count == 3
    assert bus.buffer_size == 2

    await bus.put('FLUSH')
    assert bus.removed_count == 6  # flushed!
    assert bus.buffer_size == 0

    await bus.put('rinse&repeat')
    assert bus.removed_count == 6
    assert bus.buffer_size == 1


async def test_bus_flushing_on_consuming() -> None:
    bus: Bus[Any] = Bus(flush_threshold=3)
    mark = await bus.mark()
    for i in range(7):
        await bus.put(f'hello-{i}')
    assert bus.removed_count == 0
    assert bus.buffer_size == 7

    item = await bus.get(since=mark)
    assert item == 'hello-0'
    assert bus.removed_count == 0
    assert bus.buffer_size == 7

    item = await bus.get(since=mark)
    assert item == 'hello-1'
    assert bus.removed_count == 0
    assert bus.buffer_size == 7

    item = await bus.get(since=mark)
    assert item == 'hello-2'
    assert bus.removed_count == 3  # flushed!
    assert bus.buffer_size == 4

    item = await bus.get(since=mark)
    assert item == 'hello-3'
    assert bus.removed_count == 3
    assert bus.buffer_size == 4

    item = await bus.get(since=mark)
    assert item == 'hello-4'
    assert bus.removed_count == 3
    assert bus.buffer_size == 4

    item = await bus.get(since=mark)
    assert item == 'hello-5'
    assert bus.removed_count == 6  # flushed!
    assert bus.buffer_size == 1

    item = await bus.get(since=mark)
    assert item == 'hello-6'
    assert bus.removed_count == 6
    assert bus.buffer_size == 1

    await bus.unmark(mark)


async def test_bus_flushing_explicitly() -> None:
    bus: Bus[Any] = Bus(flush_threshold=3)
    await bus.put('hello')
    assert bus.removed_count == 0
    assert bus.buffer_size == 1
    await bus.flush()
    assert bus.removed_count == 1
    assert bus.buffer_size == 0


@pytest.mark.looptime
@pytest.mark.skipif(sys.version_info < (3, 11), reason="asyncio.timeout() is available since 3.11+")
async def test_bus_streaming_entirely(looptime: int) -> None:
    bus: Bus[Any] = Bus()
    with pytest.raises(asyncio.TimeoutError):
        async with asyncio.timeout(3):
            mark = await bus.mark()
            await bus.put('hello')
            await bus.put('world')
            await bus.put('again')
            async for item in bus.stream(mark):
                assert item in {'hello', 'world', 'again'}
                assert looptime == 0
    assert bus.consumer_count == 1
    assert looptime == 3


@pytest.mark.looptime
@pytest.mark.skipif(sys.version_info < (3, 11), reason="asyncio.timeout() is available since 3.11+")
async def test_bus_streaming_till_limit(looptime: int) -> None:
    bus: Bus[Any] = Bus()
    async with asyncio.timeout(1):
        mark = await bus.mark()
        await bus.put('hello')
        await bus.put('world')
        await bus.put('again')
        async for item in bus.stream(mark, limit=2):
            assert item in {'hello', 'world'}
            assert looptime == 0
    assert bus.consumer_count == 1
    assert looptime == 0


@pytest.mark.looptime
@pytest.mark.skipif(sys.version_info < (3, 11), reason="asyncio.timeout() is available since 3.11+")
async def test_bus_streaming_exceptions(looptime: int) -> None:
    # NB: different mark variables to prevent weakref gc in CPython and behave as PyPy does.
    bus: Bus[Any] = Bus()
    with pytest.raises(BaseException):
        async with asyncio.timeout(1):
            mark1 = await bus.mark()
            await bus.put(BaseException)
            async for _ in bus.stream(mark1, limit=1):
                assert False
    with pytest.raises(BaseException, match=r"boo!"):
        async with asyncio.timeout(1):
            mark2 = await bus.mark()
            await bus.put(BaseException("boo!"))
            async for _ in bus.stream(mark2, limit=1):
                assert False
    assert bus.consumer_count == 2
    assert looptime == 0


@pytest.mark.looptime
@pytest.mark.skipif(sys.version_info < (3, 11), reason="asyncio.timeout() is available since 3.11+")
async def test_bus_streaming_blocks(looptime: int) -> None:
    bus: Bus[Any] = Bus()
    with pytest.raises(asyncio.TimeoutError):
        async with asyncio.timeout(3):
            async for _ in bus:
                assert False
    assert bus.consumer_count == 0
    assert looptime == 3


@pytest.mark.looptime
@pytest.mark.skipif(sys.version_info < (3, 11), reason="asyncio.timeout() is available since 3.11+")
async def test_bus_getting_blocks(looptime: int) -> None:
    bus: Bus[Any] = Bus()
    with pytest.raises(asyncio.TimeoutError):
        async with asyncio.timeout(3):
            await bus.get()
    assert bus.consumer_count == 0
    assert looptime == 3


@pytest.mark.looptime
@pytest.mark.skipif(sys.version_info < (3, 11), reason="asyncio.timeout() is available since 3.11+")
async def test_bus_getting_from_marker(looptime: int) -> None:
    bus: Bus[Any] = Bus()
    mark = await bus.mark()
    await bus.put('hello')
    async with asyncio.timeout(3):
        item = await bus.get(since=mark)
    await bus.unmark(mark)
    assert item == 'hello'
    assert bus.consumer_count == 0
    assert looptime == 0


@pytest.mark.looptime
@pytest.mark.skipif(sys.version_info < (3, 11), reason="asyncio.timeout() is available since 3.11+")
async def test_bus_getting_from_now(looptime: int) -> None:
    bus: Bus[Any] = Bus()
    await bus.put('ignored')

    async def putter() -> None:
        await asyncio.sleep(1)
        await bus.put('hello')

    task = asyncio.create_task(putter())
    async with asyncio.timeout(3):
        item = await bus.get()
    assert item == 'hello'
    assert looptime == 1

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
