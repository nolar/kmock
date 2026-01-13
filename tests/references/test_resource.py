import attrs
import pytest

from kmock import resource


def test_creation_from_kwargs() -> None:
    result = resource(group='group', version='version', plural='plural')
    assert result.group == 'group'
    assert result.version == 'version'
    assert result.plural == 'plural'


def test_creation_from_preparsed() -> None:
    preparsed = resource(group='group', version='version', plural='plural')
    result = resource(preparsed)
    assert result == preparsed


def test_creation_from_preparsed_with_extras() -> None:
    preparsed = resource(group='group', version='version', plural='plural')
    with pytest.raises(TypeError, match=r"Too many arguments: only one selectable"):
        resource(preparsed, 'extra')
    with pytest.raises(TypeError, match=r"Too many arguments: only one selectable"):
        resource(preparsed, None, 'extra')


def test_equality_of_resource_vs_string() -> None:
    resource1 = resource('kopf.dev/v1/kopfexamples')
    assert resource1 == 'kopf.dev/v1/kopfexamples'
    assert resource1 != 'kopf.dev/v1/somethingelse'
    assert 'kopf.dev/v1/kopfexamples' == resource1
    assert 'kopf.dev/v1/somethingelse' != resource1


def test_equality_of_resource_vs_resource() -> None:
    resource1 = resource('kopf.dev/v1/kopfexamples')
    resource2 = resource('kopf.dev/v1/kopfexamples')
    resource3 = resource('kopf.dev/v1/somethingelse')
    assert resource1 == resource2
    assert resource1 != resource3


@attrs.frozen
class TestSelectable:
    group: str | None
    version: str | None
    plural: str | None


def test_equality_of_resource_vs_selectable() -> None:
    resource1 = resource('kopf.dev/v1/kopfexamples')
    resource2 = TestSelectable('kopf.dev', 'v1', 'kopfexamples')
    resource3 = TestSelectable('kopf.dev', 'v1', 'somethingelse')
    assert resource1 == resource2
    assert resource1 != resource3


def test_equality_of_resource_vs_wrong_types() -> None:
    resource1 = resource('kopf.dev/v1/kopfexamples')
    assert resource1 != 123  # because NotImplemented and there is no other override
