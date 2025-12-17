==========
Assertions
==========

Requests spies
==============

The results of the ``<<`` or ``>>`` operations of type :class:`kmock.Reaction` can be preserved into variables and later used in assertions — a typical "spy" or a "checkpoint" pattern.

Note that every such filter instance keeps its own list of requests served, so a repeated filtering on the same criteria will return a new instance with no requests in its log. You should preserve the original filter or reaction to collect & see the requests.

Spies can be preserved either as simple filters, or as responses with ``None`` as the payload (read as "no payload").

The root handler and the inidividual filters/reactions, among other things, are sequences of requests of type :class:`kmock.Request` that have been served by these rules; for the root handler, those that ever arrived — even if responded with HTTP 404 Not Found. This can be used in assertions:

.. code-block:: python

    import kmock

    async def test_requests_assertions(kmock: kmock.RawHandler) -> None:
        # Setup the responses and preserve the spies for later assertions.
        gets = kmock['get']  # just a filter, no response/reaction
        posts = kmock['post'] << b'hello'  # a filter with response/reaction

        # Simulate the activity of the system-under-test.
        await kmock.get('/info')
        await kmock.post('/data', data={'key': 'val'})
        await kmock.delete('/info')

        # Check the overall number of requests globally & filtered.
        assert len(kmock) == 3
        assert len(gets) == 1
        assert len(posts) == 1

        # Check the 1st request globall and the 1st to the get-filter.
        assert gets[0].path == '/info'

        # Check the 2nd request globally or the 1st one to the post-filter.
        assert posts[0].path == '/data'
        assert posts[0].data == {'key': 'val'}

        # Check the 3rd request globally (zero-based index 2).
        assert kmock[2].method == kmock.method.DELETE
        assert kmock[2].path == '/info'

To make a spy which responds with an empty body and stops matching the following filters, explicitly mention ``b""`` as the content, so that it does not go to the following filters at all.

.. code-block:: python

    import kmock

    async def test_spies_with_payloads(kmock: kmock.RawHandler) -> None:
        get1 = kmock['get'] << b''    # this one will intercept all requests
        get2 = kmock['get /'] << b''  # this will never be matched

        await kmock.get('/')

        assert len(get1) == 1
        assert len(get2) == 0


Unexpected errors
=================

Errors list
-----------

To catch server-side errors usually coming from the callbacks of the mock server itself, :attr:`kmock.RawHandler.errors` (a list of exceptions) can be asserted to be empty.

.. code-block:: python

    import kmock

    async def test_errors_assertions(kmock: kmock.RawHandler) -> None:
        kmock['/'] << ZeroDivisionError('boo!')

        resp = await kmock.get('/')
        assert resp.status == 500

        assert len(kmock.errors) == 1
        assert str(kmock.errors[0]) == 'boo!'
        assert isinstance(kmock.errors[0], ZeroDivisionError)


Strict mode
-----------

Alternatively, the mock server can be created with the :attr:`kmock.RawHandler.strict` set t ``True`` option. In this case, the assertion will be performed on the client (test) side when closing the fixture. However, the server shutdown usually happens outside of the test, so explicit checking might be more preferable in some cases.

in this example, the test will fail: while the main test body will succeed as all expectations are met, the test's teardown will raise an exception ``ZeroDivisionError`` because it has happened in the request and was remembered (assume it is some unexpected error, despite simulated intentionally for the sake of the example):

.. code-block:: python

    import kmock

    @pytest.mark.kmock(strict=True)
    async def test_errors_assertions(kmock: kmock.RawHandler) -> None:
        kmock['/'] << ZeroDivisionError('boo!')

        resp = await kmock.get('/')
        assert resp.status == 500

.. note::

    The :class:`StopIteration` exception is not escalated, it is processed internally to deactivate the response handler as "depleted".


Kubernetes objects
==================

:class:`KubernetesEmulator` —the in-memory stateful database of objects— exposes the property :attr:`kmock.KubernetesEmulator.objects` to either pre-populate the server's database or to assert it after the test which uses the API.

It is explained in detail in :doc:`/kubernetes/assertions` (and, to the extent needed, in :doc:`/kubernetes/persistence`).
