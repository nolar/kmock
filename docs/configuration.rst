=============
Configuration
=============

Configuration methods
=====================

Configuring with pytest marks
-----------------------------

As with all pytest marks, the config can be applied either to individual tests, or to the whole module of tests:

.. code-block:: python

    import kmock

    # Module-level config applies to all tests in the module.
    pytestmark = [pytest.mark.kmock(port=12345, cls=kmock.RawHandler)]

    # Individual tests can override the module-level or default configs.
    @pytest.mark.kmock(port=23456, hostnames=['google.com'])
    async def test_with_overridden_config(kmock: kmock.RawHandler) -> None:
        assert kmock.port == 23456


Configuring the global defaults
-------------------------------

The global defaults in all modules of the test suite, so as with individual modules or packages, can be overridden with the ``kmock_options`` fixture, e.g. in the ``conftest.py`` file. The fixture must return a dict with the options:

.. code-block:: python

    import kmock
    import pytest

    @pytest.fixture
    def kmock_options() -> dict[str, Any]:
        return dict(port=12345, cls=kmock.RawHandler)


Configuring with config files
-----------------------------

These options (but not others) below can also be set globally via the pytest config files — the syntax slightly varies depending on which config file is used:

.. code-block:: ini

    # pytest.ini
    [pytest]
    kmock_cls = kmock.RawHandler
    kmock_limit = 999
    kmock_strict = true

.. code-block:: toml

    # pyproject.toml
    [tool.pytest]
    kmock_cls = "kmock.RawHandler"
    kmock_limit = 999
    kmock_strict = true


Configuration options
=====================

The folowing parameters can be used in the pytest marks or directly with handlers/servers (given with their defaults or types):


Mock handler class
------------------

``cls: type[kmock.RawHandler] = kmock.KubernetesEmulator`` is the handler class to use. The default is the most advanced Kubernetes emulator, :class:`kmock.KubernetesEmulator`. Another available handler is :class:`kmock.KubernetesScaffold`. Any custom-made class can also be used — if it inherits from :class:`kmock.RawHandler`.


Server options
--------------

``host: str = '127.0.0.1'`` is a local IPv4/IPv6 address to listen for connections. The default is 127.0.0.1 to avoid accidentally exposing the mock server to the local or global networks.

``port: int | None = None`` is the TCP port for listening. ``None`` means auto-picking the next free port. The real picked port can be taken at runtime from ``kmock.port`` or ``kmock.url``.


Handler options
---------------

``limit: int | None = None`` restricts the number of requests served by the server/handler in general per test, regardless of individual responses. This can be helpful if there is a risk of running into infinite requesting cycle — with such a limit, it will stop sooner or later. ``None`` means unlimited ("no limit").

``strict: bool = False`` defines whether to raise the exceptions at the end of the test; by default, they are collected in ``kmock.errors`` for future assertions and not escalated further from the handler.


Embedded client options
-----------------------

``client_fct: Callable[[yarl.URL], aiohttp.ClientSession]`` is a factory for aiohttp-based clients. By default a simple non-configured :class:`aiohttp.ClientSession` is created. You might want to configure it, e.g. with a default timeout. Note that aiohttp recommends to not make custom client classes, so it is a factory instead. The only positional argument of the factory is the base URL of the server that listens for the connections.

``user_agent: str`` — a user-agent for the embedded client, as it is sent to the servers (mocked or real). By default, it is the current version of KMock and aiohttp, e.g. ``"kmock/0.0.1 aiohttp/3.13.2"``.


DNS interception options
------------------------

``hostnames = None`` is a collection of DNS hostname, IPv4/IPv6 addresses, or hosts-ports to intercept and forward into the handler. For the details on supported formats, see :class:`kmock.AiohttpInterceptor`.

Briefly, the following notations are supported for the DNS interception:

- ``'example.com'`` (a single string with a hostname).
- ``('example.com', 80)`` (a 2-item tuple with a hostname and a port).
- ``['example.com', 'google.com']`` (a list of hostnames).
- ``{'example.com', 'google.com'}`` (a set of hostnames).
- ``['example.com', ('google.com', 80)]`` (a list of hostname and port pairs, mixed).
- ``{'example.com', ('google.com', 80)}`` (a set of hostname and port pairs, mixed).
- ``re.compile(r'.*\.example\.com')`` (a regexps for the hostnames).
- ``(re.compile(r'.*\.example\.com'), 80)`` (a tuple with the hostname regexps and a port).
- ``[re.compile(r'.*\.example\.com'), re.compile(r'.*\.local')]`` (a list of regexps of hostnames).
- ``{re.compile(r'.*\.example\.com'), re.compile(r'.*\.local')}`` (a set of regexps of hostnames).
- ``['10.20.30.40', '::1']`` (IPv4/IPv6 addresses as the hostnames, if access by the address).
- And any other combinations with the same semantics as above.
