===============
Linter warnings
===============

You might want to disable "statement has no effect" warnings in linters & IDEs.

KMock uses the ``<<`` & ``>>`` not as pure operators that shift an integer left/right by a number of bits, but as C++-style streams, i.e. as operations with side effects. Python linters & IDEs are typically unaware that these operators can be overridden to produce side effects, so they complain about a statement with no effect.

KMock does this intentionally for its fancy DSL, assuming that you already have unused statements in your tests anyway, typically under ``with pytest.raises(…):``, where you expect an error and do not expect a result.

For example:

.. code-block:: python

    async def test_me(kmock):
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

    async def test_me(kmock):
        _ = kmock['get /'] << b'hello'
