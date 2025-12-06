import asyncio
import collections.abc
import concurrent.futures
import inspect
import io
import json
import pathlib
import queue
import threading
import warnings
from collections.abc import AsyncGenerator, AsyncIterable, AsyncIterator, Awaitable, Callable, \
                            Generator, Iterable, Mapping, MutableSequence, MutableSet, Sequence
from types import EllipsisType, NotImplementedType
from typing import Any, Union, cast, final

import aiohttp.web
import attrs
import yarl
from typing_extensions import Self

from kmock._internal import aiobus, boxes, enums, parsing, resources

# Multi-type content for responses, with a heuristic to serve each type differently.
# Each item can be the whole response or a step of a streaming response.
# TODO: Rewrite Union[X,Y] to X|Y when Python 3.10 is dropped (≈October 2026).
#   Fails on Unions + ForwardRefs: https://github.com/python/cpython/issues/90015
Payload = Union[
    None,

    # Raw binary payload get into the response bodies or streams unmodified:
    bytes,
    pathlib.Path,
    io.RawIOBase,
    io.TextIOBase,
    io.BufferedIOBase,

    # Plain types with JSON-like syntax in Python go to requests JSON- or JSON-lines-encoded:
    str,
    int,
    float,
    list[Any],
    dict[Any, Any],
    Mapping[Any, Any],

    # Ellipsis ("...") marks a live response (if top-level) or a live stream segment (if nested):
    EllipsisType,

    # Round-brackets (collections, generators) become streams; they can be individually depleted:
    tuple["Payload", ...],
    Iterable["Payload"],
    AsyncIterable["Payload"],

    # Lazily evaluated content is unfolded at request handling time:
    Awaitable["Payload"],  # coros, tasks, futures (awaited before rendering)
    Callable[[], "Payload"],  # lambdas, partials, sync & async callbacks
    Callable[["Request"], "Payload"],  # lambdas, partials, sync & async callbacks

    # Exceptions are re-raised in place (some have special meaning):
    type[BaseException],
    BaseException,

    # Pre-interpreted or explicitly classified metadata to override the declared one:
    "Response",

    # An internal trick to keep side effects inbetween content sequence, but ignore their results:
    "SinkBox",
]

# Boxes can be fed into ``<<``, but never get into the payload directly (thus a separate type).
PayloadBox = (
    boxes.data |
    boxes.text[None] |
    boxes.body[None] |
    boxes.headers[None] |
    boxes.cookies[None]
)

# Sinks are where the requests go to, but any results of it are ignored. Typically used via >>.
# TODO: Rewrite Union[X,Y] to X|Y when Python 3.10 is dropped (≈October 2026).
#   Fails on Unions + ForwardRefs: https://github.com/python/cpython/issues/90015
Sink = Union[
    None,

    # For files & i/o, the requests are append-saved into those files (not overwritten!):
    #   kmock['get /'] >> pathlib.Path('/tmp/reqs.log') >> (sio:=io.StringIO())
    pathlib.Path,
    io.RawIOBase,
    io.TextIOBase,
    io.BufferedIOBase,

    # Mutable collections get the requests added to them (no dicts yet: unclear value):
    #   kmock['get /'] >> (requests:=[]) >> (deduplicated:=set())
    MutableSequence["Request"],
    MutableSet["Request"],

    # Synchronization primitives get the request object put/set into them:
    #   kmock['get /'] >> (fut:=asyncio.Future()) >> (queue:=asyncio.Queue())
    concurrent.futures.Future["Request"],
    asyncio.Future["Request"],
    asyncio.Queue["Request"],
    queue.Queue["Request"],
    threading.Event,
    threading.Condition,
    asyncio.Event,
    asyncio.Condition,
    aiobus.Bus["Request"],

    # Generators (but not simple iterators/iterables) get the requests from their `yield`.
    # The yield is interpreted as if it were an effect, or ignored if not recognized.
    Generator[Union["Sink", Any], Union["Request", None], Union["Sink", None]],
    AsyncGenerator[Union["Sink", Any], Union["Request", None]],

    # Lazily evaluated content is unfolded at request handled time.
    # The result is interpreted as it it were an effect, or ignored if not recognized.
    Awaitable[Union["Sink", Any]],  # coros, tasks, futures (awaited before rendering)
    Callable[[], Union["Sink", Any]],  # lambdas, partials, sync & async callbacks
    Callable[["Request"], Union["Sink", Any]],  # lambdas, partials, sync & async callbacks

    # An internal trick to keep side effects inbetween content sequence, but ignore their results:
    "SinkBox",
]

