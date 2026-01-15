import collections.abc
import copy
from collections.abc import Iterable, Iterator, Mapping, MutableMapping, MutableSequence
from types import EllipsisType
from typing import Any, overload

import attrs

# A note for future self: if you ever want to turn these classes into generics,
# forget it — it will not work. We rely on recursive processing of nested dicts
# for patching & matching, which requires Any for the values. We also imply None
# for absent or to-be-removed values, which might conflict with Generic[K, V].
# Also there is a conflict of a generic K with the strict str keys in kwargs.
# Even if it were possible, there is no benefit: the classes are used for one
# and only one purpose — the Kubernetes object accessors. There is no reuse.
# As such, the dicts remain bound to their purpose of K8s objects: [str, Any].


def patch_dict(value: Mapping[str, Any], patch: Mapping[str, Any], /, **kwargs: Any) -> Mapping[str, Any]:
    """
    Patch & merge the dicts recursively. ``None`` means the deletion of the key.

    The order of the keys is preserved from the value in the first place,
    then from the patch for the new keys. There is no re-shuffling of the keys.

    The patching is memory-thrifty and follows the "copy-on-write" principle.
    I.e., the original values are used without copying if there are no changes
    (even the mutable sub-dicts). New dicts are made only if there are changes.

    Lists and other non-mapping values are taken without merging.
    """
    result: dict[str, Any] = {}
    patch = dict(patch, **kwargs)  # it is safe to loose the runtime type here
    keys = list(value) + [key for key in patch if key not in value]
    for key in keys:
        a: Any | None = value.get(key)
        b: Any | None = patch.get(key)
        match a, b:
            case _, _ if key not in patch:  # old unaffected keys
                result[key] = value[key]
            case _, _ if patch[key] is None:  # deleted keys
                pass
            case _, collections.abc.Mapping() if key not in value:  # new appended keys
                result[key] = patch_dict({}, patch[key])
            case _, _ if key not in value:  # new appended keys
                result[key] = patch[key]
            case collections.abc.Mapping(), collections.abc.Mapping():
                result[key] = patch_dict(a, b)
            case collections.abc.Mapping(), _:
                raise ValueError(f"Cannot patch a dict by a scalar: {a!r} << {b!r}")
            case _, collections.abc.Mapping():
                raise ValueError(f"Cannot patch a scalar by a dict: {a!r} << {b!r}")
            case _:  # overwrite without merging
                result[key] = b
    return result


def match_dict(value: Mapping[str, Any], pattern: Mapping[str, Any], /, *, strict: bool) -> bool:
    """
    Check if the dict matches a pattern recursively.

    All keys in the pattern must match. Extra keys can exist in the dict.
    Ellipsis (``...``) in the pattern is a placeholder for any present value.
    For the absent keys, use the ``...`` pattern with a negation of the result.
    In particular, ``None`` means that the key is present and stores ``None``.
    """
    required_keys = set(pattern)
    available_keys = set(value)
    if required_keys - available_keys:
        return False  # some required keys are missing
    if strict and available_keys - required_keys:
        return False  # some extra keys are present, but not allowed
    for key in  required_keys | (available_keys if strict else set()):
        a = value[key]
        b = pattern[key]
        match a, b:
            case collections.abc.Mapping(), collections.abc.Mapping():
                if not match_dict(a, b, strict=strict):
                    return False  # recursively missing keys
            case _, EllipsisType():  # key is present, value is ignored
                pass  # we already checked that the key exists
            case _ if a != b:  # mismatching types or unequal values
                return False
    return True


