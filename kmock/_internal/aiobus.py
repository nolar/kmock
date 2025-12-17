import asyncio
import weakref
from collections.abc import AsyncIterable, AsyncIterator
from typing import Generic, TypeVar

import attrs

T = TypeVar('T')


# I beg you, keep the name! ;-)
class BusGone(Exception):
    pass


@attrs.frozen(weakref_slot=True, eq=False, order=False)
class BusMark(Generic[T], AsyncIterable[T]):
    """
    A single mark in the bus.

    For brevity, the mark can be directly used to stream from its bus
    since this mark's position, as if streamed from the `Bus.since`.
    """
    bus: "Bus[T]"

    async def __aiter__(self) -> AsyncIterator[T]:
        async for item in self.bus.stream(since=self):  # pragma: no branch
            yield item


@attrs.mutable(weakref_slot=True)
class Bus(Generic[T], AsyncIterable[T]):
    """
    A data bus with multiple writers and multiple readers.

    A bus is similar to a queue but multiple consumers get the same data.

    Each consumer gets the data in the order they were added to the bus.
    The data is consumed since the moment the consumer connects to the bus.
    The earlier data is not available.

    The bus consumes only as much memory as needed to store the items that
    were not yet consumed by all _active_ consumers. Once the latest (slowest)
    consumer gets its data, the buffered items are flushed (garbage collected).

    The flushing of buffers can be postponed until the size of the unused buffer
    (the number of items that will never be streamed) reaches the threshold.
    By default, the threshold is 0 and the bus flushes the buffers as soon
    as possible. Even with the threshold, flushing can be forced with `flush`.

    Because of this, the bus can stream significant number of items for long
    periods of time without OOM (unless one of the consumers stops consuming).

    The buffer size can be restricted to a number of items (default: unlimited).
    If so, the consumers that come for their next item after the item
    is garbage collected, will get the `BusItemGone` exception.

    The properties `buffer_size`, `streamed_count`, and `removed_count`
    can be used to monitor the current memory consumption and performance.

    There is no synchronous getting/streaming from the bus by design.
    """
    flush_threshold: int = 0
    max_buffer_size: int | None = None

    _condition: asyncio.Condition = attrs.field(init=False, factory=asyncio.Condition)
    _streamed_count: int = attrs.field(init=False, default=0)
    _removed_count: int = attrs.field(init=False, default=0)
    _buffer: list[T] = attrs.field(init=False, factory=list)
    _offsets: dict[BusMark[T], int] = attrs.field(init=False, factory=weakref.WeakKeyDictionary)

    @property
    def consumer_count(self) -> int:
        return len(self._offsets)

    @property
    def streamed_count(self) -> int:
        """The total number of items put into the bus since creation."""
        return self._streamed_count

    @property
    def removed_count(self) -> int:
        """The number of items removed from the bus after full consumption."""
        return self._removed_count

    @property
    def buffer_size(self) -> int:
        """The number of items currently stored in the bus's buffers."""
        return len(self._buffer)

    async def __aiter__(self) -> AsyncIterator[T]:
        marker = await self.mark()
        try:
            async for item in self.stream(since=marker):
                yield item
        finally:  # incl. GeneratorExit
            await self.unmark(marker)

    async def stream(self, since: BusMark[T], *, limit: int | None = None) -> AsyncIterator[T]:
        """
        Iterate over items submitted to the bus since the marked position.

        Usage::

            marker = await bus.mark()
            do_something()
            async for item in bus.since(marker):
                process_item(item)
        """
        if since.bus is not self:
            raise RuntimeError("A marker is from another bus.")
        if since not in self._offsets:
            raise ValueError(f"Unknown bus marker: {since!r}")

        # Beware: any math with offsets must be protected by the lock; and it should be fast!
        # Formulas: physical_offset = virtual_offset - removed_count
        # Formulas: virtual_offset = physical_offset + removed_count
        streamed_count = 0
        while limit is None or streamed_count < limit:

            # Mark the current buffer cursor and wait for the new items and new positions.
            async with self._condition:
                physical_start_offset = self._offsets[since] - self._removed_count
                physical_end_offset = len(self._buffer) if limit is None else physical_start_offset + limit - streamed_count
                virtual_end_offset = physical_end_offset + self._removed_count
                stream_chunk = self._buffer[physical_start_offset:physical_end_offset]

                if not stream_chunk:
                    await self._condition.wait()

            # Stream the specific range even if new items are added while yielding the old ones.
            # Note: outside of the lock — processing can be slow, the lock must remain free.
            for item in stream_chunk:

                # Update the new offset on every item. The processing can be slow,
                # but garbage collection can be done by other consumers/tasks.
                async with self._condition:
                    self._offsets[since] = virtual_end_offset

                # Garbage collect early: the current chunk will not be processed again.
                await self._flush()

                # NB: yield outside of the lock! Processing can be slow, the lock must be free.
                # A special handling for errors: raise them right in the stream.
                match item:
                    case type() if issubclass(item, BaseException):
                        raise item
                    case BaseException():
                        raise item
                    case _:
                        yield item
                        streamed_count += 1

    async def mark(self) -> BusMark[T]:
        """
        Mark a position in the bus for further iteration since it.

        The marker is then passed to ``bus(since=marker)`` iterator
        for continuation, potentially many times.

        The position is kept as long as the object is not garbage-collected
        or until ``bus.unmark(marker)`` is explicitly called.

        Mind that the marker is not the same as the current position.
        The marker moves over time. Each marker has its own position.
        To keep N different positions, create N different markers.

        As soon as the marker is abandoned (garbage-collected), the position
        is lost as if the mark was explicitly released. However, the bus
        does not release the memory until something else consumes from the bus.
        """
        # Keep this object away from garbage collection to prevent premature flushing.
        marker = BusMark(self)
        async with self._condition:
            self._offsets[marker] = self._removed_count + len(self._buffer)
        return marker

    async def unmark(self, marker: BusMark[T]) -> None:
        """
        Explicitly release the previously marked position.

        In CPython, it is enough to "forget" the marker and let it be
        garbage-collected to release the bus's buffer. However, in PyPy,
        or if CPython's garbage collection is disabled, the marker can
        hold the buffer from being flushed, thus increasing the memory usage.
        Explicit unmarking solves this problem.
        """
        if marker.bus is not self:
            raise RuntimeError("A marker is from another bus.")
        if marker not in self._offsets:
            raise ValueError(f"Unknown bus marker: {marker!r}")
        async with self._condition:
            del self._offsets[marker]
        await self._flush()

    async def get(self, since: BusMark[T] | None = None) -> T:
        """Get only one item. Block until it arrives."""
        # Implemented via streaming, so leave no open iterators at exit (for gc off as in PyPy).
        if since is not None:
            async for item in self.stream(since=since, limit=1):
                return item
        else:
            managed_marker = await self.mark()
            try:
                async for item in self.stream(since=managed_marker, limit=1):  # pragma: no branch
                    return item
            finally:  # incl. GeneratorExit
                await self.unmark(managed_marker)
        raise RuntimeError("It should never get here.")  # pragma: no cover  # for type-checkers

    async def put(self, *items: T) -> None:
        async with self._condition:
            self._buffer.extend(items)
            self._condition.notify_all()
            self._streamed_count += len(items)
        await self._flush()  # in case no one is consuming

    async def flush(self) -> None:
        """
        Release the memory from items already consumed by all consumers, if any.

        Normally, this is done automatically as soon as the items are consumed.
        However, if the flushing threshold is set, some items can accumulate.
        Explicit call of this method flushes them regardless of the threshold.
        """
        await self._flush(forced=True)

    async def _flush(self, forced: bool = False) -> None:
        async with self._condition:
            offsets = set(self._offsets.values())
            lowest_virtual_offset = min(offsets) if offsets else self._streamed_count
            lowest_physical_offset = lowest_virtual_offset - self._removed_count
            if forced or lowest_physical_offset >= self.flush_threshold:
                self._buffer[:lowest_physical_offset] = []
                self._removed_count += lowest_physical_offset
