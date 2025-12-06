===================
Streaming responses
===================

Streams syntax
==============

When the response content is one of the stream types (generally, iterables except lists and sets) or a callable/awaitable which returns such an iterable, the response will be a stream — as used in the watch-streams of Kubernetes. As with regular responses, the stream payload must be defined via the ``<<`` operation on the filters. Alternatively, a few sequential ``<<`` operations form a replayable stream, which is not much different from the regular prepared responses.

The streams are different from regular prepared responses in that, first, some stream types can be consumed and even depleted by multiple requests, i.e. the source of the stream is shared by requests, while in regular responses the same content is returned to all requests; and second, unlike the prepared responses, the streams can have a continuation, where they freeze and do not close the connection, waiting for the new data to be injected into the stream.

These types of iterables or markers are treated as streams when used in the response content:

* Ellipsis: ``...``.
* Tuples: ``(…, …)``
* Iterators ``iter(…)``
* Generator iterators: ``(v for v in …)``.
* Generator functions: ``def f(): yield …; yield …``
* Other custom iterables.

A simple example of streaming responses:

.. code-block:: python

    import kmock

    async def test_streams(kmock: kmock.RawHandler) -> None:
        # Equivalent replayable streams:
        kmock['/'] << 200 << b'hello\n' << b'world\n'
        kmock['/'] << 200 << (b'hello\n', b'world\n')

        # A stream with a continuation, which freezes and wait for new data:
        kmock['/'] << 200 << (b'hello\n', b'world\n', ...)

        # Inject the new data into the stream:
        kmock['/'][...] << b'again\n'

.. note::

    Mind that ``set``, ``frozenset``, and other sets are reserved for future ideas and not served now. They are not ordered so they would be a idea bad for streamed content; if random order is intended, shuffle the lists/tuples instead.


Streams meta-data
=================

``None`` in streams sends nothing and is ignored, it does not affect the stream. ``None`` can be used e.g. to call a function to sleep for some time or wait for an event/future/task before continuing the stream.

Similarly but differently, and empty binary blob ``b""`` also does not send anything in practice. However, this empty blob is not ignored, it initiates the streaming response on the server side, specifically it sends all accumulated response headers, so that the client can start consuming the stream instead of waiting for the server to respond.

As a rule, the streaming response does not actually start streaming until something useful is written to it, include the empty blob, but not ``None``. This allows the server to accumulate the response metadata, such as the HTTP satus code, headers, cookies, etc. Once the first bit of the useful payload arrives, all that accumulated metadata is sent, and changing/accumulating more of it becomes impossible.

.. code-block:: python

    import kmock

    async def test_streams_metadata(kmock: kmock.RawHandler) -> None:
        kmock['/'] << 404 << {'X-Server-Version': '1.2.3'} << (b'',)

        resp = await kmock.get('/')
        text = await resp.read()
        assert resp.status == 404
        assert resp.headers['X-Server-Version'] == '1.2.3'
        assert text == b''


Streams payloads
================

Streaming with JSON-lines
-------------------------

To stream the JSON-lines format, use the JSON-like data structures, in particular ``str``, ``int``, ``float``, ``bool``, ``list``, ``dict``. All these values are encoded as JSON and sent on a single line ending with a newline. Multiple items of the stream are sent one after another, forming the JSON-lines format.

.. code-block:: python

    import kmock

    async def test_json_lines_stream(kmock: kmock.RawHandler) -> None:
        kmock['/'] << {'hello': 'world'} << [123, 456]

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'{"hello": "world"}\n[123, 456]\n'

.. note::

    While ``b"hello"`` will be sent as these 5 symbols, ``"hello"`` will be sent as written — i.e. with double quotes, so that it could be JSON-decoded on the other side. Would you need to send strings as is, encode them to bytes explicitly: ``"hello".encode()``.


Streaming with binary blobs
---------------------------

To stream the raw binary blobs as is, use the ``bytes`` type. It is sent to the stream unprocessed and uninterpreted.

.. code-block:: python

    import kmock

    async def test_binary_blobs_streaming(kmock: kmock.RawHandler) -> None:
        kmock['/'] << (b'hello', b'world') << b'again'

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'helloworldagain'


Streaming from files
--------------------

To stream from a local file, which is consumed globally for all incoming requests, use the built-in :func:`open` function. Beware that open files become depleted for subsequent requests as they are consumed (unless something is appended to the file).

.. code-block:: python

    import kmock

    async def test_responses_from_open_files(kmock: kmock.RawHandler, tmp_path) -> None:
        path = tmp_path / "file.txt"
        path.write_bytes(b'hello')
        kmock['/'] << (open(str(path)), b'//end')

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'hello//end'

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'//end'  # the file has been depleted, but the stream is not


Streaming from paths
--------------------

To stream from an existing file repeatedly on requests, use the :class:`pathlib.Path`. The file will be reopened on every request and send entirely, so it is not much different from sending as a regular response — it never depletes. However, it can be a part of a bigger stream if needed.

