============
Side effects
============

TODO: make it more detailed.

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
