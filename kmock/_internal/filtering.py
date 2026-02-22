import abc
import asyncio
import collections.abc
import concurrent.futures
import enum
import fnmatch
import inspect
import re
import threading
from collections.abc import Callable, Mapping
from types import EllipsisType
from typing import Any, Protocol, TypeAlias, TypeVar, Union, runtime_checkable

import aiohttp.web
import attrs
from typing_extensions import Self

from kmock._internal import boxes, enums, parsing, rendering, resources

T = TypeVar('T')
V = TypeVar('V')


# TODO: Redesign? We use `...` (Ellipsis) in dicts to match any value.
#       Why don't we use it in fields, too? Do so!
# class _AnyT(enum.Enum):
#     """
#     A sentinel for "any" value, i.e. the aspect is ignored in filtering.
#
#     It is not exposed to the users and should not be used by the users.
#     If the users want "any" value to pass, they simply do not set the criterion.
#
#     The common alternative and temptation is to use ``None`` for this purpose,
#     but it breaks the semantics and readability in most cases:
#
#     - ``kmock.subresource(None)`` reads as "no subresource", meaning only
#       the main object requests, not "any subresource", including the real ones.
#     - ``kmock.namespace(None)`` reads as cluster-wide requests with strictly
#       absent namespace, not "any namespace", both absent and real ones.
#     - so on…
#     """
#     ANY = object()


@runtime_checkable
class SupportsBool(Protocol):
    def __bool__(self) -> bool:
        ...


CriterionFn = (
        Callable[[], "Criterion"] |
        Callable[[rendering.Request], "Criterion"]
)

# Anything that can be used as a single anonymous criterion in view filtering:
#   kmock[criterion1][criterion2, criterion3][{criterion4, criterion5}]
# It is then analyzed, parsed, and converted to specialized named criteria.
Criterion: TypeAlias = (
    None |
    str |  # mixed methods, actions, paths, namespaces
    bool |
    bytes |
    SupportsBool |
    re.Pattern[str] |
    re.Pattern[bytes] |
    enums.action |
    enums.method |
    resources.resource |
    resources.Selectable |
    Mapping[str, "Criterion"] |
    set["Criterion"] |  # or-groups
    frozenset["Criterion"] |  # or-groups
    tuple["Criterion", ...] |  # and-groups

    # Events are true if they are set.
    asyncio.Event |
    threading.Event |

    # Futures are true if they are set AND the result is true.
    asyncio.Future["Criterion"] |
    concurrent.futures.Future["Criterion"] |

    # Arbitrary callables can be used too. NB: strict bool-supporting classes! To avoid support for
    # e.g. generators and other unexpected objects as filters (which are "true" by mere existence).
    Callable[[], bool] |
    Callable[[], SupportsBool] |
    Callable[[rendering.Request], bool] |
    Callable[[rendering.Request], SupportsBool]
)
CriterionBox = (
    boxes.data |
    boxes.text[re.Pattern[str]] |
    boxes.body[re.Pattern[bytes]] |
    boxes.params[re.Pattern[str]] |
    boxes.headers[re.Pattern[str]] |
    boxes.cookies[re.Pattern[str]]
)

TRUE_STRINGS = re.compile(r'^true|yes|on|t|y|1$', re.I)
FALSE_STRINGS = re.compile(r'^false|no|off|f|n|0$', re.I)


