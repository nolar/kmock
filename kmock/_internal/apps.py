import asyncio
import contextlib
import sys
import traceback
from collections.abc import AsyncIterator, Awaitable, Callable
from importlib.metadata import version
from types import TracebackType
from typing import Any, AsyncContextManager, Protocol

import aiohttp.client
import aiohttp.test_utils
import aiohttp.web
import attrs
import yarl
from typing_extensions import Self

from kmock._internal import boxes, dns, dsl, enums, filtering, rendering, resources


# We mirror the client methods of aiohttp on the server object of kmock.
# It uses the private class `aiohttp.client._RequestContextManager` (not good).
# Instead, we only re-declare the promised protocol for regular & streaming requests.
class _RequestContextManager(
    Protocol,
    Awaitable[aiohttp.ClientResponse],
    AsyncContextManager[aiohttp.ClientResponse],
):
    pass


class KMockError(Exception):
    pass


@attrs.mutable
class Server:
    """
    All-in-one bundle needed to run the mock app on an HTTP port.

    The handlers are simple WSGI-like apps that have no networking capabilities.
    The servers implement networking, specifically listening on a TCP/HTTP port
    and marshalling the requests & responses to/from the handler.

    Kmock uses `aiohttp` by default. Using other libraries is possible as long
    as the incoming reqeusts & responses support the core signatures of aiohttp.
    This is NOT an officially supported functionality and might break any time.

    There can be several severs pointing to the same handler —
    e.g. with dfferent hosts:ports, therefore different URLs.
    The traffic is balanced across such entry points when the client methods
    of the handler are used. When the client methods of a specific server
    are used, the traffic goes through that server's endpoint only.

    A few examples with 2 servers on different random ports pointing
    to the same handler, which defines the reactions & accumulates the requests.

    Automatically balanced traffic::

        async with RawHandler() as kmock, Server(kmock), Server(kmock):
            for _ in range(10):
                await kmock.get('/')

    Routing the traffic manually by directly using the server::

        async with RawHandler() as kmock, Server(kmock), Server(kmock) as srv2:
            for _ in range(10):
                await srv2.client.get('/')

    The same as above, but via the handler (e.g. via a fixture)::

        async with RawHandler() as kmock, Server(kmock), Server(kmock):
            for _ in range(10):
                await kmock.clients[1].get('/')
    """

    handler: "RawHandler"

    # Very optional overrideable factories.
    _host: str = '127.0.0.1'
    _port: int | None = None  # exposed as .port with the ACTUALLY assigned port
    _server_cls: type[aiohttp.test_utils.RawTestServer] = aiohttp.test_utils.RawTestServer
    _client_fct: Callable[[yarl.URL], aiohttp.ClientSession] = aiohttp.ClientSession
    hostnames: dns.ResolverFilter | None = None

    # Populated only when entered. Reset to None when exited.
    _managed_server: aiohttp.test_utils.BaseTestServer | None = attrs.field(default=None, init=False)
    _managed_client: aiohttp.ClientSession | None = attrs.field(default=None, init=False)
    _managed_interceptor: dns.AiohttpInterceptor | None = attrs.field(default=None, init=False)

    # Expose the client in case we miss the server and connect elsewhere (set to '' to disable).
    user_agent: str = attrs.field(default=f"kmock/{version('kmock')} aiohttp/{version('aiohttp')}", kw_only=True)

    @property
    def url(self) -> yarl.URL:
        if self._managed_server is not None:
            return self._managed_server.make_url('')
        else:
            raise RuntimeError("The server is not active and has no URL yet.")

    @property
    def host(self) -> str:
        """
        The real host (IP address) assigned to the server (when started).

        If listening on a catch-all host (e.g. 0.0.0.0), this will report
        any IP address of the current machine, preferably localhost/127.0.0.1.
        I.e., it points to the host where the server can be accessed,
        not only where it is listening.
        """
        if self._managed_server is not None:
            return self._managed_server.host
        else:
            return self._host

    @property
    def port(self) -> int:
        """The real port assigned to the server (when started)."""
        if self._managed_server is not None and self._managed_server.port is not None:
            return self._managed_server.port
        elif self._port is not None:
            return self._port
        else:
            raise RuntimeError("The server is not active and has no port yet.")

    @property
    def client(self) -> aiohttp.ClientSession:
        if self._managed_client is not None:
            return self._managed_client
        else:
            raise RuntimeError("The server is not active and has no client yet.")

    @property
    def server(self) -> aiohttp.test_utils.BaseTestServer:
        if self._managed_server is not None:
            return self._managed_server
        else:
            raise RuntimeError("The server is not active and has no underlying server yet.")

    async def __aenter__(self) -> Self:
        if self._managed_server is not None or self._managed_client is not None:
            raise RuntimeError("The server can be started/entered only once.")

        self._managed_server = self._server_cls(self.handler, host=self._host, port=self._port)
        await self._managed_server.__aenter__()

        headers = {'User-Agent': self.user_agent} if self.user_agent else {}
        self._managed_client = self._client_fct(self._managed_server.make_url('/'))
        self._managed_client.headers.update(headers)
        await self._managed_client.__aenter__()

        server = self._managed_server
        self._managed_interceptor = dns.AiohttpInterceptor(server.host, server.port, self.hostnames)
        await self._managed_interceptor.__aenter__()

        # Register as one of the servers pointing to this handler, the traffic will be balanced.
        self.handler.servers.append(self)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        # Unregister the server from the handler.
        self.handler.servers.remove(self)

        # Shutdown the services.
        assert self._managed_interceptor is not None
        assert self._managed_client is not None
        assert self._managed_server is not None
        await self._managed_interceptor.__aexit__(exc_type, exc_value, traceback)
        await self._managed_client.__aexit__(exc_type, exc_value, traceback)
        await self._managed_server.__aexit__(exc_type, exc_value, traceback)
        self._managed_interceptor = None
        self._managed_client = None
        self._managed_server = None