@attrs.define(repr=False, init=False, order=False, eq=False)
class ObjectVersion(MutableMapping[str, Any]):
    """
    A single-dict wrapper with extra syntax features for simpler/shorter tests.

    In the core, it is a read-only mapping with a view into the wrapped dict,
    typically with the keys like ``metadata``, ``spec``, and ``status``,
    but this is neither required nor guaranteed.

    Unlike the regular dict, the object has set-like recursive partial matching.
    However, both the keys presence and their values must match on comparison.

    The actual "greater" object may contain more keys than the "smaller" pattern
    expects (typically, the metadata, names/namespaces, or resource versions),
    but those in the pattern are required and must store the expected values.

    The inverse comparison —the "smaller" raw dict & the "greater" dict view—
    is NOT a boolean inverse of the straighforward operator, but a role switch:
    the "smaller" unwrapped raw dict becomes a pattern,
    the "greater" wrapped dict becomes an object to be checked with extra keys.

    There are, by design, no ``>`` or ``<`` operators, only ``>=`` and ``<=``.
    The strict inclusion-except-equality of dicts makes no sense semantically.
    Also to avoid confusion between the role switching and inverse comparison.

    All in all, the actual pattern is always on the "smaller" side (always!).

    Example with the object containing the pattern (and maybe more)::

        assert kmock.objects[r, 'ns', 'n'] >= {'spec': {'key': 'must be this'}}
        assert {'spec': {'key': 'must be this'}} <= kmock.objects[r, 'ns', 'n']

    Example with the object NOT containing the pattern (can contain more keys)::

        assert not kmock.objects[r, 'ns', 'n'] >= {'spec': {'key': 'not this'}}
        assert not {'spec': {'key': 'not this'}} <= kmock.objects[r, 'ns', 'n']

    The ``...`` aka ``Ellipsis`` means "any value but the key must be present"
    (or "must be absent" with the negation/inversion)::

        assert kmock.objects[r, 'ns', 'n'] >= {'spec': {'key': ...}}  # present
        assert not kmock.objects[r, 'ns', 'n'] >= {'spec': {'key': ...}}  # absent

    Similar to regular dicts, the equality compares the dict as a whole,
    i.e. no extra keys are allowed in the object (``...`` is supported though)::

        assert kmock.objects[r, 'ns', 'n'] == {
            'metadata': {'name': 'n1', 'namespace': ...},
            'spec': 'must be this',
        }

    The inequality means that the values mismatch or there are the extra keys::

        assert kmock.objects[r, 'ns', 'n'] != {'spec': {'key': ...}}

    For pattern matching of two raw dicts, e.g. from an API, wrap one & compare
    to a plain-dict pattern, or wrap the plain-dict pattern itself,
    just to bring the magic to play (but mind the direction of the comparison)::

        assert kmock.PatternDict(resp['items'][0]) >= {'spec': {'key': ...}}
        assert resp['items'][0] >= kmock.PatternDict({'spec': {'key': ...}})
        assert {'spec': {'key': ...}} <= kmock.PatternDict(resp['items'][0])
        assert kmock.PatternDict({'spec': {'key': ...}}) <= resp['items'][0]

    Nested dicts (and only dicts/mappings) are enhanced with magic on access::

        assert kmock.objects[r, 'ns', 'n']['spec'] >= {'key': ...}

    But the nested non-dicts, i.e. regular values, lists, tuples, are not::

        assert kmock.objects[r, 'ns', 'n']['spec']['key'] == 'val'  # no "..."!

    To access a raw dict —nested or top-level— convert it to ``dict()``.
    Then Python does the comparison, i.e. with no recursive partial matching::

        assert dict(kmock.objects[r, 'ns', 'n'])['spec'] == {'key': 'only this'}
        assert dict(kmock.objects[r, 'ns', 'n']['spec'])['key'] == 'only this'

    Note: it is challenging to reliably wrap the nested non-dict values
    and expose their specialized fields/methods, behaviour, math, reprs, etc.
    Especially in identity checks like ``obj['key'] is None``.
    The ``...`` magic is not supported on the extracted scalars or lists.
    """
    __value: MutableMapping[str, Any]

    def __init__(self, value: Mapping[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__()
        match value:
            case None:
                self.__value = kwargs
            case ObjectVersion() if not kwargs:
                self.__value = dict(value.__value)  # unwrap
            case collections.abc.Mapping():
                self.__value = dict(value, **kwargs)
            case _:
                raise TypeError(f"Unsupported value: {value!r}")

    def __repr__(self) -> str:
        value_repr = repr(self.__value) if self.__value else ''
        return f"{self.__class__.__name__}({value_repr})"

    def __iter__(self) -> Iterator[str]:
        yield from iter(self.__value.keys())

    def __bool__(self) -> bool:
        return bool(self.__value)

    def __len__(self) -> int:
        return len(self.__value)

    # kmock.objects['v1/pods', 'ns', 'n', -1] >= {'spec': {'key': ...}}
    # {'spec': {'key': ...}} <= kmock.objects['v1/pods', 'ns', 'n', -1]
    def __ge__(self, other: Mapping[str, Any]) -> bool:
        match other:
            case collections.abc.Mapping():
                return match_dict(self, other, strict=False)
            case _:
                return NotImplemented

    # resp.json()['items'][0] >= Pattern({'spec': {'key': ...}})
    # Pattern({'spec': {'key': ...}}) <= resp.json()['items'][0]
    def __le__(self, other: Mapping[str, Any]) -> bool:
        match other:
            case collections.abc.Mapping():
                return match_dict(other, self, strict=False)  # we are the pattern!
            case _:
                return NotImplemented

    # resp.json()['items'][0] < Pattern({'spec': {'key': ...}})
    # Pattern({'spec': {'key': ...}}) > resp.json()['items'][0]
    def __gt__(self, value: Mapping[str, Any]) -> bool:
        raise NotImplementedError(
            "Strict greater-than is not implemented as semantically meaningless "
            "and to avoid an accidental confusion with the side/role switching. "
            "Use the negation with `not` to be more explicit: `not pattern <= data`"
        )

    # kmock.objects['v1/pods', 'ns', 'n', -1] < {'spec': {'key': ...}}
    # {'spec': {'key': ...}} > kmock.objects['v1/pods', 'ns', 'n', -1]
    def __lt__(self, pattern: Mapping[str, Any]) -> bool:
        raise NotImplementedError(
            "Strict lesser-than is not implemented as semantically meaningless "
            "and to avoid an accidental confusion with the side/role switching. "
            "Use the negation with `not` to be more explicit: `not data >= pattern`"
        )

    # kmock.objects['v1/pods', 'ns', 'n', -1] == {'spec': {'key': ...}}
    # kmock.objects['v1/pods', 'ns', 'n', -1] != {'spec': {'key': ...}}
    # {'spec': {'key': ...}} == kmock.objects['v1/pods', 'ns', 'n', -1]
    # {'spec': {'key': ...}} != kmock.objects['v1/pods', 'ns', 'n', -1]
    def __eq__(self, other: object) -> bool:
        match other:
            case collections.abc.Mapping():
                return match_dict(self, other, strict=True)
            case _:
                return NotImplemented

    # 'key' in kmock.objects['v1/pods', 'ns', 'n']['spec']
    def __contains__(self, key: object) -> bool:
        return key in self.__value

    # del kmock.objects['v1/pods', 'ns', 'n']['spec']
    def __delitem__(self, key: str, /) -> None:
        del self.__value[key]

    # kmock.objects['v1/pods', 'ns', 'n']['spec'] = {'key': 'val'}
    def __setitem__(self, key: str, value: Any, /) -> None:
        match value:
            case ObjectVersion():
                self.__value[key] = value.__value  # unwrap if taken from the other view
            case _:
                self.__value[key] = value

    # kmock.objects['v1/pods', 'ns', 'n']['spec'] >= {'key': ...}
    # kmock.objects['v1/pods', 'ns', 'n']['spec'] == {'key': ...}
    # kmock.objects['v1/pods', 'ns', 'n']['spec']['key']  # no Ellipsis magic!
    def __getitem__(self, key: str, /) -> Any:
        match value := self.__value[key]:
            case collections.abc.Mapping():
                return self.__class__(value)
            case _:
                return value

    @property
    def raw(self) -> dict[str, Any]:
        """Return the raw dict ready to be used in JSON, no magic views."""
        return dict(self.__value)


@attrs.define(repr=False, init=False, order=False, eq=False)
class ObjectHistory(MutableSequence[ObjectVersion | None]):
    """
    Addressable and adjustable history of dict versions.

    ``None`` is used as a soft-deletion marker.
    """
    __items: list[ObjectVersion | None]  # store pre-wrapped for efficiency

    def __init__(self, items: Iterable[Mapping[str, Any] | None] = (), /) -> None:
        super().__init__()
        self.__items = [None if item is None else ObjectVersion(item) for item in items]

    def __repr__(self) -> str:
        reprs = [repr(None if item is None else dict(item)) for item in self.__items]
        reprs_str = f"[{', '.join(reprs)}]" if reprs else ''
        return f"{self.__class__.__name__}({reprs_str})"

    # kmock['v1/pods', 'ns', 'n'].history >= […, …], maybe more
    def __ge__(self, other: object) -> bool:
        match other:
            case collections.abc.Iterable():
                materialized = list(other)
                return all(any(v1 == v2 for v2 in self.__items) for v1 in materialized)
            case _:
                return NotImplemented

    # kmock['v1/pods', 'ns', 'n'].history <= […, …], a subset of possibilities
    def __le__(self, other: object) -> bool:
        match other:
            case collections.abc.Iterable():
                materialized = list(other)
                return all(any(v1 == v2 for v2 in materialized) for v1 in self.__items)
            case _:
                return NotImplemented

    # kmock['v1/pods', 'ns', 'n'].history == […, …]
    def __eq__(self, other: object) -> bool:
        match other:
            case collections.abc.Iterable():
                return self.__items == list(other)
            case _:
                return NotImplemented

    def __len__(self) -> int:
        return len(self.__items)

    def __bool__(self) -> bool:
        return bool(self.__items)

    def __iter__(self) -> Iterator[ObjectVersion | None]:
        return iter(self.__items)

    # del kmock.objects['v1/pods', 'ns', 'n'].history[-1]
    # del kmock.objects['v1/pods', 'ns', 'n'].history[-2:]
    def __delitem__(self, key: int | slice, /) -> None:
        del self.__items[key]

    # kmock.objects['v1/pods', 'ns', 'n'].history[-1] = {…}
    @overload
    def __setitem__(self, key: int, value: Mapping[str, Any] | None, /) -> None:
        ...

    # kmock.objects['v1/pods', 'ns', 'n'].history[-2:] = [{…}, {…}]
    @overload
    def __setitem__(self, key: slice, value: Iterable[Mapping[str, Any] | None], /) -> None:
        ...

    def __setitem__(self, key: int | slice, value: Mapping[str, Any] | None | Iterable[Mapping[str, Any] | None], /) -> None:
        # NB: it is challenging to distinguish the DictInput iterables from the lists of DictInputs.
        # We rely on the key type —int or slice— but the type checkers are more picky for all cases.
        match key, value:
            case int(), None:
                self.__items[key] = None
            case int(), collections.abc.Mapping():
                self.__items[key] = ObjectVersion(value)
            case slice(), None:
                raise TypeError("Assigning None to history slices is not supported.")
            case slice(), collections.abc.Mapping():
                raise TypeError("Assigning dicts to history slices is not supported.")
            case slice(), collections.abc.Iterable():
                items: list[ObjectVersion | None] = []
                for item in value:
                    match item:
                        case None:
                            items.append(None)
                        case collections.abc.Mapping():
                            items.append(ObjectVersion(item))
                        case _:
                            raise TypeError(f"Unsupported item in the history: {item!r}.")
                self.__items[key] = items
            case _:
                raise TypeError(f"Unsupported types: [{key!r}]={value!r}")

    # kmock.objects['v1/pods', 'ns', 'n'].history[-1]
    @overload
    def __getitem__(self, key: int) -> ObjectVersion | None:
        ...

    # kmock.objects['v1/pods', 'ns', 'n'].history[-2:]
    @overload
    def __getitem__(self, key: slice) -> list[ObjectVersion | None]:
        ...

    def __getitem__(self, key: int | slice) -> ObjectVersion | None | list[ObjectVersion | None]:
        return self.__items[key]

    def clear(self) -> None:
        self.__items.clear()

    def insert(self, index: int, value: Mapping[str, Any] | None) -> None:
        self.__items.insert(index, None if value is None else ObjectVersion(value))

    def append(self, value: Mapping[str, Any] | None) -> None:
        self.__items.append(None if value is None else ObjectVersion(value))

    def extend(self, value: Iterable[Mapping[str, Any] | None]) -> None:
        self.__items.extend(None if v is None else ObjectVersion(v) for v in value)

    def pop(self, index: int = -1, /) -> ObjectVersion | None:
        return self.__items.pop(index)

    def remove(self, value: Mapping[str, Any] | None, /) -> None:
        for idx, item in enumerate(self.__items):
            if item == value:  # by strict equality, not by pattern
                del self.__items[idx]
                break  # only the 1st one is removed

    @property
    def last(self) -> ObjectVersion:
        """
        The last seen state before the soft-deletion(s) or after the patch(es).
        """
        for item in reversed(self.__items):
            if item is not None:
                return item
        raise ValueError("The object has no last seen state in its history.")

    @property
    def raw(self) -> list[ObjectVersion | None]:
        return self.__items[:]


@attrs.define(init=False, repr=False, order=False, eq=False)
class Object(MutableMapping[str, Any]):
    """
    A view of a single object: ``kmock.objects[resource, namespace, name]``.

    * ``==`` & ``!=`` recursively compare for precise equality.
    * ``<=`` & ``>=`` recursively compare against a partial pattern.

    Accessing/modifying the versioned dict delegates to the latest version
    of the dict. The previous versions are unaffected unless modified directly::

        kmock.objects['v1/pods', 'ns', 'n'].history[0]['spec'] = {'key': 'val'}

    The modification of individual keys or keys en mass, such as ``.update(…)``,
    changes the latest version and does not grow the history — in order to make
    it easier to modify objects in tests without the API-level side effects.
    Only the dedicated methods for creating/patching/deleting grow the history.

    Another critical difference of ``.patch()`` vs. ``.update()``:
    ``.patch()`` merges the sub-dicts as it happens in the Kubernetes API;
    ``.update()`` does not merge the sub-dicts, instead it overwrites them
    as if simply assigned by keys — to mimic the behavior of Python's dicts.
    This method is is a part of the ``MutableMapping``, not an API-like method::

        obj = VersionedDict({'spec': {'interval': 10, 'timeout': 60}})

        obj.patch({'spec': {'interval': 20}})
        assert obj == {'spec': {'interval': 20, 'timeout': 60}}

        obj.update({'spec': {'interval': 30}})
        assert obj == {'spec': {'interval': 30}}

        # Synonymous to:
        obj['spec'] = {'interval': 30}

    If there is no latest version —whether because it was never populated
    or because it was soft-deleted— then a new empty dict is auto-populated.
    """
    __history: ObjectHistory

    def __init__(self, history: Mapping[str, Any] | None | Iterable[Mapping[str, Any] | None] = (), /) -> None:
        super().__init__()
        match history:
            case None:
                self.__history = ObjectHistory([history])
            case collections.abc.Mapping():
                self.__history = ObjectHistory([history])
            case collections.abc.Iterable():
                # FIXME: Mapping[str, Any] leaks to here despite the case above.
                self.__history = ObjectHistory(history)
            case _:
                raise TypeError(f"Unsupported history: {history!r}")

    def __repr__(self) -> str:
        # Hide the DictHistory presence, unwrap its content as the positional argument.
        items = self.__history.raw
        reprs = [repr(None if version is None else dict(version)) for version in items]
        reprs_str = f"[{', '.join(reprs)}]" if reprs else ''
        return f"{self.__class__.__name__}({reprs_str})"

    def __iter__(self) -> Iterator[str]:
        yield from {} if self.deleted else self.last.keys()

    def __len__(self) -> int:
        return 0 if self.deleted else len(self.last)

    def __ge__(self, other: Mapping[str, Any]) -> bool:
        return (ObjectVersion() if self.deleted else self.last) >= other

    def __le__(self, other: Mapping[str, Any]) -> bool:
        return (ObjectVersion() if self.deleted else self.last) <= other

    def __gt__(self, other: Mapping[str, Any]) -> bool:
        return (ObjectVersion() if self.deleted else self.last) > other  # should raise

    def __lt__(self, other: Mapping[str, Any]) -> bool:
        return (ObjectVersion() if self.deleted else self.last) < other  # should raise

    def __eq__(self, pattern: object) -> bool:
        match pattern:
            case collections.abc.Mapping():
                return (ObjectVersion() if self.deleted else self.last) == pattern
            case _:
                return NotImplemented

    # 'spec' in kmock.objects['v1/pods', 'ns', 'n']
    def __contains__(self, key: object) -> bool:
        return False if self.deleted else key in self.last

    # del kmock.objects['v1/pods', 'ns', 'n']['spec']
    def __delitem__(self, key: str, /) -> None:
        if self.deleted:
            raise KeyError(f"No such key: {key!r}")
        del self.last[key]

    # kmock.objects['v1/pods', 'ns', 'n']['spec'] = {'key': 'val'}
    def __setitem__(self, key: str, value: Any, /) -> None:
        if self.deleted:
            self.__history.append(ObjectVersion())
        self.last[key] = value

    # kmock.objects['v1/pods', 'ns', 'n']['spec']
    def __getitem__(self, key: str) -> Any:
        if self.deleted:
            raise KeyError(f"No such key: {key!r}")
        return self.last[key]

    def clear(self) -> None:
        """Clear the data from the latest visible version (not the history!)."""
        if not self.deleted:
            self.last.clear()

    def delete(self) -> None:
        """
        Soft-delete the object by marking it as such but retaining the history.

        It is possible to soft-delete the versioned dict a few times in a row.

        In contrast, ``del kmock.objects[…]`` physically deletes it from memory,
        while ``kmock.objects[…].delete()`` keeps the object's history.
        The API emulator uses the soft-deletion internally.
        """
        self.__history.append(None)

    def create(self, changes: Mapping[str, Any] | None = None, /, **kwargs: Any) -> None:
        """
        Populate the dict with the new data.

        Can be called only if the object is either empty or soft-deleted.
        """
        self.__history.append(ObjectVersion(changes, **kwargs))

    def patch(self, changes: Mapping[str, Any] | None = None, /, **kwargs: Any) -> None:
        """
        Recursively patch the object by creating a new version.

        For scalar values, it is the same as native Python update (replacing).
        For dicts, it is a recursive merge (patching). This is so to prevent
        a dict value in the patch to replace the whole pre-existing dict
        in the base object instead of several keys in it::

            obj = Object({'spec': {'timeout': 60, 'interval': 10}})
            obj.patch({'spec': {'interval': 15}})
            assert obj == {'spec': {'timeout': 60, 'interval': 15}}

        Note the preservance of ``timeout=60`` in this example,
        which would be lost with the native Python update.

        ``None`` removes the key (even if nested).
        """
        if self.deleted:
            self.__history.append(ObjectVersion(changes, **kwargs))
        else:
            old_version = copy.deepcopy(self.last.raw)  # avoid side mutations
            new_version = patch_dict(old_version, changes or {}, **kwargs)
            self.__history.append(ObjectVersion(new_version))

    @property
    def empty(self) -> bool:
        """
        Whether the object was never created/populated (yet).
        """
        return bool(not self.__history)

    @property
    def deleted(self) -> bool:
        """
        Whether the object was never created or was recently soft-deleted.
        """
        return bool(not self.__history or self.__history[-1] is None)

    @property
    def last(self) -> ObjectVersion:
        """
        The last seen state before the soft-deletion(s) or after the patch(es).
        """
        for obj in reversed(self.__history):
            if obj is not None:
                return obj
        raise ValueError("The object has no last seen state in its history.")

    @property
    def raw(self) -> dict[str, Any]:
        """Return the raw dict ready to be used in JSON, no magic views."""
        if self.deleted:
            raise ValueError(f"The object is soft-deleted and has no raw form.")
        return self.last.raw

    @property
    def history(self) -> ObjectHistory:
        """
        The full history of the dict, all its versions & soft-deletion markers.
        """
        return self.__history  # avoid replacing (setting) the managed container

    @history.setter
    def history(self, history: Iterable[Mapping[str, Any] | None]) -> None:
        self.__history[:] = history

    @history.deleter
    def history(self) -> None:
        del self.__history[:]