@attrs.frozen
class Criteria:
    """A standalone container for specialized named criteria."""

    @abc.abstractmethod
    def __call__(self, request: rendering.Request) -> bool:
        raise NotImplementedError

    def _check(self, pat: Criterion, val: Any, *, glob: bool = False) -> bool:
        match pat, val:
            # No criteria means matching everything.
            case EllipsisType(), _:
                return True

            # Special types & wrappers check for themselves.
            case resources.resource(), _:
                return val is not None and (isinstance(val, resources.Selectable) and pat.check(val))

            # Enums from either side match both names & values case-insensitively.
            case enum.Enum(), _:
                if pat == val:  # quick-check if we are lucky
                    return True
                if self._check(re.compile(re.escape(pat.name), re.I), val):
                    return True
                if isinstance(pat.value, int):
                    return self._check(pat.value, val, glob=glob)
                if isinstance(pat.value, str) and isinstance(val, str):
                    return self._check(re.compile(re.escape(pat.value), re.I), val, glob=glob)
                if isinstance(pat.value, bytes) and isinstance(val, bytes):
                    return self._check(re.compile(re.escape(pat.value), re.I), val, glob=glob)
                return False
            case int(), enum.Enum():
                return self._check(pat, val.value)
            case str(), enum.Enum():
                if self._check(re.compile(re.escape(pat), re.I), val.name):
                    return True
                if isinstance(val.value, (int, str, bytes)):
                    return self._check(re.compile(re.escape(pat), re.I), val.value, glob=glob)
                return False
            case bytes(), enum.Enum():
                if self._check(re.compile(re.escape(pat), re.I), val.name):
                    return True
                if isinstance(val.value, (int, str, bytes)):
                    return self._check(re.compile(re.escape(pat), re.I), val.value, glob=glob)
                return False
            case re.Pattern(), enum.Enum():
                if self._check(pat, val.name):
                    return True
                if isinstance(val.value, (int, str, bytes)):
                    return self._check(pat, val.value, glob=glob)
                return False

            # Regexps accept any form of scalars.
            # Caveat: re.Patterns are tricky for MyPy: we mix `str|bytes`, but they require AnyStr
            # with str & bytes separated and never mixed up. We ensure this with the runtime logic.
            # Hence we suppress MyPy and rely on the runtime to never mix up the types.
            case re.Pattern(), int():
                return self._check(pat, str(val), glob=glob)
            case re.Pattern(), str() | bytes():
                try:
                    return pat.fullmatch(val) is not None  # type: ignore[arg-type]
                except TypeError:
                    # TypeError: can't use a string pattern on a bytes-like object
                    if isinstance(val, bytes):
                        return self._check(pat, val.decode(), glob=glob)
                    # TypeError: can't use a bytes pattern on a string-like object
                    if isinstance(val, str):
                        return self._check(pat, val.encode(), glob=glob)
                    raise  # pragma: no cover  # impossible (no other pattern types)
            case re.Pattern(), _:
                return False

            # JSON-like syntax (dicts, lists) mean matching the value, but elements can be any patterns.
            # This also covers our shortcuts: headers(), cookies(), params(), etc.
            # E.g.: {'query': re.compile('true', re.I)}
            case collections.abc.Mapping(), collections.abc.Mapping():
                return all(key in val and self._check(pat[key], val[key], glob=glob) for key in pat)
            case collections.abc.Mapping(), _:
                return False  # we wanted a dict, got something else

            # Strings & bytes are interchangeable with implicit encoding, including regexp patterns.
            case str() | bytes(), _ if glob:
                return val is not None and fnmatch.fnmatchcase(val, pat)
            case str(), bytes():
                return pat == val.decode()
            case str(), str() | int():
                return pat == str(val)
            case bytes(), str():
                return pat == val.encode()
            case bytes(), int():
                return pat == str(val).encode()
            case bytes(), bytes():
                return pat == val

            # Booleans match some predefined strings/bytes (JSON-style).
            # NB: pattern=False does NOT match value=None! If False is expected, it MUST be False/0.
            case bool(), None:
                return False
            case bool(), str() | bytes():
                return self._check(TRUE_STRINGS if pat else FALSE_STRINGS, val, glob=glob)
            case bool(), bool() | int() | SupportsBool():
                return bool(pat) == bool(val)
            case bool(), _:
                return False

            # Integers are shortcuts for same-value strings; e.g.: {'page': 5} == {'page': '5'}.
            case int(), str() | bytes():
                return self._check(str(pat), val, glob=glob)

            # Avoid materializing ephemeral collections. E.g. {'page': range(5, 9999)}.
            case range(), int():
                return val in pat
            case range(), str():
                try:
                    return int(val) in pat
                except ValueError:
                    return False
            case range(), bytes():
                try:
                    return int(val.decode()) in pat
                except ValueError:
                    return False

            # Unordered collections mean any value in it. E.g. {'watch': {'true', 'yes', '1'}}.
            case set() | frozenset(), collections.abc.Hashable() if val in pat:  # quick-check
                return True
            case set() | frozenset(), _:
                return any(self._check(sub_pat, val, glob=glob) for sub_pat in pat)

            # Compare everything else by equality — the "best effort" approach without any smart logic.
            case _:
                return bool(pat == val)

    # TODO: Rewrite Union[X,Y] to X|Y when Python 3.10 is dropped (≈October 2026).
    #   Fails on Unions + ForwardRefs: https://github.com/python/cpython/issues/90015
    @staticmethod
    def guess(arg: Union["Criteria", Criterion, CriterionBox], /) -> Union["Criteria", None]:
        match arg:
            case None:
                return None
            case aiohttp.web.StreamResponse():  # a mapping for some reason
                raise ValueError(f"Unrecognized criterion type: {type(arg)}")

            # Preparsed or explicitly defined criteria go as is. Mostly for non-boxed shortcuts below.
            case Criteria():
                return arg

            # Unpack purpose-hinting enums & boxes into purpose-specific classes & fields.
            case enums.method():
                return HTTPCriteria(method=arg)
            case enums.action():
                return K8sCriteria(action=arg)
            case boxes.body():
                return HTTPCriteria(body=arg.body)
            case boxes.text():
                return HTTPCriteria(text=arg.text)
            case boxes.data():
                return HTTPCriteria(data=arg.data)
            case boxes.path():
                return HTTPCriteria(path=arg.path)
            case boxes.params():
                return HTTPCriteria(params=dict(arg))
            case boxes.headers():
                return HTTPCriteria(headers=dict(arg))
            case boxes.cookies():
                return HTTPCriteria(cookies=dict(arg))
            case resources.resource():
                return K8sCriteria(resource=arg)
            case resources.Selectable():
                return K8sCriteria(resource=resources.resource(arg))

            # Generic Python types are either parsed & recognized, or go to multi-field criteria.
            case re.Pattern() if isinstance(arg.pattern, str):
                return HTTPCriteria(path=arg)
            case bytes():
                return HTTPCriteria(body=arg)
            case str():
                # NB: http methods over k8s actions: mostly for the ambiguous "delete" verb.
                if not arg:
                    return None
                elif (maybe_http := parsing.ParsedHTTP.parse(arg)) is not None:
                    # Reminder: Ellipsis means "any value", None means explicitly "no value".
                    return HTTPCriteria(
                        method=maybe_http.method if maybe_http.method is not None else ...,
                        path=maybe_http.path if maybe_http.path is not None else ...,
                        params=maybe_http.params if maybe_http.params is not None else ...,
                    )
                elif (maybe_k8s := parsing.ParsedK8s.parse(arg)) is not None and (maybe_k8s.method or maybe_k8s.action):
                    # Reminder: Ellipsis means "any value", None means explicitly "no value".
                    # TODO: does the parser return ... or Nones? (it makes sense to return None when not parsed)
                    return K8sCriteria(
                        method=maybe_k8s.method if maybe_k8s.method is not None else ...,
                        action=maybe_k8s.action if maybe_k8s.action is not None else ...,
                        resource=maybe_k8s.resource if maybe_k8s.resource is not None else ...,
                    )
                else:
                    return StrCriteria(arg)
            case collections.abc.Mapping():
                return DictCriteria(arg) if arg else None
            case collections.abc.Callable():
                return FnCriteria(arg)
            case asyncio.Event() | threading.Event():
                return EventCriteria(arg)
            case asyncio.Future() | concurrent.futures.Future():
                return FutureCriteria(arg)
            case bool() | SupportsBool():
                return BoolCriteria(arg)
            case _:
                raise ValueError(f"Unrecognized criterion type: {type(arg)}")