@attrs.define(kw_only=True)
class RawHandler(dsl.Root):
    """
    A mock handler to be injected into WSGi-like servers.

    The criteria & responses can be injected with the ``<<``/``>>``
    (see :doc:`/requests` and :doc:`/responses`).

    For a locally running server with a TCP port, see :class:`Server`.

    **Implementation details:**

    Due to the nature of async/await routines, it is impossible to notify
    the stream consumers about the addition of new items from synchronous
    methods like ``<<`` / ``>>`` — it is only possible from asynchronous ones.

    The only known primitive supporting synchronous "nowait" is `asyncio.Queue`:
    even if the item is put via `asyncio.Queue.put_nowait`, all async consumers
    get it immediately.

    To work around this limitation, the handler/server **MUST** be "entered"
    as a context manager (``async with``), which implicitly starts a background
    task and uses a queue to deliver the items in the "nowait" mode.

    This comes with trade-offs:

    * First, there can be a minor delay after stream feeding and before
      the items are delivered to live streams. This is actually utilised
      to pack several fed items into one batch, as in:
      ``kmock[...] << b'hello' << b'world' << ...``.

    * Second, if the code has no ``await`` somewhere after feeding the content,
      the streams can be blocked with no actual delivery happening until
      the code gives control back to the event loop via the next ``await``.
    """

    limit: int | None = None  # how many requests to serve in total
    strict: bool = False  # whether to serve unknown resources or not

    # Context managers are idempotent (can be re-entered) but each level accumulates its own errors.
    _entered: int = 0
    _errors: list[list[Exception]] = attrs.field(factory=list, init=False)

    # Which servers are served by this handler. Empty if offline or served by unsupported servers.
    servers: list["Server"] = attrs.field(factory=list, init=False, on_setattr=attrs.setters.frozen)

    @property
    def clients(self) -> list[aiohttp.ClientSession]:
        return [server.client for server in self.servers]

    @property
    def active(self) -> bool:
        return bool(self._entered)

    @property
    def errors(self) -> list[Exception]:
        """Errors of the current level of context managers (for assertions)."""
        if not self._errors:
            raise RuntimeError(
                "Handlers accumulate errors only when used as context managers. "
                "Outside of context managers, errors are escalated in place."
            )
        return self._errors[-1]

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self._entered += 1
        self._errors.append([])
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._entered -= 1
        errors = self._errors.pop(-1)

        # Cleanup the system resources as soon as possible, before re-raising of any kind.
        if not self._entered:
            await super().__aexit__(exc_type, exc_value, traceback)

        # Accumulated (request-related) & escalated (code-related) errors never intermix!
        # If nested levels raise errors or error groups from requests, they are never combined.
        # Want combined error groups? Then avoid nested context managers, use the top-level one.
        if self.strict and exc_value is None and errors:
            if sys.version_info >= (3, 11) and len(errors) > 1:
                raise ExceptionGroup("Several exceptions happened.", tuple(errors))
            else:
                raise errors[0]

    async def __call__(self, raw_request: aiohttp.web.BaseRequest) -> aiohttp.web.StreamResponse:
        """
        The main entry point when served by a WSGI/aiohttp test server or app.
        """

        # Ensure the full request payload is fetched & buffered before the connection is closed.
        # We might need the raw requests later in the tests for assertions/filtering.
        await raw_request.read()

        raw_response: aiohttp.web.StreamResponse | None = None
        try:
            # Whatever came in, if we are beyond overall server threshold on requests, stop it.
            # We can only hope that the client side will understand it and re-raise as an API error.
            if self.limit is not None and len(self._requests) >= self.limit:
                raise KMockError('Too many requests have been served so far.')

            # Parse & interpret the intentions of the requester.
            request = await rendering.Request._parse(raw_request, id=len(self._requests))
            self._requests.append(request)

            # Unwrap errors if the streaming response is already started and streamed the headers.
            # Note: created but not prepared responses will be replaced with a usual 500 response.
            try:
                return await self._handle(request)
            except rendering.StreamingError as e:  # unwrap only, do not handle
                raw_response = e.args[0]
                if e.__cause__ is not None:
                    raise e.__cause__  # guaranteed in our case; for type checkers
                else:
                    raise  # pragma: no cover  # never happens in our case

        # Server-side errors are difficult to debug in the client side when the server disconnects.
        # As such, catch all errors and provide it to clients and let them fail.
        # Mind that both the user-provided callbacks and our own code can fail.
        except Exception as e:
            # Outside of context managers, let the caller (e.g. a web server) deal with the failure.
            if not self._errors:
                raise

            # Inside the context managers, accumulate the errors and re-raise at exiting.
            self._errors[-1].append(e)

            # If the connection already got some traffic, reuse that stream. If not, respond anew.
            if raw_response is None or not raw_response.prepared:
                return await self._render_error(e)
            else:
                await self._stream_error(e, raw_response)
                await raw_response.write_eof()
                return raw_response

    async def _handle(self, request: rendering.Request) -> aiohttp.web.StreamResponse:
        """
        Serve the incoming request.

        Depending on the implementation, this method either finds a matching
        criteria and associated payload provided by users, or implements
        a more sophisticated reaction that cannot be expressed by the DSL.
        """

        # Having mixed-length/mixed-depth priorities, pad them with zeroes to the same size so that
        # the comparison is fair: (100,0)>(100,-1), despite (100,)<(100,-1) because it is shorter.
        # This is critical for e.g. `self.fallback ** N` to be a sub-priority ±N within the -∞.
        priorities: list[tuple[float, ...]] = [payload.priorities for payload in self._payloads]
        max_length: int = max(len(priority) for priority in priorities) if priorities else 0
        priorities = [tuple(-p for p in priority) for priority in priorities]  # reverse-sort
        priorities = [priority + (0,) * (max_length - len(priority)) for priority in priorities]
        indexes = sorted(range(len(priorities)), key=lambda index: priorities[index])
        payloads = [self._payloads[index] for index in indexes]

        # The only sure way to check if the filters see the request, is to really apply them.
        # Otherwise, the logic of slices, unions, intersections, can be too tricky to simulate.
        # As a result, filtering is very expensive — do this lazily until the 1st suitable match.
        for payload in payloads:
            if request in payload._source and not payload._disabled.is_set():
                try:
                    return await payload(request)
                except rendering.ReactionMismatchError:  # either mismatch or depletion
                    payload._disabled.set()
                    pass
                except NotImplementedError:  # matched, but non-actionable (nothing to respond with)
                    pass

        # We do NOT imply any default response. If needed, add low-priority reactions explicitly.
        raise NotImplementedError(
            'Undefined server behaviour: no reaction matching the request is defined. '
            'Consider adding a catch-all fallback reaction: `kmock.fallback << 404`.'
        )

    async def _render_error(self, exc: Exception) -> aiohttp.web.StreamResponse:
        # In a non-specific HTTP server, dump the exception as plain text.
        return aiohttp.web.Response(text=traceback.format_exc(), status=500)

    async def _stream_error(self, exc: Exception, raw_response: aiohttp.web.StreamResponse) -> None:
        # NB: We cannot change the status (it's too late), though we should.
        await raw_response.write(''.join(traceback.format_exception(exc)).encode())

    def _next_server(self) -> "Server":
        if not self.servers:
            raise RuntimeError(
                "There is no running server associated with this mock handler, therefore no URL."
                " Did you forget `async with Server(kmock): ...` for a custom handler?"
            )

        # Having many servers, the request can go through any of them with the same response,
        # but with different URLs (host:port) remembered. For consistency, round-robin over them:
        # in most test cases, the only request will go through the 1st server; others will be balanced.
        return self.servers[len(self._requests) % len(self.servers)]

    @property
    def url(self) -> yarl.URL:
        return self._next_server().url

    # Mimic aiohttp client signatures on the kmock server object directly — as shortcuts.
    # Support both the awaitable coroutine & context manager protocols (for streaming/chunking).
    def request(self, method: str, url: str, **kwargs: Any) -> _RequestContextManager:
        return self._next_server().client.request(method, url, **kwargs)

    def get(self, url: str, **kwargs: Any) -> _RequestContextManager:
        return self.request(enums.method.GET.value, url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> _RequestContextManager:
        return self.request(enums.method.PUT.value, url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> _RequestContextManager:
        return self.request(enums.method.POST.value, url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> _RequestContextManager:
        return self.request(enums.method.PATCH.value, url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> _RequestContextManager:
        return self.request(enums.method.OPTIONS.value, url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> _RequestContextManager:
        return self.request(enums.method.HEAD.value, url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> _RequestContextManager:
        return self.request(enums.method.DELETE.value, url, **kwargs)

    # Expose commonly used classes via the fixture without explicit imports.
    # The library itself DOES NOT use these fields, it uses the classes directly.
    # For when the fixture name overlaps the library name, so that it requires writing `import…as…`.
    Server = staticmethod(Server)
    Request = staticmethod(rendering.Request)
    Sink = rendering.Sink
    Payload = rendering.Payload
    Criteria = staticmethod(filtering.Criteria)
    Criterion = filtering.Criterion

    # Multi-purpose markers (criteria/payloads) are done as standalone boxes or enums.
    # Single-purpose markers (criteria-only) produce specialised Criteria descendants.
    path = staticmethod(boxes.path)
    body = staticmethod(boxes.body)
    text = staticmethod(boxes.text)
    data = staticmethod(boxes.data)
    action = staticmethod(enums.action)
    method = staticmethod(enums.method)
    params = staticmethod(boxes.params)
    cookies = staticmethod(boxes.cookies)
    headers = staticmethod(boxes.headers)
    clusterwide = staticmethod(filtering.clusterwide)
    namespace = staticmethod(filtering.namespace)
    name = staticmethod(filtering.name)
    subresource = staticmethod(filtering.subresource)
    resource = staticmethod(resources.resource)
