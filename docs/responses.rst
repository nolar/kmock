==================
Prepared responses
==================

Responses syntax
================

All response payloads go after the ``<<`` operation on a request filter with criteria. This is a C++-like stream of payloads and side effects.

All side effects go after the ``>>`` operation on a request filter with criteria. They send the data from the request into external destinations.

In both cases, the operations return a :class:`kmock.Reaction` instance, which can be used to add more response payloads or side effects, or preserved into a variable for later assertions.

.. note::

    Mind that ``set``, ``frozenset``, and other sets are reserved for future ideas and not served now. They are not ordered so it would be a idea bad for the response content; if random order is intended, shuffle the lists/tuples instead.


Responses meta-data
===================

Responding with status codes
----------------------------

To respond only with the HTTP status code, use the integer values in the range 100-999. Note that the HTTP staus codes 1xx usually mean the continuaton of the request is expected, so the requests might hang from the client side waiting for the continuation.

.. code-block:: python

    import kmock

    async def test_status_codes(kmock: kmock.RawHandler) -> None:
        kmock['/'] << 404 << b'hello'

        resp = await kmock.get('/')
        text = await resp.read()
        assert resp.status == 404
        assert text == b'hello'


Responding with headers
-----------------------

To send the response headers, use one of the following methods.

Either define a payload as a simple dict, assuming that all headers are well-known HTTP headers or their names start with ``X-`` (case-insensitive; the list of well-known headers can be found in ``KNOWN_HEADERS``):

.. code-block:: python

    import kmock

    async def test_inferred_headers_responses(kmock: kmock.RawHandler) -> None:
        kmock['/'] << {'X-My-Header': 'hello'}

        resp = await kmock.get('/')
        assert resp.headers['X-My-Header'] == 'hello'

Or wrap the response headers explicitly with the :class:`kmock.headers` wrapper to be certain that it is sent as headers regardless of the headers names. This wrapper additionally understands several :

.. code-block:: python

    import kmock

    async def test_wrapped_headers_responses(kmock: kmock.RawHandler) -> None:
        kmock['/'] << kmock.headers({'My-Header': 'hello'})

        resp = await kmock.get('/')
        assert resp.headers['My-Header'] == 'hello'


Responding with cookies
-----------------------

To send a simplified cookie from the server to the client, wrap it into the :class:`kmock.cookies` wrapper. There is no short version of that dict that is interpreted as cookies without wrapping.

.. code-block:: python

    import kmock

    async def test_cookies_responses(kmock: kmock.RawHandler) -> None:
        kmock['/'] << kmock.cookies({'SessionId': '123abc'})

        resp = await kmock.get('/')
        assert resp.cookies['Session'].value == '123abc'

For more precisely defined cookies, such as with specific expiration times or scopes, use the raw aiohttp responses as described nearby in :ref:`lowlevel`.


Responses bodies
================

Responding with JSON data
-------------------------

To respond with a JSON payload, use the Python types that look like supported JSON types: ``str``, ``int``, ``float``, ``bool``, ``list``, ``dict``.

.. code-block:: python

    import kmock

    async def test_json_responses(kmock: kmock.RawHandler) -> None:
        kmock['/'] << {
            'int': 123,
            'bool': True,
            'float': 123.456,
            'string': 'hello',
            'list': [123, 456],
        }

        resp = await kmock.get('/')
        text = await resp.read()
        data = await resp.json()
        assert text == b'{"int": 123, "bool": true, "float": 123.456, "string": "hello", "list": [123, 456]}'
        assert data == {"int": 123, "bool": True, "float": 123.456, "string": "hello", "list": [123, 456]}

Mind one critical difference: strings of type ``str`` are sent JSON-encoded, i.e. wrapped with double quoted and escaped inside — even if they are the only response payload. So send raw values as is, use the ``bytes`` payloads.

Mind that integers in the range 100-999 are interpreted as HTTP status codes. To send the integers are JSON values, wrap them into the :func:`kmock.data` wrapper or encode them as ``bytes`` (e.g. ``b"404"`` or ``str(val).encode()``).

To avoid interpreting the arbitrary values as having any special meaning, such as HTTP status codes, wrap that values into the :class:`kmock.data` wrapper. The wrapper accepts any JSON-serializable values and containers:

.. code-block:: python

    import kmock

    async def test_wrapped_int_responses(kmock: kmock.RawHandler) -> None:
        kmock['/'] << kmock.data(404)

        resp = await kmock.get('/')
        text = await resp.read()
        data = await resp.json()
        assert resp.status == 200
        assert text == b'404'
        assert data == 404


