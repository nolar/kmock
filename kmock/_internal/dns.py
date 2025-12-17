import collections.abc
import re
from collections.abc import Collection
from types import TracebackType
from typing import Any, AsyncContextManager, Protocol, TypedDict, cast

import aiohttp.connector
import attrs
from typing_extensions import Self


class ResolvedHost(TypedDict):
    hostname: str
    host: str  # ip address
    port: int
    family: int
    proto: int
    flags: int


class ResolverFn(Protocol):
    async def __call__(
            self, host: str, port: int, traces: list[Any] | None = None
    ) -> list[ResolvedHost]:
        ...


ResolverHostOnly = re.Pattern[str] | str
ResolverHostPort = tuple[ResolverHostOnly, int | None]
ResolverHostSpec = ResolverHostOnly | ResolverHostPort
ResolverFilter = ResolverHostSpec | Collection[ResolverHostSpec]


@attrs.define(kw_only=False)
class AiohttpInterceptor(AsyncContextManager["AiohttpInterceptor"]):
    r"""
    Intercept hostname resolution for selected hostnames to specified IP:port.

    The hostname filter can be specified either by explicit string or a regexp,
    or by a list/set of strings/regexpsts. The regexp patterns must match fully.
    String hostnames are case-insensitive, while patterns are case-sensitive
    (add `re.I` to make it case insensitive explicitly).

    For extra precision, the filter can be also specified as tuple(s)
    with the hostname (as defined above) and a specific port (integer).

    Examples:

    * `'kopf.dev'`
    * `re.compile(r'kopf\..*')`
    * `['kopf.dev', re.compile(r'kopf\..*')]`
    * `('kopf.dev', 80)`
    * `(re.compile(r'kopf\..*'), 443)`
    * `{('kopf.dev', 80), (re.compile(r'kopf\..*'), 443), 'kopf.cloud'}`

    If the target port is not specified, it resolves to the requested port.
    Otherwise, it is also intercepted and forced to the specified port.

    The filter can be modified at runtime if needed.

    The target host & port are always intercepted regardless of the filter.

    The resolver affects the hostname resolution only since the moment it is
    entered and only until it is exited. Multiple resolvers must be stacked
    as LIFO (last-in-first-out): i.e. exited in the reverse sequence as entered.

    .. warning:

        If used together with `aresponses`, the resolvers must be entered
        (but not necessarily created) strictly after the `aresponses` server.
        Otherwise, `aresponses` intercepts the resolution of **all** hostnames,
        so the resolution process never gets to the pre-entered resolvers.
        The interceptor cannot check for this case at runtime on its own
        because it gets no execution after this happens.
    """
    host: str
    port: int | None = None
    extra: ResolverFilter | None = None

    # These fields are used with "type:ignore" since it is a dirty hacking, MyPy does not like it.
    _own_resolver: ResolverFn | None = None
    _cascaded_resolver: ResolverFn | None = attrs.field(default=None, init=False)

    async def __aenter__(self) -> Self:
        if self._cascaded_resolver is not None:
            raise RuntimeError("The same resolver cannot be entered twice.")

        # We have to use a locally defined function instead of a class method
        # because of [self] vs. [connector] mess in case of class methods.
        async def _resolve_host(
                connector: aiohttp.connector.TCPConnector,
                host: str,
                port: int,
                traces: list[Any] | None = None,
        ) -> list[ResolvedHost]:
            nonlocal self
            target_filter = (self.host, self.port)
            if self._check(target_filter, host, port) or self._check(self.extra, host, port):
                return [ResolvedHost(
                    hostname=host,
                    host=self.host,
                    port=self.port if self.port is not None else port,
                    family=connector._family,
                    proto=0,
                    flags=0,
                )]
            else:
                return await self._cascaded_resolver(connector, host, port, traces=traces)  # type: ignore

        # No lock are needed: in the same event loop, these operations are not async, thus atomic.
        self._own_resolver = cast(ResolverFn, _resolve_host)
        self._cascaded_resolver = cast(ResolverFn, aiohttp.connector.TCPConnector._resolve_host)
        aiohttp.connector.TCPConnector._resolve_host = _resolve_host  # type: ignore

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._cascaded_resolver is None:
            raise RuntimeError("The resolver cannot be exited because it was not entered.")
        elif aiohttp.connector.TCPConnector._resolve_host is not self._own_resolver:  # type: ignore
            raise RuntimeError("The resolver chain is inconsistent. Maybe overridden by others?")

        # No lock are needed: in the same event loop, these operations are not async, thus atomic.
        aiohttp.connector.TCPConnector._resolve_host = self._cascaded_resolver  # type: ignore
        self._cascaded_resolver = None

    def _check(self, filter: ResolverFilter | None, host: str, port: int | None) -> bool:
        match filter:
            case None:
                return False
            case str():
                return filter.lower() == host.lower()
            case re.Pattern():
                return filter.fullmatch(host) is not None

            # Only [host,port] pairs, be that tuples or list, but not sets/strs/bytes.
            case list() | tuple() if len(filter) == 2 and filter[-1] is None:
                return self._check(filter[0], host, port)
            case list() | tuple() if len(filter) == 2 and isinstance(filter[-1], int):
                return self._check(filter[0], host, port) and port == filter[-1]

            # Other (host,...) tuples, lists, or sets, including 2-item ones.
            # Caveat: port's "int" type leaks into "sub", since (host,port) is also a collection.
            # But we need to support 2-item tuples as generic collections, too, without int ports.
            # Hence a bit hacky `not isinstance(sub, int)` check — this never happens actually.
            case collections.abc.Collection():
                return any(
                    self._check(sub, host, port) for sub in filter if not isinstance(sub, int)
                )

            case _:
                raise TypeError(f"Unsupported filter: {filter!r}")
