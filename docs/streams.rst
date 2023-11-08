===================
Streaming responses
===================

When the response content is one of the stream types (generally, iterablesexcept lists and sets) or a callable/awaitable which returns such an iterable, the response will be a stream — as used in the watch-streams of Kubernetes.

.. code-block:: python

    # Equivalent:
    kmock['/'] << 200 << b'hello\n' << b'world\n'
    kmock['/'] << 200 << (b'hello\n', b'world\n')


Stream types
============

These types of iterables are treated as streams when used in the response content:

* Ellipsis: ``...``
* Tuples: ``(…, …)``
* Iterators ``iter(…)``
* Generator iterators: ``(v for v in …)``.
* Generator functions: ``def f(): yield …; yield …``
* Other custom iterables.

But not lists & sets!


Stream content
==============

The streaming response sends the byte chunks one after another as they are generated from the items of the iterable that define the response. The items are treated similar to the response content, but with some nuances described below:

* ``...`` (``Ellipsis``) is treated as a :ref:`feeding point` for live streaming (described below).
* ``None`` is not sent, it does not affect the stream. It can be used e.g. to call a function to sleep for some time or wait for an event/future/task.
* ``bytes`` are sent as is.
* ``str``, ``int``, ``float``, ``bool``, ``list``, ``dict`` —i.e. all syntactically JSON-like objects— are encoded as JSON and sent on a separate line (with a newline added), thus simulating the JSON-lines format.
* ``tuple``, ``iter()``, sync/async generators, and other iterables (except for lists & sets) are unfolded as if their items were a part of the main stream. However, there is a subtle difference for replayable and depletable streams and stream parts (described below).
* ``open()``, ``pathlib.Path``, ``io.StringIO``, ``io.BytesIO`` are sent from the corresponding files, with strings encoded as UTF-8 but no newline added in the end.

In particular, ``pathlib.Path`` is reopened on every use, so that file is never depleted.

* Exceptions (classes and instances) are raised in place on the server side.
* Awaitables (coroutines, futures, tasks) & callables (functions, lambdas, partials) are unfolded in place and their result is streamed.

.. note::

    Mind that ``set``, ``frozenset``, and other sets are reserved for future ideas and not served now. They are not ordered so they would be a idea bad for streamed content; if random order is intended, shuffle the lists/tuples instead.


Exceptions in streams
=====================

Exceptions —either classes or instances— are raised in place on the server side. Generally, this makes little sense as it will simply break the mock server and disconnect the client, but several exceptions produce desired side effects:


Stream interuption
------------------

``StopIteration`` in a stream will stop the current request at this point. If it resides in a depletable stream or in a depletable part of a replayable stream, this can be used to simulate the varying content on multiple subsequent requests.


JSON payload
============

All items that look in Python like in JSON, are JSON-encoded and sent as a single line with a newline, thus simulating the JSON-lines format. This includes: lists ``[…,…]``, dicts ``{…:…}``, strings ``"…"``, integers and floats, and bools.

.. note::

    While ``b"hello"`` will be sent as these 5 symbols, ``"hello"`` will be sent as written — i.e. with double quotes, so that it could be JSON-decoded on the other side. Would you need to send strings as is, encode them to bytes explicitly: ``"hello".encode()``.


Replayable streams
==================

Tuples (``(…, …)``) are **replayable** streams, which means that if the same request is made multiple times, the same response will be sent each time:

.. code-block:: python

    kmock['/'] << ('Served always!',)
    kmock['/'] << ('Never happens!',)


Depletable streams
==================

Generator expressions (``(v for v in …)``), generator functions (``def fn(): yield…; yield…``), and iterators (``iter(…)``), are **depletable** streams, which means they will not be served again after served once::

    kmock['/'] << iter(['Served only once on the 1st request!'])
    kmock['/'] << iter(['Served only once on the 2nd request!'])

In particular, if the endpoint's response content is a depletable stream, the whole filter/content pair (i.e. only one of two lines above) will be deactivated after the request and will not be considered for serving again. This saves time on picking the depleted streams and getting nothing from them before getting to the next one.

# TODO: do we have a limit now, with the new syntax? probably not. then remove!
Mind that a replayable stream with the limit of 1 request is functionally equivalent to a depletable stream::

    kmock.add('/', ('Served only once on the 1st request!',), limit=1)
    kmock.add('/', iter(['Served only once on the 2nd request!']))


Partially depletable streams
============================

If a depletable sub-stream (a generator) is inside a replayable stream (a tuple), the main stream content will be served each time, but the depletable part will be skipped on subsequent requests::

    kmock['/'] << (
        'I am here each time.',
        iter(['This is seen only on the 1st request', StopIteration]),
        iter(['This is seen only on the 2nd request', StopIteration]),
        'This is shown on the 3rd, 4th, and further requests.',
    )