Responding with binary blobs
----------------------------

To send a response with a predefined binary blob, use the ``bytes`` values in Python, e.g. ``b"hello"``. The bytes are send on every request as is, without any processing or encoding/decoding.

.. code-block:: python

    import kmock

    async def test_responses_from_open_files(kmock: kmock.RawHandler) -> None:
        kmock['/'] << b'hello'

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'hello'

KMock does not interpret binary ``bytes`` values in any way, so it is safe to use them as is. To be slightly more explicit, the :class:`kmock.body` wrapper can be used to wrap dynamic binary values, so that they always go to the response body.

.. note::

    While ``b"hello"`` will be sent as these 5 symbols, the string ``"hello"`` will be sent as written — i.e. with double quotes, 7 symbols, so that it could be JSON-decoded on the other side. Would you need to send strings as is, encode them to ``bytes`` explicitly: ``"hello".encode()``.

Responding with UTF-8 texts
---------------------------

To use a regular string as a response body, wrap it with the :class:`kmock.text` wrapper. In that case, the string is encoded as UTF-8 before sending in the response, but not as JSON:

.. code-block:: python

    import kmock

    async def test_raw_string_responses(kmock: kmock.RawHandler) -> None:
        kmock['/as-json'] << 'hello'
        kmock['/as-text'] << kmock.text('hello')
        kmock['/as-body'] << kmock.body(b'hello')

        resp = await kmock.get('/as-json')
        text = await resp.read()
        assert text == b'"hello"'  # note the double quotes

        resp = await kmock.get('/as-text')
        text = await resp.read()
        assert text == b'hello'

        resp = await kmock.get('/as-body')
        text = await resp.read()
        assert text == b'hello'


Responding from files
---------------------

To send a response from a local file, which is consumed globally for all incoming requests, use the built-in :func:`open` function. Beware that open files become depleted for subsequent requests as they are consumed (unless something is appended to the file).

.. code-block:: python

    import kmock

    async def test_responses_from_open_files(kmock: kmock.RawHandler, tmp_path) -> None:
        path = tmp_path / "file.txt"
        path.write_bytes(b'hello')
        kmock['/'] << open(str(path))

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'hello'

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b''  # the file has been depleted


Responding from paths
---------------------

To send a response from a local file, which is re-opened on every request, use :class:`pathlib.Path`.

.. code-block:: python

    import kmock

    async def test_responses_from_paths(kmock: kmock.RawHandler, tmp_path) -> None:
        path = tmp_path / "file.txt"
        path.write_bytes(b'hello')
        kmock['/'] << path

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'hello'

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'hello'  # the file is re-opened again


Responding from IO buffers
--------------------------

To send a response from a file-like object, use :class:`io.StringIO` for text/string payloads, or :class:`BytesIO` for binary payloads. Technically, all descendants of the StdLib's :class:`io.RawIOBase`, :class:`io.BufferedIOBase`, :class:`io.TextIOBase` are supported if you have your own i/o classes.

Note that the buffer is consumed and depleted on requests because its current position moves forward to the end of the buffer, so the 2nd and following requests might get nothing if nothing is added to the buffer:

.. code-block:: python

    import io
    import kmock

    async def test_responses_from_io(kmock: kmock.RawHandler) -> None:
        buffer = io.StringIO('prepared buffer')
        kmock['/'] << buffer

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'prepared buffer'

        buffer.write('appended buffer')

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'appended buffer'

.. _lowlevel:

Low-level responses
===================

Responding with structured responses
------------------------------------

If you are unsatisfied with how atomic values are interpreted into metadata or response data, use the :class:`kmock.Response` instance with all fields filled explicitly:

.. code-block:: python

    import kmock

    async def test_explicit_responses(kmock: kmock.RawHandler) -> None:
        kmock['/'] << kmock.Response(
            status=404, reason='Not Found',
            headers={'My-Header': 'hello'},
            cookies={'SessionId': '123abc'},
            data={'items': []})

        resp = await kmock.get('/')
        data = await resp.json()
        assert resp.status == 404
        assert resp.reason == 'Not Found'
        assert resp.headers['My-Header'] == 'hello'
        assert resp.cookies['SessionId'].value == '123abc'
        assert data == {'items': []}


Responding with raw aiohttp responses
-------------------------------------

If you need to customize the response behavior on the low-level, you can respond with the low-level :class:`aiohttp.web.StreamResponse` or its descendant's :class:`aiohttp.web.Response` instances. Generally, this is not recommended — use the provided features of KMock where possible, including the :doc:`/streams`. However, this functionality is provided to ensure the existence of fallback scenarios in case of difficulties.