# The same as unions above, but for runtime quick-checking:
SUPPORTED_SINKS: tuple[type[Any], ...] = (
    collections.abc.Awaitable,
    # collections.abc.Callable,  # checked explicitly; breaks mypy
    pathlib.Path, io.RawIOBase, io.BufferedIOBase, io.TextIOBase,
    aiobus.Bus, asyncio.Event, asyncio.Queue, asyncio.Condition, asyncio.Future,
    threading.Event, queue.Queue, threading.Condition, concurrent.futures.Future,
    collections.abc.MutableSet, collections.abc.MutableSequence, collections.abc.MutableMapping,
    collections.abc.Generator, collections.abc.AsyncGenerator,
)
SUPPORTED_PAYLOADS: tuple[type[Any], ...] = (
    BaseException,
    bytes, int, float, bool, str, list, dict,
    pathlib.Path, io.RawIOBase, io.BufferedIOBase, io.TextIOBase,
    collections.abc.Iterable, collections.abc.AsyncIterable, collections.abc.Mapping,
    EllipsisType, NotImplementedType,
    collections.abc.Awaitable,
    # collections.abc.Callable,  # checked explicitly; breaks mypy
)


# You might want to wrap it into a closure. Forget it! That requires interpreting value types and
# signatures internally the same way as it is already done in the response rendering:
# pure awaitables, callable coroutines, sync/async callables with and without arguments, etc.
# The internal lightweight container is the simplest and also the most performant solution.
class SinkBox:
    __slots__ = '_item'
    _item: Sink

    def __init__(self, arg: Sink, /) -> None:
        super().__init__()

        # Quick early check of supported types: at definition in tests, not at execution in servers.
        # This simplifies the development in case of errors or misuse.
        if arg is None:
            self._item = arg
        elif isinstance(arg, SUPPORTED_SINKS) or callable(arg):
            self._item = arg
        else:
            raise ValueError(f"Unsupported type of a side effect: {type(arg)}")


@final
@attrs.mutable(kw_only=True)  # mutable to accumulate the payload into one tuple until consumed
class StreamBatch:
    fed: bool = False
    consumed: bool = False
    payload: Payload = None


StreamQueue = asyncio.Queue[tuple[Iterable[aiobus.Bus[StreamBatch]], StreamBatch]]


class ReactionMismatchError(Exception):
    """
    Signals that this reaction or group does not recognize the request.

    Depending on the caller type, it either skips to the next reaction or
    returns a default response.

    In either case, this error must be suppressed: it remains the internal
    signalling mechanism of the framework only and is not visible to users.
    """
    pass


class StreamingError(Exception):
    """
    An internal(!) wrapper for errors in streaming if the response is prepared.
    """


