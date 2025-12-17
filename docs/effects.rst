============
Side effects
============

Side effects syntax
===================

All response payloads go after the ``<<`` operation on a request filter with criteria. This is a C++-like stream of payloads and side effects.

All side effects go after the ``>>`` operation on a request filter with criteria. They send the data from the request into external destinations.

In both cases, the operations return a :class:`kmock.Reaction` instance, which can be used to add more response payloads or side effects, or preserved into a variable for later assertions.


Storing request objects
=======================

Storing requests to containers
------------------------------

To store all incoming requests into a mutable container of type ``list``, ``set``, or alike, direct the side effect into this list. Do not forget to store it into a variable for futher processing. The objects stored are all of type :class:`kmock.Request`.

Mind that lists are sorted in the order the requests were made chronologically, while sets are unordered.

.. code-block:: python

    import kmock

    async def test_side_effects_into_containers(kmock: kmock.RawHandler) -> None:
        reqs: list[kmock.Request] = []
        kmock['/'] >> reqs

        await kmock.get('/?q=hello')
        await kmock.get('/?q=world')

        assert len(reqs) == 2
        assert reqs[0].params == {'q': 'hello'}
        assert reqs[1].params == {'q': 'world'}

In particular, if the container is of type ``dict``, the keys become the requests of type :class:`kmock.Request`, while the values come from the requests' bodies — either JSON-parsed, or raw binary, or ``None`` if there was no request body. This is done only for convenience, while the requests' bodies are anyway available as :attr:`kmock.Request.data` and :attr:`kmock.Request.body`.

.. code-block:: python

    import kmock

    async def test_side_effects_into_containers(kmock: kmock.RawHandler) -> None:
        reqs: dict[kmock.Request, Any] = {}
        kmock['/'] >> reqs

        await kmock.get('/?q=hello')
        await kmock.get('/?q=world')

        assert len(reqs) == 2
        req1, req2 = reqs
        assert req1.params == {'q': 'hello'}
        assert req2.params == {'q': 'world'}
        assert reqs[req1] is None
        assert reqs[req2] is None


Storing requests to primitives
------------------------------

Several synchronization primitives —both sync and async— can received the instances of the :class:`kmock.Request` objects as the requests are made.

.. code-block:: python

    import kmock
    import queue

    async def test_side_effects_into_primitives(kmock: kmock.RawHandler) -> None:
        queue: queue.Queue[kmock.Request] = queue.Queue()
        kmock['/'] >> reqs

        await kmock.get('/?q=hello')
        await kmock.get('/?q=world')

        assert queue.qsize() == 2
        req1 = queue.get()
        req2 = queue.get()
        assert req1.params == {'q': 'hello'}
        assert req2.params == {'q': 'world'}


Storing request bodies
======================

Storing requests to files
-------------------------

To log all incoming requests into open files, use :func:`open` to open the file and use it for the side effect. Note that only the request's body is stored to the file, not the whole request — i.e. the HTTP handshake and headers are skipped. No separators are added either, so the request bodies go concatenated. This can be helpful for simple debugging of a flow of requests.

.. code-block:: python

    import kmock

    async def test_side_effects_into_files(kmock: kmock.RawHandler, tmp_path) -> None:
        with open(str(tmp_path / "log.txt"), 'wt') as log:
            kmock['/'] >> log << b''

            await kmock.post('/', body=b'hello')
            await kmock.post('/', body=b'world')

        text = (tmp_path / "log.txt").read_text()
        assert text == 'helloworld'


Storing requests to paths
-------------------------

Similar to open files, paths of type :class:`pathlib.Path` are written on every request with the request body. Different from open files, every new request reopens the file and overwrites it.

.. code-block:: python

    import kmock

    async def test_side_effects_into_paths(kmock: kmock.RawHandler, tmp_path) -> None:
        kmock['/'] >> (tmp_path / "log.txt") << b''
        await kmock.post('/', body=b'hello')
        await kmock.post('/', body=b'world')
        text = (tmp_path / "log.txt").read_text()
        assert text == 'world'


Storing requests to IO buffers
------------------------------

