"""
Temporary containers for nicer DSL.

Once used in one of the roles, the containers are dismissed and their
contained values are used in the relevant structures:

* As a criterion: ``kmock[kmock.headers('Authorization: Bearer tkn')]``
* As a payload: ``kmock << kmock.headers('Content-Type: application/json')``

Not all boxes can be used in all roles: e.g., params can only be in criteria.
But for uniformity, we still generate the shortcut containers first.
"""
import collections.abc
import re
import urllib.parse
from collections.abc import Mapping
from typing import Any, Generic, Iterator, TypeVar, overload

import attrs
from typing_extensions import override

# An extra type for criteria. Use as [None] for strict containers (despite already defined),
# or as [re.Pattern[str | bytes]] for criteria in addition to strict str/bytes.
P = TypeVar('P')


@attrs.define
class path:
    path: str | re.Pattern[str] = ''


@attrs.define(init=False)
class body(Generic[P]):
    body: bytes | P = b''

    @overload
    def __init__(self, arg: None | P, /) -> None:
        ...

    @overload
    def __init__(self, *args: str | bytes) -> None:
        ...

    def __init__(self, *args: str | bytes | None | P) -> None:
        super().__init__()
        if not args or all(arg is None for arg in args):
            self.body = b''
        elif len(args) == 1 and isinstance(args[0], re.Pattern):
            self.body = args[0]
        else:
            encoded: list[bytes] = []
            for arg in args:
                match arg:
                    case None:
                        pass
                    case bytes():
                        encoded.append(arg)
                    case str():
                        encoded.append(arg.encode())
                    case _:
                        raise ValueError("Body can be either strings, bytes, or a single re.Pattern.")
            self.body = b''.join(encoded)


@attrs.define(init=False)
class text(Generic[P]):
    text: str | P = ''

    @overload
    def __init__(self, arg: None | P, /) -> None:
        ...

    @overload
    def __init__(self, *args: str | bytes) -> None:
        ...

    def __init__(self, *args: str | bytes | None | P) -> None:
        super().__init__()
        if not args or all(arg is None for arg in args):
            self.text = ''
        elif len(args) == 1 and isinstance(args[0], re.Pattern):
            self.text = args[0]
        else:
            decoded: list[str] = []
            for arg in args:
                match arg:
                    case None:
                        pass
                    case str():
                        decoded.append(arg)
                    case bytes():
                        decoded.append(arg.decode())
                    case _:
                        raise ValueError("Text can be either strings, bytes, or a single re.Pattern.")
            self.text = ''.join(decoded)


@attrs.define(init=False)
class data:
    data: Any

    @overload
    def __init__(self, arg: Any, /) -> None:
        ...

    @overload
    def __init__(self, *args: Mapping[Any, Any], **kwargs: Any) -> None:
        ...

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.data = None
        for arg in args:
            match self.data, arg:
                case _, None:
                    pass
                case None, _:
                    self.data = arg
                case collections.abc.Mapping(), collections.abc.Mapping():
                    # Hopefully, arg is a mapping or a dict-ready sequence. If not, fail.
                    self.data = dict(self.data, **dict(arg))
                case _:
                    raise ValueError(f"Unmergeable combination of multiple arguments: {args!r}")
        if kwargs:
            if self.data is None or isinstance(self.data, collections.abc.Mapping):
                self.data = dict(self.data or {}, **kwargs)
            else:
                raise ValueError("Kwargs can be passed to data only alone or for a mapping.")


class patterndict(Generic[P], collections.abc.Mapping[str, str | None | P]):
    __slots__ = '_data'
    _data: dict[str, str | None | P]

    def __init__(
            self,
            *args: None | str | bytes | Mapping[str, str | None | P],
            **kwargs: str | None | P,
    ) -> None:
        super().__init__()
        self._data = {}
        for arg in args:
            match arg:
                case None:
                    pass
                case str() | bytes():
                    value = arg.decode() if isinstance(arg, bytes) else arg
                    items = self._parse_str(value)
                    self._data.update(items)
                case collections.abc.Mapping() | collections.abc.Iterable():
                    try:
                        self._data.update(arg)
                    except ValueError:
                        raise ValueError(f"Unsupported argument for {self.__class__.__name__}: {arg!r}")
                case _:
                    raise ValueError(f"Unsupported argument for {self.__class__.__name__}: {arg!r}")
        self._data.update(kwargs)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._data!r})"

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[str]:
        yield from self._data

    def __getitem__(self, key: str) -> str | None | P:
        return self._data[key]

    def _parse_str(self, s: str, /) -> Mapping[str, str | None | P]:
        raise ValueError(f"Unsupported argument for {self.__class__.__name__}: {s!r}")


class params(Generic[P], patterndict[P]):
    __slots__ = ()

    @override
    def _parse_str(self, s: str, /) -> Mapping[str, str | None | P]:
        # Distinguish truly empty keys and no-value keys: None means any value for a present key.
        # E.g.: "?key=&…" becomes {'key': ''), but "?key&…" becomes {'key': None}
        s = s.lstrip('?')
        orphans = {v for v in s.split('&') if '=' not in v}
        values = urllib.parse.parse_qsl(s, keep_blank_values=True)
        return {key: None if not val and key in orphans else val for key, val in values}


class cookies(Generic[P], patterndict[P]):
    __slots__ = ()


class headers(Generic[P], patterndict[P]):
    __slots__ = ()

    @override
    def _parse_str(self, s: str, /) -> Mapping[str, str | None | P]:
        result: dict[str, str] = {}
        lines = [line.strip() for line in s.splitlines() if line.strip()]
        for line in lines:
            if ':' not in line:
                raise ValueError(f"Unsupported argument for {self.__class__.__name__}: {line!r}")
            name, s = line.split(':', 1)
            result[name.strip()] = s.strip()
        return result
