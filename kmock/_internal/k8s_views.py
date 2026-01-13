import collections.abc
from collections.abc import Iterable, Iterator, Mapping, MutableMapping
from typing import Any, TypeGuard, TypedDict, overload

import attrs

from kmock._internal import k8s_dicts, resources

ArrayKey = tuple[resources.resource, str | None, str]  # pre-parsed ObjectKey
ObjectKey = tuple[str | resources.resource, str | None, str]
VersionKey = tuple[str | resources.resource, str | None, str, int]
HistoryKey = tuple[str | resources.resource, str | None, str, slice]


def _is_object_key(key: ObjectKey | VersionKey | HistoryKey) -> TypeGuard[ObjectKey]:
    return len(key) == 3


def _is_version_key(key: ObjectKey | VersionKey | HistoryKey) -> TypeGuard[VersionKey]:
    return len(key) == 4 and isinstance(key[-1], int)


def _is_history_key(key: ObjectKey | VersionKey | HistoryKey) -> TypeGuard[HistoryKey]:
    return len(key) == 4 and isinstance(key[-1], slice)


ResourceKey = str | resources.Selectable | resources.resource


def _is_resource_key(key: object) -> TypeGuard[ResourceKey]:
    return isinstance(key, str | resources.Selectable | resources.resource)


def _parse_resource(key: ResourceKey) -> resources.resource:
    match key:
        case resources.resource():
            return key
        case str() | resources.Selectable():
            return resources.resource(key)
        case tuple():  # length 1 & 2 & 3
            return resources.resource(*key)
        case _:
            raise TypeError(f"Unsupported resource key: {key!r}")


class ResourceDict(TypedDict, total=True):
    # All the same keys as the attributes of ResourceInfo, but with no defaults (and thus Nones).
    namespaced: bool
    kind: str
    singular: str
    verbs: Iterable[str]
    shortnames: Iterable[str]
    categories: Iterable[str]
    subresources: Iterable[str]


@attrs.define(repr=False, kw_only=True)
class ResourceInfo:
    """
    The extended discovery information about a resource.

    The identifying fields —group, version, plural— are not part of the class,
    as they are used as the key of :class:`ResourceArray` or ``kmock.resources``
    that leads to the extended resource information.
    """
    namespaced: bool | None = None
    kind: str | None = None
    singular: str | None = None

    # NB: unordered mutable set, to be adjustable on quick access:
    #   kmock.resources['v1/pods'].categories.add('cat')
    verbs: set[str] = attrs.field(factory=set, converter=set)
    shortnames: set[str] = attrs.field(factory=set, converter=set)
    categories: set[str] = attrs.field(factory=set, converter=set)
    subresources: set[str] = attrs.field(factory=set, converter=set)

    def __repr__(self) -> str:
        kwargs: dict[str, Any] = {
            field.name: getattr(self, field.name)
            for field in attrs.fields(type(self))
        }
        kwargs = {
            key: val for key, val in kwargs.items()
            if val is not None and val != set()
        }
        texts = ', '.join(f"{key!s}={val!r}" for key, val in kwargs.items())
        return f"{type(self).__name__}({texts})"