@attrs.frozen(kw_only=True, repr=False)
class OptiCriteria(Criteria):
    """
    A base for multi-field criteria with squashing/optimizing and simpler repr.
    """

    def __repr__(self) -> str:
        # For brevity, only non-default field values in repr (why is it not a feature of attrs yet?)
        cls = type(self)
        vals = {
            field.alias or field.name: getattr(self, field.name)
            for field in attrs.fields(type(self))
            if field.repr and field.init
            if not field.name.startswith('_')
            # if callable(field.default) or getattr(self, field.name) != field.default
            if getattr(self, field.name) != field.default and getattr(self, field.name) is not None and getattr(self, field.name) != {}
        }
        text = ', '.join(f"{key!s}={val!r}" for key, val in vals.items())
        return f"{cls.__name__}({text})"

    def __add__(self, other: Self) -> Self:
        # Only criteria with STRICTLY the same fields can be optimized, no descendant classes.
        if type(other) is not type(self):
            return NotImplemented
        kwargs: dict[str, Any] = {}
        for field in attrs.fields(type(self)):
            a = getattr(self, field.name)
            b = getattr(other, field.name)
            kwargs[field.name] = self._combine([field.name], a, b)
        return type(self)(**kwargs)

    def _combine(self, path: list[str], a: Any, b: Any) -> Any:
        if isinstance(a, dict) and isinstance(b, dict):
            return self._combine_dicts(path, a, b)
        elif a is not ... and b is not ... and a != b:
            keys_str = ''.join(f"[{key!r}]" for key in path[1:])
            path_str = f"{path[0]}{keys_str}"
            raise ValueError(f"Ambiguous values of {path_str}: {a!r} vs. {b!r}")
        else:
            return b if b is not ... else a if a is not ... else ...

    def _combine_dicts(self, path: list[str], a: dict[str, T], b: dict[str, T]) -> dict[str, T]:
        m: dict[str, Any] = {}
        for key in set(a) | set(b):
            if key not in a:
                m[key] = b[key]
            elif key not in b:
                m[key] = a[key]
            elif a[key] == b[key]:
                m[key] = a[key]  # b would also work
            else:
                m[key] = self._combine(path + [key], a[key], b[key])
        return m


