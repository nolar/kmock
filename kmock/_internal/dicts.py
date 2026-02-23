import collections.abc
from collections.abc import Mapping
from types import EllipsisType
from typing import Any


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