@attrs.define(init=False, repr=False, eq=False, order=False)
class ResourcesArray(MutableMapping[ResourceKey, ResourceInfo | ResourceDict]):
    """
    An associative array of extended information about cluster resources.

    Exposed via ``kmock.resources``.

    The key is either a pre-created instance of :class:`kmock.resource`,
    or a string that can be passed to and parsed by :class:`kmock.resource`:
    e.g., ``'kopf.dev/v1/kopfexamples'``, ``'kopfexamples.v1.kopf.dev'``,
    ``'v1/pods'``, ``'pods.v1'``, and some other notations; this includes
    all objects with string properties ``.group``, ``.version``, ``.plural``.
    It is stored pre-parsed, so iterating over the array yields the parsed
    instances of :class:`kmock.resource`.

    The values are of type :class:`ResourceInfo`. They are auto-created
    on access, so the properties can be assigned without preparations::

        kmock.resources['kopf.dev/v1/kopfexamples'].kind = 'KopfExample'
        kmock.resources['v1/pods'].shortnames = {'pod', 'po'}

    The alternative is storing a new instance of :class:`ResourceInfo`::

        kmock.resources['v1/pods'] = ResourceInfo(shortnames={'pod', 'po'})

    It is used in the API discovery only and is not used for payload validation.
    As such, all the information is fully optional. If the whole record or any
    fields are absent, they are returned either empty or guessed from the plural
    name of the resource (not grammatically correct, of course, but sufficient).
    """
    _resources: dict[resources.resource, ResourceInfo] = attrs.field(factory=dict, init=False)

    def __init__(self, resources: Mapping[ResourceKey, ResourceInfo | ResourceDict] | None = None, /) -> None:
        super().__init__()

        self._resources = {}
        for key, val in (resources or {}).items():
            resource = _parse_resource(key)
            match val:
                case ResourceInfo():
                    self._resources[resource] = val
                case Mapping():
                    self._resources[resource] = ResourceInfo(**val)  # type: ignore[arg-type]
                case _:
                    raise TypeError(f"Unsupported resource value: {val!r}")

    def __repr__(self) -> str:
        subrepr = ', '.join(f'{res!r}: {info!r}' for res, info in self._resources.items())
        subrepr = f"{{{subrepr}}}" if subrepr else ""
        return f"{self.__class__.__name__}({subrepr})"

    def __bool__(self) -> bool:
        return bool(self._resources)

    def __len__(self) -> int:
        return len(self._resources)

    def __iter__(self) -> Iterator[resources.resource]:
        yield from self._resources

    def __contains__(self, key: object, /) -> bool:
        return (_parse_resource(key) if _is_resource_key(key) else key) in self._resources

    def __setitem__(self, key: ResourceKey, value: ResourceInfo | ResourceDict, /) -> None:
        res = _parse_resource(key)
        match value:
            case ResourceInfo():
                self._resources[res] = value
            case Mapping():
                self._resources[res] = ResourceInfo(**value)   # type: ignore[arg-type]
            case _:
                raise TypeError(f"Unsupported resource value: {value!r}")

    def __delitem__(self, key: ResourceKey, /) -> None:
        res = _parse_resource(key)
        del self._resources[res]

    def __getitem__(self, key: ResourceKey, /) -> ResourceInfo:
        # The behaviour as for the defaultdict - to make it possible to assign fields blindly:
        #   kmock.resources['pods.v1'].kind = 'Pod'
        res = _parse_resource(key)
        if res not in self._resources:
            self._resources[res] = ResourceInfo()
        return self._resources[res]

    def clear(self) -> None:
        self._resources.clear()


