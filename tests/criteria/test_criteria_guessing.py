import re
from collections.abc import AsyncIterator, Iterator
from typing import Any

import aiohttp.web
import attrs
import pytest

from kmock import Criteria, DictCriteria, HTTPCriteria, K8sCriteria, Selectable, StrCriteria, action, method, resource


@attrs.frozen
class SampleResource(Selectable):
    group: str
    version: str
    plural: str


@pytest.mark.parametrize('method_', list(method))
def test_none_guessing(method_: method) -> None:
    criteria = Criteria.guess(None)
    assert criteria is None


@pytest.mark.parametrize('method_', list(method))
def test_method_enum_guessing(method_: method) -> None:
    criteria = Criteria.guess(method_)
    assert isinstance(criteria, HTTPCriteria)
    assert criteria.method == method_
    assert not attrs.asdict(criteria, filter=lambda a, v: v is not ... and a.name not in {'method'})


@pytest.mark.parametrize('arg, method_', (
    {(m.name.lower(), m) for m in method} |
    {(m.name.upper(), m) for m in method} |
    {(m.name.title(), m) for m in method} |
    {(m.value.lower(), m) for m in method} |
    {(m.value.upper(), m) for m in method} |
    {(m.value.title(), m) for m in method}
))
def test_method_str_guessing(arg: str, method_: method) -> None:
    criteria = Criteria.guess(arg)
    assert isinstance(criteria, HTTPCriteria)
    assert criteria.method == method_
    assert not attrs.asdict(criteria, filter=lambda a, v: v is not ... and a.name not in {'method'})


@pytest.mark.parametrize('action_', list(action))
def test_action_enum_guessing(action_: action) -> None:
    criteria = Criteria.guess(action_)
    assert isinstance(criteria, K8sCriteria)
    assert criteria.action == action_
    assert not attrs.asdict(criteria, filter=lambda a, v: v is not ... and a.name not in {'action'})


# 'delete' is recognized as an HTTP method, not as a K8s action, so we exclude it for now.
@pytest.mark.parametrize('arg, action_', (
    {(a.name.lower(), a) for a in set(action) - {action.DELETE}} |
    {(a.name.upper(), a) for a in set(action) - {action.DELETE}} |
    {(a.name.title(), a) for a in set(action) - {action.DELETE}} |
    {(a.value.lower(), a) for a in set(action) - {action.DELETE}} |
    {(a.value.upper(), a) for a in set(action) - {action.DELETE}} |
    {(a.value.title(), a) for a in set(action) - {action.DELETE}}
))
def test_action_str_guessing(arg: str, action_: action) -> None:
    criteria = Criteria.guess(arg)
    assert isinstance(criteria, K8sCriteria)
    assert criteria.action == action_
    assert not attrs.asdict(criteria, filter=lambda a, v: v is not ... and a.name not in {'action'})


@pytest.mark.parametrize('arg', ['bloop /', 'bloop kopf.dev/v1/kopfexamples'])
def test_nonmethod_nonaction_guessing(arg: str) -> None:
    criteria = Criteria.guess(arg)
    assert not isinstance(criteria, HTTPCriteria)
    assert not isinstance(criteria, K8sCriteria)
    assert isinstance(criteria, StrCriteria)
    assert criteria.value == arg


@pytest.mark.parametrize('arg, expected', [
    (SampleResource('', 'v1', 'pods'), resource(group='', version='v1', plural='pods')),
    (resource('', 'v1', 'pods'), resource(group='', version='v1', plural='pods')),
])
def test_selectable_protocol_guessing(arg: Selectable, expected: resource) -> None:
    criteria = Criteria.guess(arg)
    assert isinstance(criteria, K8sCriteria)
    assert criteria.resource == expected
    assert not attrs.asdict(criteria, filter=lambda a, v: v is not ... and a.name not in {'resource'})


@pytest.mark.parametrize('arg', [
    '/', '/path', '/path/', '/path/subpath',
    re.compile(r'no-slash'),
])
def test_path_guessing(arg: str | re.Pattern[str]) -> None:
    criteria = Criteria.guess(arg)
    assert isinstance(criteria, HTTPCriteria)
    assert criteria.path == arg
    assert not attrs.asdict(criteria, filter=lambda a, v: v is not ... and a.name not in {'path'})


def test_text_guessing() -> None:
    criteria = Criteria.guess('hello')
    assert isinstance(criteria, StrCriteria)
    assert criteria.value == 'hello'


def test_body_guessing() -> None:
    criteria = Criteria.guess(b'hello')
    assert isinstance(criteria, HTTPCriteria)
    assert criteria.body == b'hello'
    assert not attrs.asdict(criteria, filter=lambda a, v: v is not ... and a.name not in {'body'})


def test_dict_guessing() -> None:
    criteria = Criteria.guess({'q': 'query'})
    assert isinstance(criteria, DictCriteria)
    assert criteria.value == {'q': 'query'}


def test_empty_text_guessing() -> None:
    criteria = Criteria.guess('')
    assert criteria is None


def test_empty_dict_guessing() -> None:
    criteria = Criteria.guess({})
    assert criteria is None


def sync_generator() -> Iterator[Any]:
    yield 'item'


async def async_generator() -> AsyncIterator[Any]:
    yield 'item'


@pytest.mark.parametrize('arg', [
    [],
    ['item'],
    (),
    ('item',),
    set(),
    frozenset(),
    {'item'},
    iter(['item']),
    (v for v in ['item']),
    sync_generator(),
    async_generator(),
    sync_generator(),
    async_generator(),
    ZeroDivisionError(),
    SystemExit(),
    aiohttp.web.Response(),
    aiohttp.web.StreamResponse(),
])
def test_unrecognized_criteria(arg: Any) -> None:
    with pytest.raises(ValueError, match=r"Unrecognized criterion type: .*"):
        Criteria.guess(arg)
