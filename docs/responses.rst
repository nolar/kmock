=======================
Responding to a request
=======================

.. highlight:: python

All response payloads go after the ``<<`` operation on a filter. This is a C++-like stream of payloads and side effects.

All side effects go after the ``>>`` operation on a filter. They send the data from the request into external destinations.

In both cases, the operations return a :class:`Reaction` object, which can be used to add more response payloads or side effects, or preserved into a variable for later assertions.


Payload content
===============

The response can be of any of the following types, and is handled accordingly:

``None`` is ignored. It can be used to define a resource in a Kubernetes mock server without actually adding any payload, so that the resources become visible in the cluster discovery in :class:`KubernetesScaffold` and :class:`KubernetesEmulator`::

    kmock['kopfexamples.v1.kopf.dev'] << None

``...`` (aka ``Ellipsis``), ``tuple``, ``iter()``, sync/async generators, and other iterables (except for lists & sets) define a live stream, which is described in details in :doc:`/streams`.

``int`` in the range 100-999 are sent as an HTTP status.

``dict`` with only well-known HTTP headers or those starting with ``X-`` (case-insensitive) are used as HTTP headers. The list of well-known headers can be found in ``KNOWN_HEADERS``.

``str``, ``int``, ``float``, ``bool``, ``list``, ``dict`` —i.e. all syntactically JSON-like objects— are encoded as JSON and sent as a JSON response.

``bytes`` are sent as is.

``open()``, ``pathlib.Path``, ``io.StringIO``, ``io.BytesIO`` are sent from the corresponding files in binary mode, with strings from text-mode files encoded as UTF-8.

``pathlib.Path`` is opened and consumed anew every time, so it is never depleted.

:class:`kmock.Response` and :class:`aiohttp.web.StreamResponse` instances are used for responses directly.

Exceptions (classes and instances) are raised in place on the server side.

Awaitables (coroutines, futures, tasks) & callables (functions, lambdas, partials) are unfolded in place and their result is returned as if was placed instead of the function/awaitable.

.. note::

    Mind that ``set``, ``frozenset``, and other sets are reserved for future ideas and not served now. They are not ordered so they would be a idea bad for response content; if random order is intended, shuffle the lists/tuples instead.

.. note::

    While ``b"hello"`` will be sent as these 5 symbols, ``"hello"`` will be sent as written — i.e. with double quotes, 7 symbols, so that it could be JSON-decoded on the other side. Would you need to send strings as is, encode them to bytes explicitly: ``"hello".encode()``.


Binary responses
----------------

``bytes`` are sent as is.

``open()``, ``io.RawIOBase``, ``io.BufferedIOBase``, ``io.TextIOBase`` are consumed and their content is sent t the response. Note that some of them may become depleted for subsequent requests.

``pathlib.Path`` is opened and consumed anew every time, so it is never depleted.


Callables/awaitables in content
-------------------------------

Awaitables (futures, coroutines, tasks) are awaited, and their result is served according to its type as if it was directly mentioned.

Callables (sync & async functions, lambdas, partials) are called, and their result is served according to its type as if it was directly mentioned; in particular, this means that an async function, which returns a corotuine, is awaited and its result is served instead. Callables CAN (not MUST) accept a single positional argument of type :class:`Request` and return one of the supported content types — including, if needed, other callables, awaitables, and exceptions.


Payload wrappers
----------------

To ensure that arbitrary dicts are used as cookies or headers, not as JSON payloads, wrap them with the specialized wrapper:

``kmock.headers()`` for HTTP headers regardless whether they are known or not.

``kmock.cookies()`` for HTTP cookies.

Similarly, to prevent guessing the purpose of an arbitrary value and use it in the desired role:

``kmock.data()`` for JSON payloads.

``kmock.text()`` for text responses encoded as UTF-8.

``kmock.body()`` for binary responses with ``bytes``.


Exceptions in content
---------------------

Exceptions in the response content —both classes and instances— are raised on the server side as if they have really happened. This is a shorter form of doing ``raise …``.

Raising exceptions is generally not advised as it will only break the server and disconnect the client. However, some exceptions can have beneficial effects.

``StopIteration`` & ``StopAsyncIteration`` mark the reaction as depleted and cease serving it in the future requests unless explicitly reactivated. With this, users can use ``next()`` or ``anext()`` calls from an external source to simulate varying content on each request, which can raise one of these exceptions and thus look like the source was depleted normally:

.. code-block:: python

    source = (i for i in range(5))
    kmock.add('get', '/', lambda: {'counter': next(source)}
    kmock.add('get', '/', 404}

    while True:
        rsp = requests.get(kmock.url + '/')
        print(f"{rsp.status}, {rsp.text()!r}")
        if rsp.status != 200:
            break
    # 200 '{"counter": 0}'
    # 200 '{"counter": 1}'
    # 200 '{"counter": 2}'
    # 200 '{"counter": 3}'
    # 200 '{"counter": 4}'
    # 404 ''




Side effects
============

``open()``, ``pathlib.Path``, ``io.StringIO``, ``io.BytesIO`` are written with the data of the request's body (and only body; no headers, verbs, paths).

Several container types are supported:

``set``, ``list``, and other mutable sequences get an instance of :class:`Request` added/appended.

``dict`` and other mutable mappings get the new key of type :class:`Request`, with the value being the request's data (if parsed from JSON) or binary body (if not) or ``None`` (if no body at all).

Several synchronization primitives —sync and async— are supported out of the box:

``asyncio.Queue``, ``queue.Queue`` receive an instance of :class:`Request`.

``asyncio.Future``, ``concurrent.futures.Future`` are set with an instance of :class:`Request`.

``asyncio.Event``, ``asyncio.Queue`` are set, but not data is passed.

``asyncio.Condition``, ``threading.Condition`` are notified, but no data is passed.

Generators (sync & async) get the instance of :class:`Request` as the result of their ``yield`` operation and can execute until the next ``yield``.

Other awaitables (coroutines) & callables (functions, lambdas, partials) are unfolded in place and their result is used to receive the request instance as described above.


Spies
=====

The results of ``<<`` or ``>>`` operations of type :class:`Reaction` can be preserved into variables and later used in assertions — a typical "spy" or a "checkpoint" pattern.

Note that every such filter instance keeps its own list of requests served, so a repeated filtering on the same criteria will return a new instance with no requests in its log. You should preserve the original filter or reaction to see the requests.

.. code-block:: python

    async def test_gets():
        getter = kmock['get']
        kmock['get /'] << b'root'
        kmock['/path'] << b'path'

        await kmock.get('/')
        await kmock.get('/path')
        await kmock.post('/path')

        assert len(list(kmock)) == 3
        assert len(list(getter)) == 2

To make a reaction which responds with an empty body and stops matching the following filters, explicitly mention ``b""`` as the content.

.. code-block:: python

    async def test_gets():
        get1 = kmock['get'] << b''
        get2 = kmock['get /'] << b''  # this will never be matched

        await kmock.get('/')

        assert len(list(get1)) == 1
        assert len(list(get2)) == 0