@attrs.frozen(kw_only=True, repr=False)
class HTTPCriteria(OptiCriteria):
    """
    The generic HTTP-level criteria of the request (not involving K8s aspects).
    """

    # Reminder: Ellipsis means "any value", None means explicitly "no value".
    method: enums.method | None | EllipsisType = ...
    path: re.Pattern[str] | str | None | EllipsisType = ...
    text: re.Pattern[str] | str | None | EllipsisType = ...
    body: re.Pattern[bytes] | bytes | None | EllipsisType = ...
    data: Any | None | EllipsisType = ...
    params: dict[str, None | str | re.Pattern[str]] | None | EllipsisType = ...
    cookies: dict[str, None | str | re.Pattern[str]] | None | EllipsisType = ...
    headers: dict[str, None | str | re.Pattern[str]] | None | EllipsisType = ...

    def __call__(self, request: rendering.Request) -> bool:
        return (
            True
            # TODO: consider globs for headers/params. But if so, treat None as "must be absent".
            #       same for .data — None MUST mean it must be either JSON-null, or absent (which is equivalent in k8s)
            #       current interpretation as "any" is highly MISLEADING. Use "*" for "any"?
            and self._check(self.method, request.method)
            and self._check(self.params, request.params)  # TODO: glob=True?
            and self._check(self.headers, request.headers)  # TODO: glob=True?
            and self._check(self.cookies, request.cookies)  # TODO: glob=True?
            and self._check(self.path, request.url.path, glob=True)
            and self._check(self.text, request.text)
            and self._check(self.body, request.body)
            and self._check(self.data, request.data)
        )