.. code-block:: python

    import kmock

    async def test_paths_streaming(kmock: kmock.RawHandler, tmp_path) -> None:
        path = tmp_path / "file.txt"
        path.write_bytes(b'hello')
        kmock['/'] << (path, b'//end')

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'hello//end'

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'hello//end'  # the file was reopened


Streaming from IO buffers
-------------------------

To stream from a textual or binary buffers, use the :class:`io.StringIO` and :class:`io.BytesIO` accordingly. Technically, all descendants of the StdLib's :class:`io.RawIOBase`, :class:`io.BufferedIOBase`, :class:`io.TextIOBase` are supported if you have your own i/o classes.

Note that the buffer is consumed and depleted on requests because its current position moves forward to the end of the buffer, so the 2nd and following requests might get nothing if nothing is added to the buffer:

.. code-block:: python

    import kmock

    async def test_binary_buffers_streaming(kmock: kmock.RawHandler) -> None:
        buffer = io.StringIO('prepared buffer')
        kmock['/'] << (buffer, b'//end')

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'prepared buffer//end'

        buffer.write('appended buffer')

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'appended buffer//end'


Errors in streams
=================

Exceptions —either classes or instances— are raised in place on the server side. Generally, this makes little sense as it will simply break the mock server and disconnect the client, but several exceptions produce desired side effects:


StopIteration exceptions
------------------------

:class:`StopIteration` and :class:`StopAsyncIteration` in a stream will stop the current request at this point. If it resides in a depletable stream or in a depletable part of a replayable stream, this can be used to simulate the varying content on multiple subsequent requests.


Replayable streams
==================

To construct a stream which is replayed on every new request multiple times, use tuples (``(…, …)``) — they are **replayable** streams:

.. code-block:: python

    import kmock

    async def test_replayable_stream(kmock: kmock.RawHandler) -> None:
        kmock['/'] << (b'Served always!',)
        kmock['/'] << (b'Never happens!',)

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'Served always!'

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'Served always!'


Depletable streams
==================

To construct a stream that is shared across multiple requests and can be eventually depleted, use generator expressions (``(v for v in …)``), generator functions (``def fn(): yield…; yield…``), or iterators (``iter(…)``) — they are **depletable** streams:

.. code-block:: python

    import kmock

    async def test_depletable_stream(kmock: kmock.RawHandler) -> None:
        kmock['/'] << iter([b'Served only once on the 1st request!'])
        kmock['/'] << iter([b'Served only once on the 2nd request!'])

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'Served only once on the 1st request!'

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'Served only once on the 2nd request!'

In particular, if the endpoint's response content is a depletable stream, the whole filter/content pair will be deactivated after the request and will not be considered for serving again. This saves time on picking the depleted streams and getting nothing from them before getting to the next one. This is an internal optimization which does not affect the declared behavior of depletable streams.


Partially depletable streams
============================

If a depletable sub-stream (a generator) is inside a replayable stream (a tuple), the main stream content will be served each time, but the depletable part will be skipped on subsequent requests.

Note in this example that the stream goes until the first :class:`StopIteration` exception or till the end. In particular, the depletable sub-streams raise this exception once they are served, interrupting that individual request, but they will not be consumed and therefore will not raise the exception on the next requests because they become depleted:

.. code-block:: python

    import kmock

    async def test_mixed_streams(kmock: kmock.RawHandler) -> None:
        # Form a replayable stream with depeletable constituents:
        kmock['/'] << (
            b'I am here each time. ',
            iter([b'This is seen only on the 1st request.', StopIteration]),
            iter([b'This is seen only on the 2nd request.', StopIteration]),
            b'This is shown on the 3rd, 4th, and further requests.',
        )

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'I am here each time. This is seen only on the 1st request.'

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'I am here each time. This is seen only on the 2nd request.'

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'I am here each time. This is shown on the 3rd, 4th, and further requests.'


Lazy dynamic streams
====================

Lazy streaming with callables
-----------------------------

To define which item should be streamed on every request, or to generate that item based on the request, use callables in the stream.

The callables can either have no arguments, or accept one positional argument of type :class:`kmock.Request`. Use this to define some realistic server-side behaviour which depends on the request sent.

The result of the callable is used for the stream as if it was placed in place of the callable itself. In particular, this means that an async function, which returns a corotuine, is awaited and its result is streamed instead.

In particular, lambdas can be used to sleep. In this example, async sleep coroutine is created on every request and is awaited before returning the result. Its own result is ``None`` and is therefore ignored.

.. code-block:: python

    import kmock

    async def test_callables_in_streams(kmock: kmock.RawHandler) -> None:
        kmock['/greetings'] << (
            lambda: asyncio.sleep(1),  # some delay to simulate heavy thinking
            b"Hello, ",
            lambda req: req.params.get('name', 'user'),
            b"!",
        )

        resp = await kmock.get('/greetings?name=John')
        text = await resp.read()
        assert text == b'Hello, John!"

        resp = await kmock.get('/greetings')
        text = await resp.read()
        assert text == b'Hello, user!"


Lazy streaming with awaitables
------------------------------

The most common sync & async synchronisation primitives can be used as streamed items. In that case, the primitive is awaited with the most appropriate method for that primitive, and its result is used. For primitives with no results, such as events, ``None`` is used, so it simply waits until the primitive is set, but continues to the following stream items.

