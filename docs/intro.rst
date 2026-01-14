============
Introduction
============

.. When changing this, ensure the tests are synced with test_doc_examples.py & the tests do pass.

Here is how tests can look like with KMock — from the simplest HTTP to the advanced Kubernetes tests:

A typical structure of the test:

* The entry point in pytest is the ``kmock`` fixture, which works out of the box. You can construct your own handler and/or server if needed (see :doc:`/usage`).
* The server pre-population starts with ``kmock[criteria] << payload``. Kubernetes emulator's data fixtures go into ``kmock.objects[resource, namespace, name]`` and ``kmock.resources[resource]``.
* Then the system-under-test runs and makes arbitrary HTTP/API requests to ``kmock.url`` or using the embedded client.
* In the end, the test asserts on the received (or missed) requests via the ``kmock`` fixture or spies, so as on the client-side responses just in case, and on the modified ``kmock.objects`` for the Kubernetes emulator.


HTTP mock server
================

The simplest HTTP example: respond with the status code 418 and return a JSON-encoded dictionary (or any other JSON-compatible value) at the root endpoint.

Then we use the embedded client to retrieve the response of that root URL.

.. code-block:: python

    import kmock


    async def test_http_access(kmock: kmock.RawHandler) -> None:

        # Pre-populate the HTTP server with request criteria and associated responses.
        kmock['get /'] << 418 << {'hello': 'world'}

        # Perform a sample request using the embedded client and assert the response.
        resp = await kmock.get('/')
        data = await resp.json()
        assert resp.status == 418
        assert data == {'hello': 'world'}


Kubernetes mock server
======================

In this example, we use the default most advanced handler :class:`kmock.KubernetesEmulator`, which is capable of keeping in-memory state of objects, which in turn can be manipulated either via the API, or via the ``kmock.objects`` associative array. See more in :doc:`/kubernetes/discovery` and :doc:`/kubernetes/persistence`.

Specifically, we populate the server's state with two objects named ``name1`` and ``name2`` in different namespaces ``ns1`` and ``ns2``. Then we list the objects of the namespaces ``ns1`` only. As a result, the object named ``name1`` is returned, while object ``name2`` is omitted.

The final :class:`kmock.Object` wrapper enables the partial dict comparison with subset-like inclusion of keys, thus checking only for the presence and value if the ``items`` key, and ignoring all other extra keys that might be present in the response.

.. code-block:: python

    import kmock


    async def test_k8s_list(kmock: kmock.KubernetesEmulator) -> None:

        # Pre-populate the Kubernetes emulator with objects.
        kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'name1'] = {'spec': 123}
        kmock.objects['kopf.dev/v1/kopfexamples', 'ns2', 'name2'] = {'spec': 456}

        # Perform a sample request using the embedded client and assert the response.
        resp = await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples')
        data = await resp.json()
        assert kmock.Object(data) >= {'items': [{'spec': 123}]}


Kubernetes watch-streams
========================

Kubernetes allows watching over resources as they change — returning the events as soon as the object is modified. The provided :class:`kmock.KubernetesEmulator` produced such events when the objects are manipulated via the API.

An important nuance: the watch-stream (the GET …?watch=true request) must be opened strictly before any activity happens on the objects. We use aiohttp's approach to opening such streaming requests as context managers.

We then simulate two operations: a creation of a resource and a deletion of the newly created resource. In the resulting events we see the expected ADDED & DELETED events.

.. code-block:: python

    import json
    import kmock


    async def test_k8s_watch(kmock: kmock.KubernetesEmulator) -> None:
        # Announce the existence of the resource to the server.
        kmock.resources['kopf.dev/v1/kopfexamples'] = {}

        # The stream must start BEFORE the activity happens.
        async with kmock.get('/apis/kopf.dev/v1/kopfexamples?watch=true') as resp:

            # Simulate the activity (ignore the responses).
            body = {'metadata': {'namespace': 'ns1', 'name': 'name3'}, 'spec': 789}
            await kmock.post('/apis/kopf.dev/v1/kopfexamples', json=body)
            await kmock.delete('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/name3')
            await asyncio.sleep(0.1)  # the loopback network stack takes some time

            # Read the accumulated stream and parse into individual events on each line.
            lines: list[bytes] = resp.content.read_nowait().splitlines()
            events = [json.loads(line.decode()) for line in lines]

        # Close the connection, and assert the results.
        assert len(events) == 2
        assert kmock.Object(events[0]) >= {'type': 'ADDED', 'object': {'spec': 789}}
        assert kmock.Object(events[1]) >= {'type': 'DELETED', 'object': {'spec': 789}}