@attrs.frozen(kw_only=True, eq=False)
class Request:
    """
    An incoming request with pre-parsed HTTP- & Kubernetes-specific intentions.

    The request can be compared/asserted against a wide range of simpler types
    if they are understood by :class:`kmock.Criteria` and descendants::

        assert kmock.gets[0] == b'{}'  # bytes are request bodies
        assert kmock.gets[0] == {'status': {}}  # dicts do partial nested json matching
        assert kmock.gets[0] == '/api/v1'  # strings starting with slash are full paths
        assert kmock.gets[0] == re.compile(r'/api/v1.*')  # regexps are paths
        assert kmock.gets[0] == 'get'  # known HTTP methods are directly supported
        assert kmock.gets[0] == 'list'  # known Kubernetes actions are directly supported
        assert kmock.gets[0] == kmock.method.POST  # so as enums
        assert kmock.gets[0] == kmock.action.WATCH  # so as enums
        assert kmock.gets[0] == kmock.resource('', 'v1', 'pods')  # Kubernetes specific resources
        assert kmock.gets[0] == kmock.resource(group='kopf.dev')  # Kubernetes partial resources
        assert kmock.gets[0] == 'ns'  # BEWARE: strings are namespaces, not the requested content

    If implicit comparision is not sufficient, specific fields can be used.
    It is more verbose and wordy but very precise.

    .. note::
        ``int`` is not supported for HTTP statuses: requests have no statuses,
        those are in responses. We do not assert on responses since the user
        typically defines the responses manually.
    """

    id: int = 0  # starts with 0, increments in the handler context

    # Raw HTTP-specifics. We hide the low-level API client, so we have to keep these explicitly.
    # NB: no dict-boxes here! These are factual http data, not the smartly parsed handmade patterns.
    method: enums.method = attrs.field(default=None, converter=enums.method)
    url: yarl.URL = attrs.field(default=yarl.URL(''), converter=yarl.URL)
    params: Mapping[str, str] = attrs.field(factory=dict)
    headers: Mapping[str, str] = attrs.field(factory=dict)
    cookies: Mapping[str, str] = attrs.field(factory=dict)
    body: bytes = b''
    text: str = ''
    data: Any = None

    # Parsed K8s-specifics (even if it was defined as a raw pattern or was not registered at all).
    action: enums.action | None = None
    resource: resources.resource | None = None
    namespace: str | None = None  # None means cluster-wide (for requests)
    # TODO: for specific requests, namespace is not a pattern, so None means cluster wide.
    #       -> make .clusterwide a property for assertions only (=self.namespace is None)
    clusterwide: bool | None = None
    name: str | None = None
    subresource: str | None = None

    # None only in tests or other artificial setups.
    # Neither the type nor the protocol are guaranteed, use at your own risk.
    _raw_request: aiohttp.web.BaseRequest | None = attrs.field(default=None, repr=False)

    # Impl note 1: Despite having only one consumer, asyncio.Queue is a bad fit: it wastes memory
    #   on items even when not streamed; and it yields items from before the start of the stream.
    #   The complexity of proper queue flushing on Ellipsis occurrences with nested sub-streams or
    #   nested callbacks grows to the same of the Bus, which flushes at item injection instead.
    # Impl note 2: Despite not being a semantic property of requests per se, the bus here simplifies
    #   the rendering. Otherwise, we have to have a dict{request->bus} in e.g. Root/Handler and pass
    #   it to every response. But we already pass the Request — so why not pass its own bus with it?
    _stream_bus: aiobus.Bus[StreamBatch] = attrs.field(factory=aiobus.Bus, repr=False, init=False)

    @classmethod
    async def _parse(cls, raw_request: aiohttp.web.BaseRequest, *, id: int = 0) -> Self:

        # Normalize the HTTP specifics as much as possible.
        # Ensure the full request payload is fetched & buffered before the connection is closed.
        # We will need the requests later in the tests for assertions/filtering.
        body = await raw_request.read()
        text = await raw_request.text()

        try:
            data = await raw_request.json()
        except ValueError:  # usually json.JSONDecodeError, but might depend on the module
            try:
                # It is an empty dict for wrong content-types instead of an error, hence "or None".
                data = await raw_request.post() or None
            except ValueError:
                data = None

        # Translate the HTTP request into the K8s request as much as possible.
        k8s = parsing.parse_path(raw_request.path)
        resource = None if k8s is None or k8s.group is None else resources.resource(
            group=k8s.group, version=k8s.version, plural=k8s.plural)
        method = enums.method(raw_request.method)  # even if unknown
        action = parsing.guess_k8s(k8s, method, dict(raw_request.query))
        request = cls(
            id=id, raw_request=raw_request,
            url=raw_request.url,
            method=raw_request.method,
            params=dict(raw_request.query),
            headers=dict(raw_request.headers),
            cookies=dict(raw_request.cookies),
            data=data, body=body, text=text,
            action=action, resource=resource, namespace=k8s.namespace,
            name=k8s.name, subresource=k8s.subresource,
            clusterwide=None if k8s is None or k8s.group is None else bool(k8s.namespace is None),
        )
        return request

    def __hash__(self) -> int:
        return id(self)