# NB: Mapping-like, but not a Mapping — there is no specific fixed-type key-val.
# The keys-vals are flexible, essentially multi-type with different types.
@attrs.frozen(eq=False, order=False)
class ObjectsArray:
    """
    An associative array of K8s objects and their past versions.

    The following notations are supported with a 3-item key::

        kmock.objects['v1/pods', 'ns', 'name']          # namespaced objects
        kmock.objects['v1/pods', None, 'name']          # cluster-wide objects

    The 4-item key is a shortcut for the ``.history`` field of the object view::

        kmock.objects['v1/pods', 'ns', 'name', 0]       # the initial version
        kmock.objects['v1/pods', 'ns', 'name', -2]      # the pre-last version
        kmock.objects['v1/pods', 'ns', 'name', -1]      # the current version
        kmock.objects['v1/pods', 'ns', 'name', 1:3]     # a slice of versions
        kmock.objects['v1/pods', 'ns', 'name', :]       # a list of all versions

    In both cases, the first item of the key is either a pre-created instance
    of :class:`kmock.resource`, or a string or an object that can be passed to
    and parsed by :class:`kmock.resource`:
    e.g., ``'kopf.dev/v1/kopfexamples'``, ``'kopfexamples.v1.kopf.dev'``,
    ``'v1/pods'``, ``'pods.v1'``, and some other notations; this includes
    all objects with string properties ``.group``, ``.version``, ``.plural``.

    There are 2 ways to delete the object:

    * ``del kmock.objects['v1/pods', 'ns', 'n']`` hard-deletes it from memory.
    * ``kmock.objects['v1/pods', 'ns', 'n'].delete()`` soft-deletes the object.

    When the object is hard-deleted, a new object with the same name begins
    a new history starting with the version zero. The previous history is lost.

    When the object is soft-deleted, a placeholder ``None`` is put as the latest
    version. It does NOT compare to any dict anymore (always raises an error).
    However, it still has ``.history`` to access the past states of the object,
    or ``.last`` to access the last seen non-deleted state.

    The array does not do any introspection or interpretation of an object's
    stored contents, such as name-, namespace-, or resource-guessing.
    These elements must be provided as the object's address (key) explicitly.
    The API handler does the introspection from the URL and the request payload.

    A new object with the same name continues the versioning with the new state.
    The following state of the object's history is possible
    (note: the ``<=`` & ``>=`` mean set-like "includes but may contain more")::

        POST /…/namespaces/ns/… ← {'spec': '1st', 'metadata': {'name': 'n1'}}
        PATCH /…/namespaces/ns/…/n1 ← {'spec': '1st modified'}
        DELETE /…/namespaces/ns/…/n1
        POST /…/namespaces/ns/… ← {'spec': '2nd', 'metadata': {'name': 'n1'}}

        assert len(kmock.objects[r, 'ns', 'n1', 0].history) == 4
        assert kmock.objects[r, 'ns', 'n1', 0] >= {'spec': '1st'}
        assert kmock.objects[r, 'ns', 'n1', 1] >= {'spec': '1st modified'}
        assert kmock.objects[r, 'ns', 'n1', 2] is None
        assert kmock.objects[r, 'ns', 'n1', 3] >= {'spec': '2nd'}

    Objects tend to be sorted chronologically in the order of first appearance
    with the same code flow — the same as it happens for usual Python dicts.
    The hard-deletion followed by re-creation moves the object to the end.
    The soft-deletion followed by re-creation keeps it in its original position.
    """
    _objects: dict[ArrayKey, k8s_dicts.Object] = attrs.field(factory=dict, init=False)

    def __bool__(self) -> bool:
        return bool(self._objects)

    def __len__(self) -> int:
        return len(self._objects)

    def __iter__(self) -> Iterator[ArrayKey]:
        yield from self._objects

    def keys(self) -> Iterator[ArrayKey]:
        yield from self._objects.keys()

    def values(self) -> Iterator[k8s_dicts.Object]:
        yield from self._objects.values()

    def items(self) -> Iterator[tuple[ArrayKey, k8s_dicts.Object]]:
        yield from self._objects.items()

    # kmock.objects >= [{…}, {…}]
    # All provided patterns match at least one object each. Order is irrelevant.
    def __ge__(self, other: Any) -> bool:
        match other:
            case list() | tuple():
                matches: dict[int, set[int]] = {
                    obj_idx: {pat_idx for pat_idx, pat in enumerate(other) if obj >= pat}
                    for obj_idx, obj in enumerate(self._objects.values())
                }
                objs2pats, pats2objs = _match_objects_to_patterns(matches)
                if set(range(len(other))) - set(pats2objs):
                    return False  # unmatched patterns
                return True
            case _:
                return NotImplemented

    # kmock.objects <= [{…}, {…}]
    # All existing objects match at least one pattern each. Order is irrelevant.
    def __le__(self, other: Any) -> bool:
        match other:
            case list() | tuple():
                matches: dict[int, set[int]] = {
                    obj_idx: {pat_idx for pat_idx, pat in enumerate(other) if obj >= pat}
                    for obj_idx, obj in enumerate(self._objects.values())
                }
                objs2pats, pats2objs = _match_objects_to_patterns(matches)
                if set(range(len(self._objects))) - set(objs2pats):
                    return False  # unmatched objects
                return True
            case _:
                return NotImplemented

    # kmock.objects == [{…}, {…}]
    # kmock.objects != [{…}, {…}]
    # All objects match all patterns by strict equality, no misses/extras/dupes.
    # Every pattern can be used only once by one objects, no overlaps are allowed.
    def __eq__(self, other: Any) -> bool:
        match other:
            case list() | tuple():
                matches: dict[int, set[int]] = {
                    obj_idx: {pat_idx for pat_idx, pat in enumerate(other) if obj == pat}
                    for obj_idx, obj in enumerate(self._objects.values())
                }
                objs2pats, pats2objs = _match_objects_to_patterns(matches)
                if set(range(len(self._objects))) - set(objs2pats):
                    return False  # unmatched objects
                if set(range(len(other))) - set(pats2objs):
                    return False  # unmatched patterns
                return True
            case _:
                return NotImplemented

    # Note: instead of `{…} in kmock.objects`, use `kmock.objects >= [{…}]`
    def __contains__(self, key: ObjectKey, /) -> bool:
        return key in self._objects

    # del kmock.objects['v1/pods', 'ns', 'n']
    # del kmock.objects['v1/pods', 'ns', 'n', -1]
    # del kmock.objects['v1/pods', 'ns', 'n', :2]
    def __delitem__(self, key: ObjectKey | VersionKey | HistoryKey) -> None:
        if _is_object_key(key):
            namespace, name = key[-2:]
            resource = _parse_resource(key[0])
            del self._objects[resource, namespace, name]
        elif _is_version_key(key):
            namespace, name, version = key[-3:]
            resource = _parse_resource(key[0])
            del self._objects[resource, namespace, name].history[version]
        elif _is_history_key(key):
            namespace, name, versions = key[-3:]
            resource = _parse_resource(key[0])
            del self._objects[resource, namespace, name].history[versions]
        else:
            raise TypeError(f"Unsupported key: {key!r}")

    # kmock.objects['v1/pods', 'ns', 'n'] = {}
    @overload
    def __setitem__(self, key: ObjectKey, value: Mapping[str, Any], /) -> None:
        ...

    # kmock.objects['v1/pods', 'ns', 'n'] = [{}, None, {'spec': 123}]
    @overload
    def __setitem__(self, key: ObjectKey, value: Iterable[Mapping[str, Any] | None], /) -> None:
        ...

    # kmock.objects['v1/pods', 'ns', 'n', -1] = {}
    @overload
    def __setitem__(self, key: VersionKey, value: Mapping[str, Any] | None, /) -> None:
        ...

    # kmock.objects['v1/pods', 'ns', 'n', :2] = [{}, None, {'spec': 123}]
    @overload
    def __setitem__(self, key: HistoryKey, value: Iterable[Mapping[str, Any] | None], /) -> None:
        ...

    def __setitem__(self, key: ObjectKey | VersionKey | HistoryKey, value: Mapping[str, Any] | None | Iterable[Mapping[str, Any] | None], /) -> None:
        if _is_object_key(key):
            namespace, name = key[-2:]
            resource = _parse_resource(key[0])
            self._objects[resource, namespace, name] = k8s_dicts.Object(value)
        elif _is_version_key(key):
            match value:
                case None | collections.abc.Mapping():
                    namespace, name, version = key[-3:]
                    resource = _parse_resource(key[0])
                    self._objects[resource, namespace, name].history[version] = value
                case _:
                    raise TypeError(f"Assigning history slices to a single version is not allowed.")
        elif _is_history_key(key):
            match value:
                case None | collections.abc.Mapping():
                    raise TypeError(f"Assigning dicts or nones to history slices is not allowed.")
                case _:
                    namespace, name, versions = key[-3:]
                    resource = _parse_resource(key[0])
                    self._objects[resource, namespace, name].history[versions] = value
        else:
            raise TypeError(f"Unsupported key: {key!r}")

    # kmock.objects['v1/pods', 'ns', 'n']
    @overload
    def __getitem__(self, _: ObjectKey, /) -> k8s_dicts.Object:
        ...

    # kmock.objects['v1/pods', 'ns', 'n', -1]
    @overload
    def __getitem__(self, _: VersionKey, /) -> k8s_dicts.ObjectVersion | None:
        ...

    # kmock.objects['v1/pods', 'ns', 'n', :2]
    @overload
    def __getitem__(self, _: HistoryKey, /) -> list[k8s_dicts.ObjectVersion | None]:
        ...

    def __getitem__(self, key: ObjectKey | VersionKey | HistoryKey, /) -> k8s_dicts.Object | k8s_dicts.ObjectVersion | list[k8s_dicts.ObjectVersion | None] | None:
        if _is_object_key(key):
            namespace, name = key[-2:]
            resource = _parse_resource(key[0])
            return self._objects[resource, namespace, name]
        elif _is_version_key(key):
            namespace, name, version = key[-3:]
            resource = _parse_resource(key[0])
            return self._objects[resource, namespace, name].history[version]
        elif _is_history_key(key):
            namespace, name, versions = key[-3:]
            resource = _parse_resource(key[0])
            return self._objects[resource, namespace, name].history[versions]
        else:
            raise TypeError(f"Unsupported key for objects: {key!r}")

    def clear(self) -> None:
        """Remove all past & current objects, reset to the initial state."""
        self._objects.clear()


