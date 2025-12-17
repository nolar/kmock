import enum
from typing import overload

from typing_extensions import Self

_unknown_methods: dict[str, "method"] = {}


class method(str, enum.Enum):
    """
    Which HTTP method is requested (of those we recognize).
    """
    GET = 'GET'
    PUT = 'PUT'
    POST = 'POST'
    HEAD = 'HEAD'
    PATCH = 'PATCH'
    DELETE = 'DELETE'
    OPTIONS = 'OPTIONS'

    @classmethod
    @overload
    def guess(cls, value: None) -> None:
        ...

    @classmethod
    @overload
    def guess(cls, value: Self) -> Self:
        ...

    @classmethod
    @overload
    def guess(cls, value: str) -> Self:
        ...

    @classmethod
    def guess(cls, value: str | None | Self) -> Self | None:
        if value is None or isinstance(value, cls):
            return value
        for v in cls:
            if v.name.upper() == value.upper() or v.value.upper() == value.upper():
                return v

        # Unknown HTTP methods are rendered as method instances.
        # This block also applies to the initial enum members population.
        global _unknown_methods
        if value.lower() not in _unknown_methods:
            pseudo_enum = super().__new__(cls, value)
            pseudo_enum._value_ = value
            pseudo_enum._name_ = value
            _unknown_methods[value.lower()] = pseudo_enum
        return _unknown_methods[value.lower()]


class action(str, enum.Enum):
    """
    Which K8s action is requested, based on the HTTP method & URL structure.

    Note: It follows the same convention of using verbs as in HTTP `method`,
    except for the deletion: it would conflict with the well-known HTTP verb.
    In most cases, there is no big difference between the HTTP method `DELETE`
    and the Kubernetes-level action of deletion, so the `"delete"` can be used.
    If it matters, the action criterion can be enforced either by passing
    an enum value `action.DELETE` explicitly (not a string), or as the keyword
    argument `action='delete'` (both name & value are accepted in this case).
    """
    LIST = 'LIST'  # corresponds: method==GET && the name is absent (otherwise FETCH)
    WATCH = 'WATCH'  # corresponds: method==GET && ?watch=true is present (with & without names)
    FETCH = 'FETCH'  # corresponds: method==GET && the name is present (otherwise LIST)
    CREATE = 'CREATE'  # corresponds: method==POST; the name is absent (NB!)
    UPDATE = 'UPDATE'  # corresponds: method==PATCH; the name is present
    DELETE = 'DELETE'  # corresponds: method==DELETE; the name is present
    # We ignore a few combinations of methods and URL parts:
    # - DELETE & PATCH & PUT on list resources (they make little sense in the K8s URL conventions).
    # - POST on named resources (it has no sense at all).
    # - PUT on named resources (but it would correspond to CREATE/UPDATE based on situation).
    # Note: WATCH on named resources is detected, despite it is not used by Kopf.

    @classmethod
    @overload
    def guess(cls, value: None) -> None:
        ...

    @classmethod
    @overload
    def guess(cls, value: Self) -> Self:
        ...

    @classmethod
    @overload
    def guess(cls, value: str) -> Self:
        ...

    @classmethod
    def guess(cls, value: str | None | Self) -> Self | None:
        if value is None or isinstance(value, cls):
            return value
        for v in cls:
            if v.name.upper() == value.upper() or v.value.upper() == value.upper():
                return v
        return enum.Enum.__new__(cls, value)


# A trick to support unknown methods as instances of method, despite not accessible as method.XYZ.
# I.e., they will always have .name & value & a good repr & pass the isinstance(…, method) check.
#   method('GET') -> method.GET
#   method('get') -> method.GET
#   method('unknown') -> has .name & .value, though it is unavailable as method.UNKNOWN
#   action('LIST') -> action.LIST
#   action('list') -> action.LIST
#   action('unknown') -> raises ValueError!
# Python StdLib overwrites __new__ with its own restrictive code, so we monkey-patch post-factum:
method.__new__ = lambda cls, value: cls.guess(value)  # type: ignore[method-assign,assignment]
action.__new__ = lambda cls, value: cls.guess(value)  # type: ignore[method-assign,assignment]
