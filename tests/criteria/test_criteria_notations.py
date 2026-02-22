from types import EllipsisType
from typing import Any

import attrs
import pytest

from kmock import Criteria, HTTPCriteria, K8sCriteria, action, method, resource


@pytest.mark.parametrize('arg, method_, path, params', [
    # Single method/path/query:
    ('get', method.GET, ..., ...),
    ('/', ..., '/', ...),
    ('/path', ..., '/path', ...),
    ('?q=query', ..., ..., {'q': 'query'}),

    # Method-path-query combinations:
    ('/?', ..., '/', ...),
    ('get /', method.GET, '/', ...),
    ('get /?', method.GET, '/', ...),
    ('get ?q=query', method.GET, ..., {'q': 'query'}),
    ('get /?q=query', method.GET, '/', {'q': 'query'}),
    ('/path?q=query', ..., '/path', {'q': 'query'}),

    # All other methods:
    ('get /path', method.GET, '/path', ...),
    ('put /path', method.PUT, '/path', ...),
    ('post /path', method.POST, '/path', ...),
    ('patch /path', method.PATCH, '/path', ...),
    ('delete /path', method.DELETE, '/path', ...),

    # Extra spaces are ignored when not part of path/params.
    ('  get  ', method.GET, ..., ...),
    ('  /  ', ..., '/', ...),
    ('delete   /path', method.DELETE, '/path', ...),
])
def test_http_notation(arg: str, method_: method | EllipsisType, path: str | EllipsisType, params: Any) -> None:
    criteria = Criteria.guess(arg)
    assert isinstance(criteria, HTTPCriteria)
    assert criteria.method == method_
    assert criteria.path == path
    assert criteria.params == params
    assert not attrs.asdict(criteria, filter=lambda a, v: v is not ... and a.name not in {'path', 'method', 'params'})


@pytest.mark.parametrize('arg, method_, action_, resource_', [
    # Single action.
    ('list', ..., action.LIST, ...),
    ('watch', ..., action.WATCH, ...),
    ('fetch', ..., action.FETCH, ...),
    ('create', ..., action.CREATE, ...),
    ('update', ..., action.UPDATE, ...),
    # ('deletion', ..., action.DELETE, ...),

    # action-resource combinations (NB: it uses "any name", not "plural").
    # Note: standalone resources are not easy to recognize, so we do not try.
    ('list pods', ..., action.LIST, resource('pods')),
    ('list kopfexamples', ..., action.LIST, resource('kopfexamples')),
    ('list pods.v1', ..., action.LIST, resource('', 'v1', 'pods')),
    ('list v1/pods', ..., action.LIST, resource('', 'v1', 'pods')),
    ('list kopfexamples.v1.kopf.dev', ..., action.LIST, resource('kopf.dev', 'v1', 'kopfexamples')),
    ('list kopf.dev/v1/kopfexamples', ..., action.LIST, resource('kopf.dev', 'v1', 'kopfexamples')),
    ('list kopf.dev/v1', ..., action.LIST, resource(group='kopf.dev', version='v1')),

    # All other methods and actions:
    ('get pods.v1', method.GET, ..., resource('', 'v1', 'pods')),
    ('put pods.v1', method.PUT, ..., resource('', 'v1', 'pods')),
    ('head pods.v1', method.HEAD, ..., resource('', 'v1', 'pods')),
    ('post pods.v1', method.POST, ..., resource('', 'v1', 'pods')),
    ('patch pods.v1', method.PATCH, ..., resource('', 'v1', 'pods')),
    ('options pods.v1', method.OPTIONS, ..., resource('', 'v1', 'pods')),
    ('watch pods.v1', ..., action.WATCH, resource('', 'v1', 'pods')),
    ('fetch pods.v1', ..., action.FETCH, resource('', 'v1', 'pods')),
    ('create pods.v1', ..., action.CREATE, resource('', 'v1', 'pods')),
    ('update pods.v1', ..., action.UPDATE, resource('', 'v1', 'pods')),
    ('delete pods.v1', method.DELETE, action.DELETE, resource('', 'v1', 'pods')),

    # Extra spaces are ignored when not part of recognized elements.
    ('  list  ', ..., action.LIST, ...),
    ('  watch  ', ..., action.WATCH, ...),
    ('create   pods.v1', ..., action.CREATE, resource('', 'v1', 'pods')),
    ('delete   pods.v1', method.DELETE, action.DELETE, resource('', 'v1', 'pods')),
])
def test_k8s_notation(arg: str, method_: method | EllipsisType, action_: action | EllipsisType, resource_: resource | None) -> None:
    criteria = Criteria.guess(arg)
    assert isinstance(criteria, K8sCriteria)
    assert criteria.method == method_
    assert criteria.action == action_
    assert criteria.resource == resource_
    assert not attrs.asdict(criteria, filter=lambda a, v: v is not ... and a.name not in {'method', 'action', 'resource'})