@attrs.frozen(kw_only=True)
class Response:
    """
    A pre-assembled response to be sent as a rection to matching requests.

    Typicaly constructed from consecutive ``view << response_item`` calls.
    The containing DSL view that contains a response is :class:`Reaction`.

    Chained feeding (``view << item1 << item2``) either combines the metadata
    (if distinguishable: status, headers, etc.), or creates a stream (if not).
    """

    status: int | None = None
    reason: str | None = None
    payload: Payload | None = None
    cookies: Mapping[str, str | None] | None = None
    headers: Mapping[str, str | None] | None = None

    async def __call__(self, request: Request) -> aiohttp.web.StreamResponse:
        try:
            response: aiohttp.web.StreamResponse = await self._render(request, self.payload)
        except (StopIteration, StopAsyncIteration):  # can come from next()/anext() callables
            raise ReactionMismatchError

        # The response-related fields (status) are applied anyway, headers are merged.
        if not response.prepared:
            self.__apply_metadata(response)

        return response

    async def _render(self, request: Request, payload: Payload) -> aiohttp.web.StreamResponse:
        result: Payload
        match payload:
            # No content means that the reaction is a catcher: record the request but continue matching.
            # This includes callables/awaitables that return no content (i.e. no lazy content too).
            case None if self.status is None:
                raise ReactionMismatchError
            case None:
                return aiohttp.web.Response()
            case Response():
                object.__setattr__(self, 'status', payload.status)
                object.__setattr__(self, 'reason', payload.reason)
                object.__setattr__(self, 'headers', dict(self.headers or {}, **(payload.headers or {})))
                object.__setattr__(self, 'cookies', dict(self.cookies or {}, **(payload.cookies or {})))
                return await self._render(request, payload.payload)

            # We hold the side effects in the content field to keep the response items ordered,
            # but effects live their own life with their own type interpretation.
            case SinkBox():
                await self._effect(request, payload._item)
                return await self._render(request, None)  # NB: .status affects the response or skipping

            # Some syntax sugar is reserved for future interpretation, prevent their usage now.
            case set() | frozenset() | collections.abc.Set():
                raise ValueError("Sets are reserved and are not served.")

            # Exceptions are raised in-place. It must go before the callable check.
            case NotImplementedType():
                raise ReactionMismatchError
            case type() if issubclass(payload, StopIteration):
                # Python prohibits synchronous StopIteration from coroutines, so we convert it here.
                raise StopAsyncIteration
            case StopIteration():
                # Python prohibits synchronous StopIteration from coroutines, so we convert it here.
                raise StopAsyncIteration(*payload.args) from payload
            case BaseException():
                raise payload
            case type() if issubclass(payload, BaseException):
                raise payload

            # Binaries go to the response as is, uninterpreted.
            case bytes():
                return aiohttp.web.Response(body=payload)
            case pathlib.Path():
                return aiohttp.web.Response(body=payload.read_bytes())
            case io.RawIOBase() | io.BufferedIOBase() | io.TextIOBase():
                return aiohttp.web.Response(body=payload.read())

            # Lazy content is unfolded into real content at request time, not at definition time.
            # Beware: callables and awaitables can raise here, i.e. without further recursion.
            # Beware: futures are iterable (for some weird reason), they must go first.
            case collections.abc.Awaitable():  # coroutines, futures, tasks
                result = await payload
                return await self._render(request, result)
            case _ if callable(payload):  # sync & async callbacks, lambdas, partials
                has_params = inspect.signature(payload).parameters
                result = cast(Payload, payload(request) if has_params else payload())  # type: ignore[call-arg]
                return await self._render(request, result)

            # Tuples, generators, and other iterables (except lists & sets) go as streams.
            case collections.abc.Iterable() | collections.abc.AsyncIterable() if not isinstance(payload, (str, list, collections.abc.Mapping, collections.abc.Set)):
                assert request._raw_request is not None  # for type checkers: it is None only in some tests.
                raw_response = aiohttp.web.StreamResponse()
                self.__apply_metadata(raw_response)
                try:
                    # Postpone the HTTP/TCP initial traffic until the very first real(!) chunk arrives.
                    # With this, the renderer can do invisible side effects or e.g. raise StopIteration
                    # to skip serving the request and pass it to the next renderers in line/priority.
                    # possibly with other status/headers or even to non-streams (e.g. 404/410/JSON).
                    # If the stream is prepared before chunk-yielding, there is no way back except as
                    # to reuse the pre-initialized response with maybe wrong status/headers.
                    stream = aiter(self._stream(request, payload))
                    chunk = await anext(stream)
                    try:
                        await raw_response.prepare(request._raw_request)
                        await raw_response.write(chunk)
                        async for chunk in stream:
                            await raw_response.write(chunk)
                        await raw_response.write_eof()
                    # I don't know how to simulate this. See test_blocking_without_feeding().
                    except ConnectionError:  # pragma: no cover
                        pass  # the client sometimes disconnects earlier, ignore it
                    return raw_response

                # This stream is depleted, try the next pattern (maybe not a stream). Comes from anext()
                except StopAsyncIteration:
                    raise ReactionMismatchError
                except Exception as e:
                    raise StreamingError(raw_response) from e

            # Standalone ellipsis (not wrapped into a tuple) can become a stream or a simple payload.
            # It depends on the actual value fed into the corresponding live view, i.e. kmock[...].
            case EllipsisType():
                batch: StreamBatch = await request._stream_bus.get()
                batch.consumed = True
                return await self._render(request, batch.payload)

            # Everything that syntactically looks like JSON, goes as JSON: [], {}, strs, ints, floats…
            # Mind that strings go quoted, not as the raw payload (use bytes for that).
            # Note it is confirmed payload; positional ints are classified as status at earlier stages.
            case int() | float() | bool() | str() | list() | dict() | collections.abc.Mapping():
                return aiohttp.web.json_response(payload)

            case _:
                raise ValueError(f"Unsupported payload type: {type(payload)}")

    async def _stream(self, request: Request, item: Payload) -> AsyncIterable[bytes]:
        """
        Render a streamed item into chunks of bytes to send in the response.

        One content item can produce 0…♾️ chunks, e.g. if it is a callback.
        All such chunks are sent on their own without concatenation.
        """
        result: Payload
        match item:
            # Nones usually come as a result of callables/awaitables with other useful side effects.
            case None:
                pass

            # We hold the side effects in the content field to keep the response items ordered,
            # but effects live their own life with their own type interpretation.
            case SinkBox():
                await self._effect(request, item._item)

            # Exceptions are raised in-place. It must go before the callable check.
            case BaseException():
                raise item
            case type() if issubclass(item, BaseException):
                raise item

            # Binaries go to the stream as is, uninterpreted.
            case bytes():
                yield item
            case pathlib.Path():
                yield item.read_bytes()
            case io.TextIOBase():
                yield item.read().encode('utf-8')
            case io.RawIOBase() | io.BufferedIOBase():
                yield item.read()

            # Lazy content is unfolded into real content at request time, not at definition time.
            # Beware: callables and awaitables can raise here, i.e. without further recursion.
            # Beware: futures are iterable (for some weird reason), they must go first.
            case collections.abc.Awaitable():  # coros, futures, tasks
                result = await item
                async for chunk in self._stream(request, result):
                    yield chunk
            case _ if callable(item):  # sync & async callbacks, lambdas, partials
                has_params = inspect.signature(item).parameters
                result = cast(Payload, item(request) if has_params else item())  # type: ignore[call-arg]
                async for chunk in self._stream(request, result):
                    yield chunk

            # Everything that visually looks like JSON, goes as JSON: [], {}, strs, ints, floats…
            # Mind that strings go quoted, not as the raw payload (used bytes for that).
            case int() | float() | bool() | str() | list() | dict():
                yield json.dumps(item).encode('utf-8') + b'\n'

            # Tuples, generators, and other iterables are sub-streams.
            case set() | frozenset() | collections.abc.Set():
                raise ValueError("Sets are reserved and are not served.")
            case collections.abc.Iterable():
                for subitem in item:
                    # FIXME: no branch coverage — maybe a bug in `coverage`?
                    #   It shows that the inner cycle never exits to the outer cycle,
                    #   while the manual debug shows that it does exit.
                    #   See: test_live_streams.py::test_json_encoding()
                    async for chunk in self._stream(request, subitem):  # pragma: no branch
                        yield chunk
            case collections.abc.AsyncIterable():
                # Escalate StopAsyncIteration if the source is depleted, to match the next reaction.
                # yield await anext(item)
                async for subitem in item:
                    async for chunk in self._stream(request, subitem):
                        yield chunk

            # Live streams stream live, with tail optimization & some extra item interpretation.
            case EllipsisType():
                async for subitem in self.__optimize_tail(request._stream_bus):
                    async for chunk in self._stream(request, subitem):
                        yield chunk
            case _:
                raise ValueError(f"Unsupported streaming type: {type(item)}")

    async def __optimize_tail(self, bus: aiobus.Bus[StreamBatch]) -> AsyncIterator[Payload]:
        """
        Unfold from a bus into a flat stream & optimize the tail recursion.

        For live streams, only one batch of items is processed at a time.
        The live stream either ends or continues if a new ellipsis was added.
        Stream tails (items after the ellipsis) remain on hold for later,
        i.e. when a new batch is injected with no ellipsis in it.

        Tail optimization means that recursion is avoided when not needed,
        and it runs in a simple same-level for/while cycle.
        Stateful cases with tail items —(a,...,b)— are recursed as the only way.
        Deterministic cases —(a,b,...) or (a,(b,(...,)))— are tail-optimized.
        Lazy-eval cases —(a,b,lambda:...)— cannot be optimized due to ambiguity,
        but this can be revised in the future if a good algorithm is found.
        """
        tail_ellipsis = True
        while tail_ellipsis:
            batch: StreamBatch = await bus.get()
            batch.consumed = True
            flat_payloads = self.__unfold(batch.payload)
            tail_ellipsis = bool(flat_payloads and flat_payloads[-1] is Ellipsis)
            for payload in flat_payloads[:-1] if tail_ellipsis else flat_payloads:
                yield payload

    def __unfold(self, item: Payload) -> Sequence[Payload]:
        """
        Flatten the batch of nested tuples (but not of lists or iterables!).

        Callables & awaitables & other lazy-evaluated items are not resolved
        to avoid premature or out-of-order side-effects. Tuples and only tuples!

        It is NOT exposed to users and is used only for better tail optimization
        to cover all deterministic cases instead of only top-level Ellipsis.
        """
        flat_batch: list[Payload] = []
        if isinstance(item, tuple):  # and tuples only! not lists, not iterables!
            for subitem in item:
                flat_batch.extend(self.__unfold(subitem))
        else:
            flat_batch.append(item)
        return tuple(flat_batch)

    async def _effect(self, request: Request, sink: Sink) -> None:
        from kmock._internal import dsl  # otherwise causes circular imports

        result: Sink
        match sink:
            case None:
                pass

            # A special case when the callables are used to inject the new data into the [...]
            # continued streams during the processing of an incoming request (reactive behaviour):
            #   e.g., `kmock['/trigger'] << (lambda: kmock['/stream'][...] << b'hello'`)
            #   See examples: test_cross_entangled_madness().
            # Other specific types can be listed as no-op here, but not the generic catch-all cases.
            case dsl.Stream():
                pass

            # TODO: write the whole request with verb + headers?
            case pathlib.Path():
                sink.write_bytes(request.body)
            case io.TextIOBase():
                sink.write(request.text)
            case io.RawIOBase() | io.BufferedIOBase():
                sink.write(request.body)

            # Synchronization primitives are also supported.
            case aiobus.Bus():
                await sink.put(request)
            case asyncio.Event():
                sink.set()
            case asyncio.Queue():
                await sink.put(request)
            case queue.Queue():
                sink.put(request)  # beware: it can block the whole event loop
            case asyncio.Condition():
                async with sink:
                    sink.notify_all()
            case asyncio.Future() if not isinstance(sink, asyncio.Task):
                sink.set_result(request)
            case concurrent.futures.Future():
                sink.set_result(request)
            case threading.Event():
                sink.set()  # beware: it can block the whole event loop
            case threading.Condition():
                with sink:  # beware: it can block the whole event loop
                    sink.notify_all()

            # Raw mutable containers accumulate requests. E.g.: kmock>>(reqs:=[])
            case collections.abc.MutableSet():
                sink.add(request)
            case collections.abc.MutableSequence():
                sink.append(request)
            case collections.abc.MutableMapping():
                sink[request] = request.data or request.body or None

            # Generators (but not simple iterators/iterables) get the requests from their `yield`.
            # The yield is interpreted as if it were an effect, or ignored if not recognized.
            case collections.abc.Generator():
                if inspect.getgeneratorstate(sink) == inspect.GEN_CREATED:
                    try:
                        next(sink)  # jump to the first `yield`
                    except StopIteration:
                        pass  # instantly exited? ignore!
                if inspect.getgeneratorstate(sink) == inspect.GEN_SUSPENDED:
                    try:
                        sink.send(request)
                    except StopIteration:
                        pass  # it has finally exited on this run
            case collections.abc.AsyncGenerator():
                # TODO: Python>=3.12: switch to inspect.getasyncgenstate() & AGEN_… as for syncgens.
                #   For Python 3.10 & 3.11 (until ≈October 2027), we have to use this hacky check:
                try:
                    await sink.asend(request)
                except TypeError as e:
                    if 'just-started' in str(e):
                        try:
                            await anext(sink)  # jump to the first `yield`
                        except StopAsyncIteration:
                            pass  # instantly exited? ignore!
                        await self._effect(request, sink)
                    else:
                        raise  # not our business
                except StopAsyncIteration:
                    pass  # it has exited on this or earlier run

            # Lazy content is unfolded into real content at request time, not at definition time.
            # Beware: callables and awaitables can raise here, i.e. without further recursion.
            # Beware: futures are iterable (for some weird reason), they must go first.
            case collections.abc.Awaitable():  # coroutines, futures, tasks
                result = cast(Sink, await sink)
                await self._effect(request, result)
            case _ if callable(sink):  # sync & async callbacks, lambdas, partials
                has_params = inspect.signature(sink).parameters
                result = cast(Sink, sink(request) if has_params else sink())  # type: ignore[call-arg]
                await self._effect(request, result)

            case _:
                raise ValueError(f"Unsupported side-effect type: {type(sink)}")

    @classmethod
    def guess(cls, arg: Payload | PayloadBox) -> Self:
        match arg:
            case None:
                return cls()
            case int() if not isinstance(arg, bool) and isinstance(arg, int) and 100 <= arg < 1000:
                return cls(status=arg)

            # Unpack purpose-hinting boxes into purpose-specific classes & fields.
            case boxes.body():
                return cls(payload=arg.body)
            case boxes.text():
                return cls(payload=arg.text)
            case boxes.data():
                return cls(payload=arg.data)
            case boxes.headers():
                return cls(headers=dict(arg))
            case boxes.cookies():
                return cls(cookies=dict(arg))

            case collections.abc.Mapping() if parsing.are_all_known_headers(arg) and not isinstance(arg, aiohttp.web.StreamResponse):
                return cls(headers=arg)
            case set() | frozenset() | collections.abc.Set() | boxes.params() | boxes.path():
                raise ValueError(f"Unsupported payload type: {type(arg)}")
            case type() if issubclass(arg, BaseException):
                return cls(payload=arg)
            case Response() | SinkBox():
                return cls(payload=arg)
            case _:
                payload: Payload = cast(Payload, arg)  # logically, nothing else is possible
                cls.__verify_payload(payload)
                return cls(payload=payload)

    @classmethod
    def __verify_payload(cls, payload: Payload) -> None:
        match payload:
            case None:
                pass
            case aiohttp.web.StreamResponse():
                raise ValueError(f"Unsupported payload type: {type(payload)}")
            case set() | frozenset() | collections.abc.Set():  # reserved for future
                raise ValueError(f"Unsupported payload type: {type(payload)}")
            case type() if issubclass(payload, BaseException):
                pass
            case tuple():  # safe introspection of simple streams without depletion
                for item in payload:
                    cls.__verify_payload(item)
            case _ if isinstance(payload, SUPPORTED_PAYLOADS) or callable(payload):
                pass
            case _:
                raise ValueError(f"Unsupported payload type: {type(payload)}")

    def __add__(self, other: "Response") -> "Response":
        """
        Combine 2 responses into one.

        Metadata (status, headers, cookies, etc) from both sides is combined.
        If they have conflicting metadata values, an error is raised.
        Payloads (the response bodies) from both sides are packed to a stream.
        """
        if not isinstance(other, Response):
            return NotImplemented

        if self.status is not None and other.status is not None:
            warnings.warn(f"Ambiguous statuses: {self.status!r} vs. {other.status!r}", UserWarning)
        status = other.status if other.status is not None else self.status

        if self.reason is not None and other.reason is not None:
            warnings.warn(f"Ambiguous reasons: {self.reason!r} vs. {other.reason!r}", UserWarning)
        reason = other.reason if other.reason is not None else self.reason

        a_headers = {key: val for key, val in (self.headers or {}).items()}
        b_headers = {key: val for key, val in (other.headers or {}).items()}
        conflicting_keys = sorted(set(a_headers) & set(b_headers))
        if conflicting_keys:
            warnings.warn(f"Ambiguous headers: {conflicting_keys!r}", UserWarning)
        headers = dict(a_headers, **b_headers)

        a_cookies = {key: val for key, val in (self.cookies or {}).items()}
        b_cookies = {key: val for key, val in (other.cookies or {}).items()}
        conflicting_keys = sorted(set(a_cookies) & set(b_cookies))
        if conflicting_keys:
            warnings.warn(f"Ambiguous cookies: {conflicting_keys!r}", UserWarning)
        cookies = dict(a_cookies, **b_cookies)

        match self.payload, other.payload:
            case None, _:
                payload = other.payload
            case _, None:
                payload = self.payload

            # Fail on conceptually conflicting contents: e.g., 2 full responses cannot be joined.
            # NB: the earlier checks catch the Nones; here, the counterparty is certainly not None.
            case aiohttp.web.StreamResponse(), _:
                warnings.warn(f"Ambiguous content: {self.payload!r} vs. {other.payload!r}", UserWarning)
                payload = other.payload
            case _, aiohttp.web.StreamResponse():
                warnings.warn(f"Ambiguous content: {self.payload!r} vs. {other.payload!r}", UserWarning)
                payload = other.payload

            # Optimize: combine immutable repeatable streams into a flat stream, for simplicity.
            case tuple(), tuple():
                payload = self.payload + other.payload
            case tuple(), _:
                payload = self.payload + (other.payload,)
            case _, tuple():
                payload = (self.payload,) + other.payload
            case _:
                payload = (self.payload, other.payload)

        return attrs.evolve(
            self,
            status=status, reason=reason,
            cookies=cookies, headers=headers,
            payload=payload,
        )

    def __apply_metadata(self, raw_response: aiohttp.web.StreamResponse) -> None:
        """
        Transfer the metadata (status, headers, etc) into a raw response.
        """
        if self.status is not None:
            raw_response.set_status(self.status, self.reason)
        for header_name, header_val in (self.headers or {}).items():
            if header_val is not None:
                raw_response.headers[header_name] = header_val
        for cookie_name, cookie_val in (self.cookies or {}).items():
            if cookie_val is not None:
                raw_response.set_cookie(cookie_name, cookie_val)
            else:
                raw_response.del_cookie(cookie_name)
