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
