=====
Usage
=====

Handlers & servers
==================

A typical KMock setup consists of two cross-dependent components: a handler and a server.

The handler is a usual WSGI-like callable that accepts an instance of :class:`aiohttp.web.BaseRequest` and returns an instance of :class:`aiohttp.web.StreamResponse`. KMock-specific handlers should be the instances of :class:`kmock.RawHandler` or any of its descendants.

There are several classes of handlers with pre-implemented logic:

* :class:`kmock.RawHandler` allows defining the plain & simple HTTP responses for patterns of requests. This server is sufficient for arbitrary (non-Kubernetes) APIs with any structure.
* :class:`kmock.KubernetesScaffold` is a prepopulated API structure which serves the meta-information about known resources, resource groups, etc — but no objects persistence.
* :class:`kmock.KubernetesEmulator` is a stateful database of objects added/modified/deleted via the API as if it was a real Kubernetes server. However, it does not implement any resource-specific merging logic or behaviour.

The handler also has the embedded client in it, so the methods like ``kmock.get('/')``, ``kmock.post('/')``, and others are available out of the box — using the ``aiohttp`` notation and protocols of :class:`aiohttp.ClientSession`. The base URL is automatically injected, so the URLs can be relative.

The server is a network-related component that listens on a local port and directs all the requests into the handler that was provided at the server creation. There is only one class ready out of the box: :class:`kmock.Server` — and you usually do not need more (but you can make you server classes if needed). The server accepts a compatible handler and TCP-related parameters, such as the listening host & port, intercepted hostnames, a pre-constructed ``aiohttp`` server, and an ``aiohttp`` client factory — all of these parameters are optional and have reasonable defaults.

Optionally, the KMock server installs the DNS interceptor into ``aiohttp`` to redirect certain specified hostnames into the local server, where the hostnames can be any arbitrary DNS names or IPv4/IPv6 addresses, optionally combined with certain TCP ports. The DNS interception works **only** with the built-in client, and does not work for third-party clients — they should explicitly use the ``kmock.url`` endpoint. For details, see :class:`kmock.AiohttpInterceptor`.

Both the handler and the server MUST be entered as context managers to serve the requests. Mind that under the hood, the server, when activated, automatically adds itself to the provided handler (for URLs & hosts & ports), and removes itself when deactivated.

.. note::

    HTTPS is currently not supported, but will be in the futur (with self-signed certificates).


Standalone servers
==================

If you do not use any testing framework or maybe do not write tests at all, the easiest way to start is to run a standalone server.

This example accepts the requests on port 12345, responds with the hard-coded payload on the root endpoint, and prints a message locally on stdout on every request (server-side) — to show that it is alive. For the sake of example, it makes an initial request to the intercepted hostname ``google.com`` using the embedded client immediately on the start, and then sleeps forever letting you use ``curl`` or similar tools on the command line.

.. code-block:: python

    import asyncio
    from kmock import Server, RawHandler

    async def main() -> None:
        async with RawHandler() as kmock, Server(kmock, port=12345, hostnames=['google.com']):
            kmock['/'] << b'Hello, there!' << lambda req: print(f"{req}")

            resp = await kmock.get('http://google.com/')
            text = await resp.read()
            print(f"Response: {text}")

            print(f"Now do: curl -i {kmock.url!s}")
            await asyncio.Event().wait()  # sleep forever


    if __name__ == '__main__':
        asyncio.run(main())

Run it in your IDE or in the CLI. When needed, stop it with Ctrl-C:

.. code-block::

    $ python server.py

Access the server from another shell:

.. code-block:: shell

    $ curl -i http://localhost:12345/
    HTTP 200 OK

    Hello, there!


Pytest integration
==================

Pytest fixtures
---------------

If you use pytest_, a fixture named ``kmock`` is provided out of the box with a preconfigures handler and an already running server. The server's URL is available via ``kmock.url``.

.. _pytest: https://pytest.org/

.. code-block:: python

    from kmock import KubernetesEmulator

    def test_me(kmock: KubernetesEmulator) -> None:
        kmock.objects['kopf.dev/v1/kopfexamples', 'ns', 'name'] = {'spec': 123}
        resp = await kmock.get('/apis/kopf.dev/v1/kopfexamples')  # list cluster-wide
        data = await resp.json()
        assert kmock.Object(data) >= {'items': [{'spec': 123}}]}

Alternatively, you can make your self-made fixtures with one or more K8s mock servers, even running in parallel (e.g. for multi-cluster API testing):

.. code-block:: python

    import pytest_asyncio
    from kmock import RawHandler, Server

    @pytest_asyncio.fixture
    async def myk8s() -> AsyncIterator[RawHandler]:
        async with RawHandler() as handler, Server(handler, host='127.0.0.1', port=12345) as server:
            print(f"Listening on {server.url}")
            yield handler