Similar to files, textual and binary buffers of types :class:`io.BytesIO` and :class:`io.StringIO` accumulate the requests' bodies as they arrive.

.. code-block:: python

    import io
    import kmock

    async def test_side_effects_into_buffers(kmock: kmock.RawHandler, tmp_path) -> None:
        buffer = io.StringIO()
        kmock['/'] >> buffer << b''

        await kmock.post('/', body=b'hello')
        await kmock.post('/', body=b'world')

        text = buffer.getvalue()
        assert text == 'helloworld'



Lazy dynamic side effects
=========================

Lazy side effects with callables
--------------------------------

To call a function lazily and ignore its result, use callables as side effects: sync & async functions, lambdas, partials.

The callables can either have no arguments, or accept one positional argument of type :class:`kmock.Request`. Use this to define some realistic server-side behaviour which depends on the request sent.

This can be helpful to call some function that do not return ``None`` but some other value that can be otherwise interpreted as a payload if the ``<<`` operation is used. With the side-effect ``>>`` operation, its result will be ignored.

.. code-block:: python

    import kmock

    async def test_callable_side_effect(kmock: kmock.RawHandler, chronometer) -> None:
        # Simulate the slow behavior of the server side.
        kmock['/'] >> (lambda: time.sleep(1)) << b'hello'

        with chronometer:
            resp = await kmock.get('/')
            text = await resp.read()

        assert 0.8 <= chronometer.seconds <= 1.2  # 1s ± 0.2s uncertainty
        assert text == b'hello"

In this example, the ``chronometer`` fixtures comes from the looptime_. It simply measures the runtime of the code blocks in the wall-clock terms using :func:`time.perf_counter`.

.. _looptime: https://github.com/nolar/looptime


Lazy side effects with awaitables
---------------------------------

The most common sync & async synchronisation primitives can be used as side effects. In that case, the primitive is awaited with the most appropriate method for that primitive, the instance of :class:`kmock.Request` is set/fed into the primitive if applicable, and the result is ignored.

The following awaitable primitives are supported with the respective methods used to get the result:

- Async primitives:
 - :class:`asyncio.Future` (uses :meth:`asyncio.Future.set_result`).
 - :class:`asyncio.Event` (uses :meth:`asyncio.Event.set`).
 - :class:`asyncio.Condition` (uses :meth:`asyncio.Condition.notify_all` while locked).
 - :class:`asyncio.Queue` (uses :meth:`asyncio.Queue.put`).
 - :class:`asyncio.Task` (uses ``await task``).
- Sync primitives:
 - :class:`concurrent.futures.Future` (uses :meth:`concurrent.futures.Future.set_result`).
 - :class:`threading.Event` (uses :meth:`threading.Event.set`).
 - :class:`threading.Condition` (uses :meth:`threading.Condition.notify_all` while locked).
 - :class:`queue.Queue` (uses :meth:`queue.Queue.put`).


.. code-block:: python

    import kmock

    @pytest.mark.looptime
    async def test_awaitable_side_effect(kmock: kmock.RawHandler) -> None:
        queue: asyncio.Queue[Any] = asyncio.Queue()
        kmock['/'] >> queue

        await kmock.post('/', data=b'hello')
        await kmock.post('/', data=b'world')

        assert queue.qsize() == 2
        body1 = queue.get_nowait()
        body2 = queue.get_nowait()
        assert body1 == b'hello'
        assert body2 == b'world'


Lazy side effects with generators
---------------------------------

As a particular case of callable side effects, sync & async generators accept the instance of :class:`kmock.Request` as the result of the ``yield`` operation and continue to the next ``yield``.

.. code-block:: python

    import kmock
    from typing import Iterator

    def generator() -> Iterator[None]:
        while True:
            req: kmock.Request = yield
            print(f"-> {req.params}")

    async def test_generator_side_effects(kmock: kmock.RawHandler) -> None:
        kmock['/'] >> generator()

        await kmock.get('/?q=hello')
        await kmock.get('/?q=world')

    # Output:
    # -> {'q': 'hello'}
    # -> {'q': 'world'}