Callables/awaitables in streams
===============================

Callables/awaitables can behave both as replayable and as depletable streams depending on whether they return the same or different objects on each call: the same reused tuple object will be depleted, but the newly created tuple will be treated as a replayable stream::

    depleted_part = iter(['This line is shown only once, as it is the same generator each time.'])
    kmock['/'] << (
        lambda: iter(['This line is shown on each request, as it is a new generator each time.']),
        lambda: depleted_part,
    )


Reserved types
==============

``set``, ``frozenset``, and other sets are reserved for future ideas and not served now. They are unordered so they would be a bad idea for streamed content; if random order is intended, shuffle the tuples instead.

???
---


???
---
TODO: move to another section

Due to the support of callables & awaitables in streams, sleeping/waiting coroutine can be used to simulate a slow stream from the remote server:

.. code-block:: python

    import asyncio
    import math
    from kmock import RawHandler, Server


    async def main():
        async with RawHandler() as kmock, Server(kmock):
            # An event that is set with a 7-second delay.
            event = asyncio.Event()
            asyncio.get_running_loop().call_later(7, event.set)

            resource = kmock.resource('kopf.dev', 'v1', 'kopfexamples')
            kmock['watch', resource] << (
                b'{"type": "ADDED", "object": {}}\n',
                asyncio.sleep(3),  # continue after 3 seconds
                {"type": "MODIFIED", "object": {}},
                event.wait(),  # continue after 4 more seconds (7-3=4)

                # Simulate 10 object updates, one per second.
                # Lambda is needed to have fresh timestamps on every call.
                lambda: [
                    [
                        lambda: {"type": "MODIFIED", "object": {"status": {"time": datetime.datetime.utc(tz=daetime.UTC).isoformat()}}},
                        asyncio.sleep(1),
                    ]
                    for i in range(10)
                ],
            )

            await asyncio.Event().wait()  # sleep forever until interrupted by Ctrl-C


    if __name__ == '__main__':
        asyncio.run(main())

In the example above, the inner lambda is needed to provide up-to-date timestamps (executed when the event is streamed, not when it is declared). The outer lambda is needed to ensure that multiple requests to the same endpoint provide the new stream instead of trying to continue the previously started one (read how iterator-generators are "depleted" in Python).


Live streams
------------

# TODO: how do we feed? there is a new syntax.
Streams can have "feeding points" marked as ``...`` (literally three dots, also known as ``Ellipsis``). You can read this as "to be continued". In that case, the request blocks at the feeding point and waits for new items to be fed into the stream via ``Reaction.feed``.

The stream only streams the items fed strictly after the stream reached the feeding point. Previously fed items are not preserved and not replayed.

If the newly fed items do not contain the new feeding point, the stream unblocks and continues till the end (or finishes immediately if there are no scheduled items left). To keep the stream infinitely blocking, add a new feeding point on every feeding.


.. code-block:: python

    async def consume_stream(url):
        async with aiohttp.ClientSession() as session:
            rsp = session.get(url)
            rsp.raise_for_status()
            for chunk in rsp.content.iter_chunked():
                print(f"{chunk!r}")

    stream = kmock.add('get', '/', ('Hello!', ..., 'Good bye!'))
    asyncio.create_task(consume_stream(kmock.url))

    stream.feed(b'Countdown:\n', ...)
    for i in range(3, 0, -1):
        stream.feed(i, asyncio.sleep(1), ...)
    stream.feed()  # finishes the stream because no new feeding point
    # Hello!
    # Countdown:
    # 3
    # 2
    # 1
    # Good bye!


.. note::

    Live streams are tail-optimized: if the feeding point is deterministicaly the last item on the stream, there will be no recursion involved to save resources. This covers the cases like ``stream.add((1,2,3,...))`` or even with nested tuples ``stream.add((1,(2,(3,(...)))))``.

    However, non-deterministic cases are not optimized and use the recursion. E.g., callables/awaitables that return the Ellipsis in the result: ``stream.add((1, 2, 3, lambda: ...))``.

    Similarly, the non-tailing Ellipsis is not optimized as there is need to persist and stream the stream-closing items: ``stream.add((b"hello", ..., b"good-bye"))``.

.. warning::

    The feeding routine is synchronous for the syntactic simplicity, so it can be used even in the sync tests with sync HTTP/API clients. However, it uses some asynchronous machinery behind — a queue and a task to get from the queue and put to the bus. As such, there can be a minor delay after the ``feed()`` has returned and before the item is noticed. If you do not do ``await`` inbetween, the queue/bus/stream can be blocked with no actual streaming, so either async tests/routines are recommended anyway, or the feeding must be happening in a parallel thread.

    The feeding routine can also be used with ``await`` as if it were an async coroutine. For that, it returns a future on every feeding, which is set when the items are delivered to the queue of items being fed. This eliminates the delay.
