import pytest

from kmock import action, method
from kmock._internal import enums


@pytest.fixture(autouse=True)
def _reset_cached_enums() -> None:
    enums._unknown_methods.clear()
    yield
    enums._unknown_methods.clear()


@pytest.mark.parametrize('expected', list(method))
def test_method_names(expected: method) -> None:
    created = method(expected.name)
    assert created == expected


@pytest.mark.parametrize('expected', list(method))
def test_method_values(expected: method) -> None:
    created = method(expected.value)
    assert created == expected


@pytest.mark.parametrize('expected', list(method))
def test_method_from_method(expected: method) -> None:
    created = method(expected)
    assert created is expected


def test_method_from_none() -> None:
    assert method(None) is None


def test_method_case_insensitivity() -> None:
    created = method('geT')
    assert created == method.GET


def test_methods_autocreation() -> None:
    created = method('unknown')
    assert isinstance(created, method)
    assert created not in set(method)
    assert created == 'unknown'
    assert created.name == 'unknown'
    assert created.value == 'unknown'


def test_method_reuse() -> None:
    created1 = method('unknown')
    created2 = method('UNKNOWN')
    assert created1 == created2
    assert created1 is created2


@pytest.mark.parametrize('expected', list(action))
def test_action_names(expected: action) -> None:
    created = action(expected.name)
    assert created == expected


@pytest.mark.parametrize('expected', list(action))
def test_action_values(expected: action) -> None:
    created = action(expected.value)
    assert created == expected


@pytest.mark.parametrize('expected', list(action))
def test_action_from_action(expected: action) -> None:
    created = action(expected)
    assert created is expected


def test_action_from_none() -> None:
    assert action(None) is None


def test_action_case_insensitivity() -> None:
    created = action('lIsT')
    assert created == action.LIST


def test_action_strictness() -> None:
    with pytest.raises(ValueError, match=r"'unknown' is not a valid action"):
        action('unknown')