KMock co-operates with aresponses_ if it (or they) is/are present. For this, the mock server restores the host & port resolution for its own host & port only, but leaves everything else to ``aresponses`` as it/hey want(s) to have it. The default ``kmock`` fixture therefore depends on ``aresponses`` in the resoltution order, putting ``aresponses`` ahead. Otherwise —if ``aresponses`` is initialised afer ``kmock``— ``aresponses`` would intercept all the traffic and redirect it into itself, including the Kubernetes traffic, so the KMock server would get nothing. To simulate this behaviour with your own fixtures, put ``aresponses`` into their dependencies (even if not actually used).

.. _aresponses: https://github.com/aresponses/aresponses


Pytest markers
--------------

In pytest, the handler class and several of its parameters can be overridden on a per-function, per-class, per-module, per-package, or per-session level with pytest marks — with the more specific (closest) markers overriding the more generic (farthest) options:

.. code-block:: python

    import kmock
    import pytest

    pytestmark = pytest.mark.kmock(cls=kmock.KubernetesEmulator)

    def test_with_a_stateful_kubernetes_server(kmock: kmock.KubernetesEmulator) -> None:
        pass

    @pytest.mark.kmock(cls=kmock.KubernetesScaffold)
    def test_with_a_bare_kubernetes_server(kmock: kmock.KubernetesScaffold) -> None:
        pass

The default is the most functionally advanced server — :class:`kmock.KubernetesEmulator`.

.. code-block:: python


    import pytest

    @pytest.mark.kmock(port=12345, hostnames=['google.com'])
    def test_me(kmock):
        kmock << b'Hello! I am not Google.'
        resp = await kmock.get('http://google.com/?q=search')
        text = await resp.read()
        assert text == b'Hello! I am not Google.'

Other keyword parameters of the mark are passed to the server's or handler's constructors as is — see below.


Configuration
=============

The folowing parameters can be used in the pytest marks or directly with handlers/servers (given with their defaults or types):

- ``cls: type[kmock.RawHandler] = kmock.KubernetesEmulator`` is the handler class to use, a descendant of :class:`kmock.RawHandler`.

- Server parameters:

  - ``host: str = '127.0.0.1'`` — a local IPv4/IPv6 address to listen for connections.
  - ``port: int | None = None`` — the port for listening. ``None`` means auto-select the next free port. The real port can be taken from ``kmock.port`` or ``kmock.url``.
  - ``client_fct: Callable[[yarl.URL], aiohttp.ClientSession]`` — a factory for aiohttp-based clients. By default a simple non-configured :class:`aiohttp.ClientSession` is created.
  - ``hostnames = None`` — a collection of DNS hostname, IPv4/IPv6 addresses, or hosts-ports to intercept and forward into the handler. For the details on supported formats, see :class:`kmock.AiohttpInterceptor`.
  - ``user_agent: str`` — a user-agent to send with the embedded client. By default, it is the current version of KMock and aiohttp.

- Handler parameters:

  - ``limit: int | None = None`` — restrict the number of requests served by the server in general, regardless of individual responses. This can be helpful if there is a risk of running into infinite requesting cycle — with such a limit, it will stop sooner or later. ``None`` means unlimited ("no limit").
  - ``strict: bool = False`` — whether to raise the exceptions; by default, they are collected in ``kmock.errors`` for future assertions and not escalated further from the handler.


Embedded client
===============

The ``kmock`` fixture in pytest starts a local web server locally and creates an associated client. Specifically, the client has the base URL configured to point to the local server (including the dynamically allocated port), so that the relative URLs could be used in tests.

The underlying aiohttp server & client can be accessed as ``kmock.server`` & ``kmock.client`` — without any additional fixtures:

.. code-block:: python

    async def test_me(kmock: kmock.RawHandler) -> None:
        kmock['/'] << 444 << b'{"key": "val"}'

        url = kmock.server.make_url('/path?q=params')
        assert str(url).startswith('http://127.0.0.1:')
        assert url.port >= 1024
        assert url.path == '/path'

        resp = await kmock.get('/')
        data = await resp.json()
        assert resp.status == 444
        assert data == {'key': 'val'}

.. warning::

    Both the client & the server are currently implemented with aiohttp_ — :class:`aiohttp.ClientSession` and :class:`aiohttp.test_utils.RawTestServer` accordingly. They are also declared with these specific types — to simplify type-checking and IDE hinting. However, this is not guaranteed in the future and the underlying library can change at any time. To reduce the impact in this case, the new client will provide the typical requesting methods & fields with the same typical signature. This is the reason that only a minimal subset of aiohttp methods is exposed in the KMock handlers.

    In case you rely heavily on ``aiohttp`` or want to use another client/server library (or two different libraries), override the ``kmock`` fixture in the root ``conftest.py`` and assemble your own setup similar to how the provided fixture does this (see the source code). The main class is a simple callable that takes a request in and returns a response out (WSGI-style).

.. _aiohttp: https://docs.aiohttp.org/en/stable/
