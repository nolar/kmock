import re
from collections.abc import Iterable
from typing import Any, Protocol, Union, runtime_checkable

import attrs

# Detect conventional API versions for some cases: e.g. in "myresources.v1alpha1.example.com".
# Non-conventional versions are indistinguishable from API groups ("myresources.foo1.example.com").
# See also: https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definition-versioning/
K8S_VERSION_PATTERN = re.compile(r'^v\d+(?:(?:alpha|beta)\d+)?$')


@runtime_checkable
class Selectable(Protocol):
    """
    A minimally sufficient resource to be recognized for selection/filtering.
    Anything less that that is not even considered.
    More fields CAN be present (as per other protocols), but not required.
    """
    group: str | None
    version: str | None
    plural: str | None


@attrs.frozen(init=False, eq=False, unsafe_hash=True)
class resource(Selectable):
    """
    A resource specification that can match several resource kinds.

    The resource specifications are not usable in K8s API calls, as the API
    has no endpoints with masks or placeholders for unknown or catch-all
    resource identifying parts (e.g. any API group, any API version, any name).

    They are used only locally in the operator to match against the actual
    resources with specific names (:class:`kmock.resource`). The handlers are
    defined with resource specifications, but are invoked with specific
    resource kinds. Even if those specifications look very concrete and allow
    no variations, they still remain specifications.
    """
    group: str | None = None
    version: str | None = None
    plural: str | None = None

    # TODO: Rewrite Union[X,Y] to X|Y when Python 3.10 is dropped (≈October 2026).
    #   Fails on Unions + ForwardRefs: https://github.com/python/cpython/issues/90015
    def __init__(
            self,
            arg1: str | Union[Selectable, "resource"] | None = None,
            arg2: str | None = None,
            arg3: str | None = None,
            /, *,
            group: str | None = None,
            version: str | None = None,
            plural: str | None = None,
    ) -> None:
        parsed_group: str | None = None
        parsed_version: str | None = None
        parsed_plural: str | None = None

        if isinstance(arg1, (Selectable, resource)):
            if arg2 is not None or arg3 is not None:
                raise TypeError("Too many arguments: only one selectable object is accepted.")
            parsed_group = arg1.group
            parsed_version = arg1.version
            parsed_plural = arg1.plural
        elif arg3 is not None:  # ('kopf.dev', 'v1', 'kexes'), ('', 'v1', 'pods')
            parsed_group = arg1
            parsed_version = arg2
            parsed_plural = arg3
        elif arg2 is not None:
            if isinstance(arg1, str) and '/' in arg1:  # ('kopf.dev/v1', 'kexes')
                parsed_group = arg1.rsplit('/', 1)[0]
                parsed_version = arg1.rsplit('/')[-1]
                parsed_plural = arg2
            elif arg1 == 'v1':  # ('v1', 'pods')
                parsed_group = ''
                parsed_version = arg1
                parsed_plural = arg2
            else:  #  ('kopf.dev', 'kexes')
                parsed_group = arg1
                parsed_plural = arg2
        elif arg1 is not None:
            if '/' in arg1:
                if K8S_VERSION_PATTERN.match(arg1.split('/')[1]):  # kopf.dev/v1, kopf.dev/v1/kexes
                    parsed_group = arg1.split('/')[0]
                    parsed_version = arg1.split('/')[1]
                    parsed_plural = arg1.split('/', 2)[2] if len(arg1.split('/')) >= 3 else None
                elif K8S_VERSION_PATTERN.match(arg1.split('/')[0]):  # v1/pods
                    parsed_group = ''
                    parsed_version = arg1.split('/', 1)[0]
                    parsed_plural = arg1.split('/', 1)[1]
                else:  # kopf.dev/kopfexamples
                    parsed_group = arg1.split('/')[0]
                    parsed_plural = arg1.split('/', 1)[1]
            elif '.' in arg1:
                if K8S_VERSION_PATTERN.match(arg1.split('.')[1]):  # kexes.v1.kopf.dev, pods.v1
                    parsed_group = arg1.split('.', 2)[2] if len(arg1.split('.')) >= 3 else ''
                    parsed_version = arg1.split('.')[1]
                    parsed_plural = arg1.split('.')[0]
                else:  # kopfexamples.kopf.dev
                    parsed_group = arg1.split('.', 1)[1]
                    parsed_plural = arg1.split('.')[0]
            elif arg1 == 'v1':  # 'v1'
                parsed_group = ''
                parsed_version = arg1
            else:  # 'pods', 'kexes'
                parsed_plural = arg1 or None

        if group is not None and parsed_group is not None:
            raise TypeError(f"Ambiguous resource group: {group!r} vs. {parsed_group!r}")
        if version is not None and parsed_version is not None:
            raise TypeError(f"Ambiguous resource version: {version!r} vs. {parsed_version!r}")
        if plural is not None and parsed_plural is not None:
            raise TypeError(f"Ambiguous resource name: {plural!r} vs. {parsed_plural!r}")

        self.__attrs_init__(
            group=group if group is not None else parsed_group,
            version=version if version is not None else parsed_version,
            plural=plural if plural is not None else parsed_plural,
        )

    def __eq__(self, other: object) -> bool:
        match other:
            case resource() | Selectable():
                return (self.group, self.version, self.plural) == (other.group, other.version, other.plural)
            case str():
                parsed = resource(other)
                return (self.group, self.version, self.plural) == (parsed.group, parsed.version, parsed.plural)
            case _:
                return NotImplemented

    def check(self, resource: Selectable) -> bool:
        return bool(
            (self.group is None or self.group == resource.group) and
            (self.version is None or self.version == resource.version) and
            (self.plural is None or self.plural == resource.plural)
        )


# NB: `converter=set` is easier, works at runtime, but makes mypy cry for no reason.
def _to_set(v: Iterable[str]) -> set[str]:
    return set(v)


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
    verbs: set[str] = attrs.field(factory=set, converter=_to_set)
    shortnames: set[str] = attrs.field(factory=set, converter=_to_set)
    categories: set[str] = attrs.field(factory=set, converter=_to_set)
    subresources: set[str] = attrs.field(factory=set, converter=_to_set)

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