.. code-block:: python

    import aiohttp.web
    import kmock

    async def test_explicit_responses(kmock: kmock.RawHandler) -> None:
        kmock['/'] << aiohttp.web.Response(
            status=404, reason='Not Found',
            headers={'My-Header': 'hello'},
            text='hello')

        resp = await kmock.get('/')
        text = await resp.read()
        assert resp.status == 404
        assert resp.reason == 'Not Found'
        assert resp.headers['My-Header'] == 'hello'
        assert text == b'hello'


Errors in responses
===================

Raising exceptions server-side
------------------------------

In order to simulate a server-side error, define a payload which is either an exception type of a pre-created exception instance. In that case, it will be raised in place where the response is rendered.

In raw handlers, filters and responses, this has little practical benefits except as for testing KMock itself on how it behaves on internal errors.

In Kubernetes-specific handlers, however, it is actively used to inject the Kubernetes-specific errors that render into HTTP responses such as 404 Resource Not Found, 404 Object Not Found, all 500 "ambiguous behaviour" situations, so on.

To simulate your application-specific server-side errors, it is better to explicitly provide the specific status codes and response payloads than to rely on a predefined rendering done by KMock.

.. code-block:: python

    import kmock

    async def test_responses_with_errors(kmock: kmock.RawHandler) -> None:
        kmock['/'] << ZeroDivisionError("boo!")

        resp = await kmock.get('/')
        text = await resp.read()
        assert resp.status == 500
        assert b'ZeroDivisionError' in text


StopIteration exceptions
------------------------

Some exceptions are handled specially: :class:`StopIteration` & :class:`StopAsyncIteration` mark the reaction as depleted and cease serving it in the future requests unless explicitly reactivated.

With this, users can use ``next()`` or ``anext()`` calls from an external source to simulate varying content on each request, which can raise one of these exceptions and thus look like the source was depleted normally.

In this example, ``next(source)`` yields a viable value 5 times, after which it yields a :class:`StopIteration` exception. Once this happens the whole reaction deactivates self, and the next defined reaction comes into play and returns the HTTP status 404, which in turn stops the ``while True`` cycle:

.. code-block:: python

    import kmock

    async def test_stopiteration_exception_in_response(kmock: kmock.RawHandler) -> None:
        source = (i for i in range(5))
        kmock['/'] << (lambda: {'counter': next(source)})
        kmock['/'] << 404

        while True:
            resp = await kmock.get('/')
            text = await resp.read()
            print(f"{resp.status}, {text!r}")
            if rsp.status != 200:
                break
    # Output:
    # 200 b'{"counter": 0}'
    # 200 b'{"counter": 1}'
    # 200 b'{"counter": 2}'
    # 200 b'{"counter": 3}'
    # 200 b'{"counter": 4}'
    # 404 b''


Lazy dynamic responses
======================

Lazy responses with callables
-----------------------------

To define which response should be returned on a specific request, or to generate that response on every request (even if the same), use callables: sync & async functions, lambdas, partials.

The callables can either have no arguments, or accept one positional argument of type :class:`kmock.Request`. Use this to define some realistic server-side behaviour which depends on the request sent.

The result of the callable is used for the response as if it was placed in place of the callable itself. In particular, this means that an async function, which returns a corotuine, is awaited and its result is served instead.

.. code-block:: python

    import kmock

    async def test_callable_responses(kmock: kmock.RawHandler) -> None:
        kmock['/greetings'] << (lambda req: f"Hello, {req.params.get('name', 'user')}!".encode())

        resp = await kmock.get('/greetings?name=John')
        text = await resp.read()
        assert text == b'Hello, John!"

        resp = await kmock.get('/greetings')
        text = await resp.read()
        assert text == b'Hello, user!"


Lazy responses with awaitables
------------------------------

The most common sync & async synchronisation primitives can be used as responses. In that case, the primitive is awaited with the most appropriate method for that primitive, and its result is used. For primitives with no results, such as events, ``None`` is used, so it simply waits until the primitive is set, but continues to the following filters & responses.

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
    async def test_awaitable_response(kmock: kmock.RawHandler) -> None:
        queue: asyncio.Queue[Any] = asyncio.Queue()
        kmock['/'] << queue

        loop = asyncio.get_running_loop()
        loop.call_later(1, queue.put_nowait, b'hello')
        loop.call_later(3, queue.put_nowait, b'world')

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'hello'
        assert loop.time() == 1

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'world'
        assert loop.time() == 3
