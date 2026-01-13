=======
Caveats
=======

Linter warnings in IDEs
=======================

You might want to disable "statement has no effect" warnings in linters & IDEs.

KMock uses the ``<<`` & ``>>`` not as pure operators that shift an integer left/right by a number of bits, but as C++-style streams, i.e. as operations with side effects. Python linters & IDEs are typically unaware that these operators can be overridden to produce side effects, so they complain about a statement with no effect.

KMock does this intentionally for its fancy DSL, assuming that you already have unused statements in your tests anyway, typically under ``with pytest.raises(…):``, where you expect an error and do not expect a result.

For example:

.. code-block:: python

    import kmock

    async def test_me(kmock: kmock.RawHandler) -> None:
        kmock['get /'] << b'hello'  # false-positive "statement has no effect"
        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'hello'

In PyCharm, disable the ``Settings`` / ``Editor`` / ``Inspections`` / ``Statement has no effect``.

.. figure:: linters-pycharm.png
   :align: center
   :width: 100%
   :alt: PyCharm settings to disable the "statement has no effect" inspection.

Alternatively, put the results into a underscore-named variables — but in that case, you will likely hit the "unused variable" warning.

.. code-block:: python

    import kmock

    async def test_me(kmock: kmock.RawHandler) -> None:
        _ = kmock['get /'] << b'hello'


Instant & delayed headers
=========================

For streaming responses, there is a subtle difference in these two cases:
the response headers are not sent until a very first binary payload appears,
i.e. a payload which is not ``None``. Until then, the server seems working
without actual stream starting. Some clients may interpret this differently
than the immediate receival of headers and then thinking on the stream payload.

In the delayed-headers test, the sleep goes first. It returns ``None``
but takes time. All this time (5 seconds), the headers are not sent
to the requestor. Only when it comes to the actual binary payload,
it prepares and send the headers and the response body at the same instant:

.. code-block:: python

    import kmock

    async def test_delayed_headers_in_stream(kmock: kmock.RawHandler) -> None:
        kmock['get /'] << (
            lambda: asyncio.sleep(5),
            b'hello'
        )
        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'hello'


In the instant-headers test, the very first item is a real binary payload:
despite it is empty and sends nothing useful, it nevertheless prepares
and sends the response headers, and sleeps for 5 seconds after that.
Only after 5 seconds, it sends the non-empty streaming content.

.. code-block:: python

    import kmock

    async def test_instant_headers_in_stream(kmock: kmock.RawHandler) -> None:
        kmock['get /'] << (
            b'',  # <-- this is the only difference
            lambda: asyncio.sleep(5),
            b'hello'
        )
        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'hello'

Usually, from an external observer's point of view, this is irrelevant --
the server just "thinks" on how to respond. But this subtle difference
should be kept in mind when debugging the behaviour.