Bizzarily sophisticated stream
==============================

In this example, we generate the streaming response, which returns content over time (not instantly). For the sake of the example, it simulates the Kubernetes resource watching with the ADDED/MODIFIED/DELETED events.

The handler is pinned to the basic :class:`kmock.RawHandler` to avoid overlapping with the out-of-the-box functionality of :class:`kmock.KubernetesEmulator`.

This server always listens on port 12345 so that we could use ``curl`` to access the server from the command line.

.. code-block:: python

    import asyncio
    import datetime
    import json
    import pytest
    import kmock


    @pytest.mark.kmock(port=12345, cls=kmock.RawHandler)
    async def test_bizzarily_complex_k8s_simulation(kmock):
        deletion_event = asyncio.Event()
        asyncio.get_running_loop().call_later(6, deletion_event.set)

        gets = kmock['get']
        lists = kmock['list']
        watches = kmock['watch']

        kmock['list kopf.dev/v1/kopfexamples', kmock.namespace('ns1')] << {'items': [], 'metadata': {'resourceVersion': 'v1'}}
        kmock['watch kopf.dev/v1/kopfexamples', kmock.namespace('ns1')] << [
            {'type': 'ADDED', 'object': {'spec': {}}},
            lambda: asyncio.sleep(3),
            lambda: {'type': 'MODIFIED', 'object': {'spec': {'time': datetime.datetime.now(tz=datetime.UTC).isoformat()}}},
            deletion_event.wait(),
            [
                {'type': 'DELETED', 'object': {'metadata': {'name': f'demo{i}'}}}
                for i in range(3)
            ],
            410,
        ]

        kmock << 404 << b'{"error": "not served"}' << {'X-MyServer-Info': 'error'}

        await function_under_test()

        assert len(kmock) == 3
        assert len(gets) == 2
        assert len(lists) == 1
        assert len(watches) == 1
        assert watches[0].params == {'watch': 'true'}  # other params are tolerated
        assert watches[0].headers['X-MyLib-Version'] == '1.2.3'


    async def function_under_test(kmock: kmock.RawHandler) -> None:
        resp = await kmock.post('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples')
        assert resp.status == 404
        assert resp.headers['X-MyServer-Info'] == 'error'

        await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples')

        headers = {'X-MyLib-Version': '1.2.3'}
        timeout = aiohttp.ClientTimeout(total=1)
        await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples?watch=true',
                        timeout=timeout, headers=headers)

Such a server, when started, will behave as follows (if used from the shell; note the timing in the stream):

.. code-block:: shell

    $ curl -i -X POST http://localhost:12345/apis/kopf.dev/v1/namespaces/ns1/kopfexamples
    HTTP 404 Not Found

    {"error": "not served"}

    $ curl -i http://localhost:12345/apis/kopf.dev/v1/namespaces/ns1/kopfexamples
    HTTP 200 OK

    {'items': [], 'metadata': {'resourceVersion': 'v1'}}

    $ curl -i http://localhost:12345/apis/kopf.dev/v1/namespaces/ns1/kopfexamples?watch=true | xargs -L 1 echo $(date +'[%Y-%m-%d %H:%M:%S]')
    [2020-12-31 23:59:56] HTTP 200 OK
    [2020-12-31 23:59:56]
    [2020-12-31 23:59:56] {'type': 'ADDED', 'object': {'spec': {}}}
    [2020-12-31 23:59:59] {'type': 'MODIFIED', 'object': {'spec': {'time': '2020-12-31T23:59:59.000Z'}}},
    [2020-12-31 23:59:59] {'type': 'DELETED', 'object': {'metadata': {'name': f'demo0'}}}
    [2020-12-31 23:59:59] {'type': 'DELETED', 'object': {'metadata': {'name': f'demo1'}}}
    [2020-12-31 23:59:59] {'type': 'DELETED', 'object': {'metadata': {'name': f'demo2'}}}
    [2020-12-31 23:59:59] {'type': 'ERROR', 'object': {'code': 410}}

Note that there is no pause between MODIFIED & DELETED. While you copy-paste the curl commands, those 6 seconds will most likely elapse, so the event will be already set by the server. As such, the wait-step will be passed instantly (not so in the automated test which runs fast). The sleeping step, however, will be new every time.

In general, KMock's API is designed in such a way that you can express your most sophisticated ideas and desires easily and briefly. Read the full documentation on the detailed DSL for both request criteria & response payloads.
