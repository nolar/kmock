from typing import Any

import attrs
import pytest

from kmock import Criteria, HTTPCriteria, K8sCriteria, action, method, resource


@pytest.mark.parametrize('arg, method_, path, params', [
    # Single method/path/query:
    ('get', method.GET, None, None),
    ('/', None, '/', None),
    ('/path', None, '/path', None),
    ('?q=query', None, None, {'q': 'query'}),

    # Method-path-query combinations:
    ('/?', None, '/', None),
    ('get /', method.GET, '/', None),
    ('get /?', method.GET, '/', None),
    ('get ?q=query', method.GET, None, {'q': 'query'}),
    ('get /?q=query', method.GET, '/', {'q': 'query'}),
    ('/path?q=query', None, '/path', {'q': 'query'}),

    # All other methods:
    ('get /path', method.GET, '/path', None),
    ('put /path', method.PUT, '/path', None),
    ('post /path', method.POST, '/path', None),
    ('patch /path', method.PATCH, '/path', None),
    ('delete /path', method.DELETE, '/path', None),

    # Extra spaces are ignored when not part of path/params.
    ('  get  ', method.GET, None, None),
    ('  /  ', None, '/', None),
    ('delete   /path', method.DELETE, '/path', None),
])
def test_http_notation(arg: str, method_: method | None, path: str | None, params: Any) -> None:
    criteria = Criteria.guess(arg)
    assert isinstance(criteria, HTTPCriteria)
    assert criteria.method == method_
    assert criteria.path == path
    assert criteria.params == params
    assert not attrs.asdict(criteria, filter=lambda a, v: v is not None and a.name not in {'path', 'method', 'params'})


@pytest.mark.parametrize('arg, action_, resource_', [
    # Single action.
    ('list', action.LIST, None),
    ('watch', action.WATCH, None),
    ('fetch', action.FETCH, None),
    ('create', action.CREATE, None),
    ('update', action.UPDATE, None),
    # ('deletion', action.DELETE, None),

    # action-resource combinations (NB: it uses "any name", not "plural").
    # Note: standalone resources are not easy to recognize, so we do not try.
    ('list pods', action.LIST, resource('pods')),
    ('list kopfexamples', action.LIST, resource('kopfexamples')),
    ('list pods.v1', action.LIST, resource('', 'v1', 'pods')),
    ('list v1/pods', action.LIST, resource('', 'v1', 'pods')),
    ('list kopfexamples.v1.kopf.dev', action.LIST, resource('kopf.dev', 'v1', 'kopfexamples')),
    ('list kopf.dev/v1/kopfexamples', action.LIST, resource('kopf.dev', 'v1', 'kopfexamples')),
    ('list kopf.dev/v1', action.LIST, resource(group='kopf.dev', version='v1')),

    # All other methods:
    ('watch pods.v1', action.WATCH, resource('', 'v1', 'pods')),
    ('fetch pods.v1', action.FETCH, resource('', 'v1', 'pods')),
    ('create pods.v1', action.CREATE, resource('', 'v1', 'pods')),
    ('update pods.v1', action.UPDATE, resource('', 'v1', 'pods')),
    ('delete pods.v1', action.DELETE, resource('', 'v1', 'pods')),

    # Extra spaces are ignored when not part of recognized elements.
    ('  list  ', action.LIST, None),
    ('  watch  ', action.WATCH, None),
    ('create   pods.v1', action.CREATE, resource('', 'v1', 'pods')),
    ('delete   pods.v1', action.DELETE, resource('', 'v1', 'pods')),
])
def test_k8s_notation(arg: str, action_: action | None, resource_: resource | None) -> None:
    criteria = Criteria.guess(arg)
    assert isinstance(criteria, K8sCriteria)
    assert criteria.action == action_
    assert criteria.resource == resource_
    assert not attrs.asdict(criteria, filter=lambda a, v: v is not None and a.name not in {'action', 'resource'})