The following awaitable primitives are supported with the respective methods used to get the result:

- Async primitives:
 - :class:`asyncio.Future` (uses :meth:`asyncio.Future.result`).
 - :class:`asyncio.Event` (uses :meth:`asyncio.Event.wait`).
 - :class:`asyncio.Condition` (uses :meth:`asyncio.Condition.wait` while locked).
 - :class:`asyncio.Queue` (uses :meth:`asyncio.Queue.get`).
 - :class:`asyncio.Task` (uses ``await task``).
- Sync primitives:
 - :class:`concurrent.futures.Future` (uses :meth:`concurrent.futures.Future.result`).
 - :class:`threading.Event` (uses :meth:`threading.Event.wait`).
 - :class:`threading.Condition` (uses :meth:`threading.Condition.wait` while locked).
 - :class:`queue.Queue` (uses :meth:`queue.Queue.get`).

.. code-block:: python

    import kmock

    @pytest.mark.looptime
    async def test_awaitable_stream(kmock: kmock.RawHandler) -> None:
        sleeper = asyncio.Event()
        kmock['/'] << (sleeper, b"hello")

        loop = asyncio.get_running_loop()
        loop.call_later(1, sleeper.set)

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'hello'
        assert loop.time() == 1


Depletion of callables/awaitables
---------------------------------

Callables/awaitables can behave both as replayable and as depletable streams depending on whether they return the same or different objects on each call: the same reused tuple object will be depleted, but the newly created tuple will be treated as a replayable stream:

.. code-block:: python

    import kmock

    async def test_callable_depletion(kmock: kmock.RawHandler) -> None:
        depleted_part = iter([b'This line is shown only once, as it is the same generator each time.'])
        kmock['/'] << (
            lambda: iter([b'This line is shown on each request, as it is a new generator each time.']),
            lambda: depleted_part,
        )

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'This line is shown only once, as it is the same generator each time.'

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'This line is shown on each request, as it is a new generator each time.'


.. _live_streams:

Live streams
============

Streams can have "feeding points" marked as ``...`` (literally three dots, also known as ``Ellipsis``). You can read this as "to be continued". In that case, the request blocks at the feeding point and waits for new items to be fed into the stream with the ``<<`` operation on the feeding filter marked with the same ``...`` (``Ellipsis``) as a criterion, e.g. ``kmock[...]`` (or on any applicable request filter).

The stream only streams the items fed strictly after the stream reached the feeding point. Previously fed items are not preserved and are not replayed.

If the newly fed items do not contain the new feeding point, the stream unblocks and continues till the end (or finishes immediately if there are no scheduled items left). To keep the stream infinitely blocking, add a new feeding point ``...`` on every feeding.

.. code-block:: python

    import aiohttp
    import kmock


    # A sample system-under-test that consumes the stream and prints it:
    async def consume_stream(url: str) -> None:
        async with aiohttp.ClientSession() as session:
            resp = session.get(url)
            resp.raise_for_status()
            for chunk in resp.content.iter_chunked():
                print(f"{chunk!r}")


    async def test_stream_feeding(kmock: kmock.RawHandler) -> None:
        # Setup the endpoints and streams:
        stream = kmock['get /'] << ('Hello!', ..., 'Good bye!')

        # Initiate the background reading from the stream:
        asyncio.create_task(consume_stream(str(kmock.url)))

        # Slowly feed some simulated payload into the stream:
        stream << b'Countdown:\n' << ...
        for i in range(3, 0, -1):
            # Feed an additional feeding point on every iteration:
            stream << i << ...

            # Sleep to simulate the slowly going process:
            await asyncio.sleep(1)

        # Finish the stream and close the connection (because no new feeding point).
        stream << b''

The output is:

.. code-block:: console

    Hello!
    Countdown:
    3
    2
    1
    Good bye!

.. note::

    Live streams are internally tail-optimized: if the feeding point is deterministicaly the last item on the stream, there will be no recursion involved to save resources. This covers the cases like ``stream << (1,2,3,...)`` or even with nested tuples ``stream << (1,(2,(3,(...,))))``.

    However, non-deterministic cases are not optimized and use the recursion. E.g., callables/awaitables that return the ``Ellipsis`` in the result: ``stream << (1, 2, 3, lambda: ...)``.

    Similarly, the non-tailing ``Ellipsis`` is not optimized as there is need to persist and stream the stream-closing items: ``stream << (b"hello", ..., b"good-bye"))``.

.. warning::

    The feeding operation is synchronous for the syntactic simplicity, so it can be used even in the sync tests with sync HTTP/API clients. However, it uses some asynchronous machinery behind — a queue and a task to get items from the queue and put them to a bus. As such, there can be a minor delay after the feeding operation ``<<`` has returned and before the item is noticed by the consumers. If you do not do ``await`` inbetween, the queue/bus/stream can be blocked with no actual streaming, so either async tests/routines are recommended anyway, or the feeding must be happening in a parallel thread.

    In async routines and tests, doing ``await asyncio.sleep(0)`` should suffice to give control to the event loop and execute the queue/bus/stream activity.