# Prompt: Write a function _match_objects_to_patterns for the Augmenting Path Algorithm.
# The function accepts `matches: dict[int, set[int]]` with the indexes of the source
# elements mapped to the matching target elements,
# and returns a pair of two `dict[int, int]` from source indexes to their best-matching
# target indexes, and from the target indexes back to their best-matching source indexes.
# One source index can match at most one target index, and one target index matches at most
# one source index. The reuse or overlaps of target or source indexes are not allowed.
def _match_objects_to_patterns(
        matches: dict[int, set[int]]
) -> tuple[dict[int, int], dict[int, int]]:
    src2dst: dict[int, int] = {}
    dst2src: dict[int, int] = {}
    for source in matches:
        _find_augmenting_path(matches, src2dst, dst2src, source, visited=set())
    return src2dst, dst2src


# AI suggests this as a closure function, but a standalone one is better with JIT.
# As such, we carry the full accumulating state in the arguments, not in the closure.
def _find_augmenting_path(
        matches: dict[int, set[int]],
        src2dst: dict[int, int],
        dst2src: dict[int, int],
        src: int,
        visited: set[int],
) -> bool:
    for dst in matches.get(src, set()):
        if dst in visited:
            continue
        visited.add(dst)

        # If dst is unmatched, we found an augmenting path.
        if dst not in dst2src:
            src2dst[src] = dst
            dst2src[dst] = src
            return True

        # If dst is already matched, try to find an augmenting path
        # from the src currently matched to this dst.
        current_source = dst2src[dst]
        if _find_augmenting_path(matches, src2dst, dst2src, current_source, visited):
            # We found an augmenting path, so reassign this dst to new src
            src2dst[src] = dst
            dst2src[dst] = src
            return True

    return False