@attrs.frozen(kw_only=True, repr=False)
class K8sCriteria(OptiCriteria):
    """
    The K8s-level criteria of the request, if they could be guessed/parsed.

    This is also an example of extending KMock for app-specific handling.
    """

    # Reminder: Ellipsis means "any value", None means explicitly "no value".
    method: enums.method | None | EllipsisType = ...
    action: enums.action | None | EllipsisType = ...
    resource: resources.resource | None | EllipsisType = ...
    namespace: re.Pattern[str] | str | None | EllipsisType = ...
    # TODO: get rid of clusterwide now, when we have namespace=None for this purpose (not "any").
    clusterwide: bool | None | EllipsisType = ...
    name: re.Pattern[str] | str | None | EllipsisType = ...
    subresource: re.Pattern[str] | str | None | EllipsisType = ...

    def __call__(self, request: rendering.Request) -> bool:
        return (
            True
            and self._check(self.method, request.method)
            and self._check(self.action, request.action)
            and self._check(self.resource, request.resource)
            and self._check(self.subresource, request.subresource)
            and self._check(self.clusterwide, request.clusterwide)
            and self._check(self.namespace, request.namespace, glob=True)
            and self._check(self.name, request.name, glob=True)
        )


@attrs.frozen
class FnCriteria(Criteria):
    fn: CriterionFn

    def __call__(self, request: rendering.Request) -> bool:
        # A callable can return anything: other callables, awaitables, bools, or None.
        # Treat the result as a positional non-specialised criterion (no way to specialise it).
        # Everything else can be explicitly specialised with kwargs, hence the separate fields.
        has_params = inspect.signature(self.fn).parameters
        result = self.fn(request) if has_params else self.fn()  # type: ignore[call-arg]
        criteria = Criteria.guess(result)
        return criteria(request) if criteria is not None else False


@attrs.frozen
class BoolCriteria(Criteria):
    value: bool | SupportsBool

    def __call__(self, request: rendering.Request) -> bool:
        return bool(self.value)


@attrs.frozen
class DictCriteria(Criteria):
    value: Mapping[str, Any]

    def __call__(self, request: rendering.Request) -> bool:
        return bool(
            self._check(self.value, request.headers) or
            self._check(self.value, request.cookies) or
            self._check(self.value, request.params) or
            self._check(self.value, request.data)
        )


@attrs.frozen
class StrCriteria(Criteria):
    value: str

    def __call__(self, request: rendering.Request) -> bool:
        return bool(
            self._check(self.value, request.method) or
            self._check(self.value, request.data) or
            self._check(self.value, request.text)
        )


@attrs.frozen
class EventCriteria(Criteria):
    event: asyncio.Event | threading.Event

    def __call__(self, request: rendering.Request) -> bool:
        return self.event.is_set()


@attrs.frozen
class FutureCriteria(Criteria):
    future: asyncio.Future[Criterion] | concurrent.futures.Future[Criterion]

    def __call__(self, request: rendering.Request) -> bool:
        return bool(self.future.done() and self.future.result())


# Some non-boxed shortcuts with values of specific purpose. They are not worth making them
# into separate class(es) in boxes.py, but are still needed for DSL completeness.
# TODO: Remake into classes — e.g. for kmock.objects[kmock.namespace('ns1')]
#       in addition to kmock.objects[kmock.resource('v1/pods')]
#  OR: keep those indexes positional?
def clusterwide(arg: bool = True) -> Criteria:
    return K8sCriteria(clusterwide=bool(arg))


def namespace(arg: re.Pattern[str] | str | None) -> Criteria:
    return K8sCriteria(namespace=arg)


def name(arg: re.Pattern[str] | str | None) -> Criteria:
    return K8sCriteria(name=arg)


def subresource(arg: re.Pattern[str] | str | None) -> Criteria:
    return K8sCriteria(subresource=arg)
