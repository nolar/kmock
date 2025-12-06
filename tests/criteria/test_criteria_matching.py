"""
Note there is another `test_matching.py` — for actual requests received
from a server and parsed. But it is not as verbose as this in-memory matching
with all possible combinations and edge cases.
"""
import re
from typing import Any

import attrs
import pytest

from kmock import DictCriteria, HTTPCriteria, K8sCriteria, Request, Selectable, StrCriteria, action, method, resource


@attrs.frozen
class SampleResource(Selectable):
    group: str
    version: str
    plural: str


@pytest.mark.parametrize('method, data, text, expected', [
    pytest.param('get', None, None, True, id='method-true'),
    pytest.param('put', None, None, False, id='method-false'),
    pytest.param(None, 'get', None, True, id='data-true'),
    pytest.param(None, 'put', None, False, id='data-false'),
    pytest.param(None, None, 'get', True, id='data-true'),
    pytest.param(None, None, 'put', False, id='data-false'),
    pytest.param(None, None, None, False, id='generic-false'),
])
def test_str_criteria(method: Any, data: Any, text: Any, expected: bool) -> None:
    request = Request(method=method, data=data, text=text, body=b'unrelated')
    criteria = StrCriteria('get')
    assert criteria(request) == expected


@pytest.mark.parametrize('headers, cookies, params, data, expected', [
    pytest.param({'x': 'y'}, None, None, None, True, id='headers-true'),
    pytest.param({'x': 'z'}, None, None, None, False, id='headers-false'),
    pytest.param(None, {'x': 'y'}, None, None, True, id='cookies-true'),
    pytest.param(None, {'x': 'z'}, None, None, False, id='cookies-false'),
    pytest.param(None, None, {'x': 'y'}, None, True, id='params-true'),
    pytest.param(None, None, {'x': 'z'}, None, False, id='params-false'),
    pytest.param(None, None, None, {'x': 'y'}, True, id='data-true'),
    pytest.param(None, None, None, {'x': 'z'}, False, id='data-false'),
    pytest.param(None, None, None, None, False, id='generic-false'),
])
def test_dict_criteria(headers: Any, cookies: Any, params: Any, data: Any, expected: bool) -> None:
    request = Request(headers=headers, cookies=cookies, params=params, data=data, body=b'unrelated')
    criteria = DictCriteria({'x': 'y'})
    assert criteria(request) == expected


# Test it all at once here, so that we have no need to test it in every test below.
@pytest.mark.parametrize('data', [None, [], {'key': 'val'}])
@pytest.mark.parametrize('text', [None, '', 'hello'])
@pytest.mark.parametrize('body', [None, b'', b'hello'])
@pytest.mark.parametrize('headers', [{}, {'X-Header': 'val'}])
@pytest.mark.parametrize('params', [{}, {'q': 'query'}])
@pytest.mark.parametrize('url', ['', '/', '/path'])
@pytest.mark.parametrize('method_', list(method))
def test_catchall_http(method_: Any, url: Any, params: Any, headers: Any, body: Any, text: Any, data: Any) -> None:
    request = Request(method=method_, url=url, params=params, headers=headers, body=body, text=text, data=data)
    criteria = HTTPCriteria()
    assert criteria(request)


@pytest.mark.parametrize('subresource', [None, 'status', 'subresource'])
@pytest.mark.parametrize('name', [None, 'n1', 'n2'])
@pytest.mark.parametrize('namespace', [None, 'ns1', 'ns2'])
@pytest.mark.parametrize('resource_', [None, resource('kopf.dev', 'v1', 'kopfexamples'), resource('', 'v1', 'pods')])
@pytest.mark.parametrize('action_', [None] + list(action))
def test_catchall_k8s(action_: Any, resource_: Any, namespace: Any, name: Any, subresource: Any) -> None:
    request = Request(action=action_, resource=resource_, namespace=namespace, name=name, subresource=subresource)
    criteria = K8sCriteria()
    assert criteria(request)


@pytest.mark.parametrize('requested, pattern', [
    (req_method, pat_method) for req_method in method for pat_method in method if req_method != pat_method
])
def test_method_mismatching(requested: method, pattern: method) -> None:
    request = Request(method=requested)
    criteria = HTTPCriteria(method=pattern)
    assert not criteria(request)


@pytest.mark.parametrize('method_', list(method))
def test_method_requirement(method_: method) -> None:
    request = Request()
    criteria = HTTPCriteria(method=method_)
    assert not criteria(request)


@pytest.mark.parametrize('method_', list(method))
def test_method_matching(method_: method) -> None:
    request = Request(method=method_)
    criteria = HTTPCriteria(method=method_)
    assert criteria(request)


@pytest.mark.parametrize('requested, pattern', [
    (req_action, pat_action) for req_action in action for pat_action in action if req_action != pat_action
])
def test_action_mismatching(requested: action, pattern: action) -> None:
    request = Request(action=requested)
    criteria = K8sCriteria(action=pattern)
    assert not criteria(request)


@pytest.mark.parametrize('action_', list(action))
def test_action_requirement(action_: action) -> None:
    request = Request()
    criteria = K8sCriteria(action=action_)
    assert not criteria(request)


@pytest.mark.parametrize('action_', list(action))
def test_action_matching(action_: action) -> None:
    request = Request(action=action_)
    criteria = K8sCriteria(action=action_)
    assert criteria(request)


@pytest.mark.parametrize('requested, pattern, expected', [
    ('', '/', False),
    ('/', None, True),
    ('/', '/', True),
    ('/path', '/', False),
    ('/', '/path', False),
    ('/path', '/path', True),
    ('path', 'path', True),  # we use explicit kwargs
    ('/path', re.compile('/'), False),
    ('/', re.compile('/path'), False),
    ('/', re.compile('/.*'), True),
    ('/path', re.compile('/.*'), True),
    ('/path', re.compile('/.*/'), False),
    ('/path/', re.compile('/.*/'), True),
])
def test_path_matching(requested: str, pattern: Any, expected: bool) -> None:
    request = Request(url=requested)
    criteria = HTTPCriteria(path=pattern)
    result = criteria(request)
    assert result == expected


@pytest.mark.parametrize('requested, pattern, expected', [
    ({'q': 'query', 'extra': ''}, None, True),
    ({'q': 'query', 'extra': ''}, {'q': 'query'}, True),
    ({'q': 'query'}, {'q': 'query'}, True),
    ({'q': 'query'}, {'q': 'wrong'}, False),
    ({'q': 'query'}, {}, True),
    ({}, {'q': 'query'}, False),
])
def test_params_matching(requested: dict[str, str], pattern: Any, expected: bool) -> None:
    request = Request(params=requested)
    criteria = HTTPCriteria(params=pattern)
    result = criteria(request)
    assert result == expected


@pytest.mark.parametrize('requested, pattern, expected', [
    ({'Content-Type': 'text/plain', 'extra': ''}, None, True),
    ({'Content-Type': 'text/plain', 'extra': ''}, {'Content-Type': 'text/plain'}, True),
    ({'Content-Type': 'text/plain'}, {'Content-Type': 'text/plain'}, True),
    ({'Content-Type': 'text/plain'}, {'Content-Type': 'application/json'}, False),
    ({'Content-Type': 'text/plain'}, {}, True),
    ({}, {'Content-Type': 'text/plain'}, False),
])
def test_headers_matching(requested: dict[str, str], pattern: Any, expected: bool) -> None:
    request = Request(headers=requested)
    criteria = HTTPCriteria(headers=pattern)
    result = criteria(request)
    assert result == expected


@pytest.mark.parametrize('requested, pattern, expected', [
    ({'session': 'sid', 'extra': ''}, None, True),
    ({'session': 'sid', 'extra': ''}, {'session': 'sid'}, True),
    ({'session': 'sid'}, {'session': 'sid'}, True),
    ({'session': 'sid'}, {'session': 'some-other-sid'}, False),
    ({'session': 'sid'}, {}, True),
    ({}, {'session': 'sid'}, False),
])
def test_cookies_matching(requested: dict[str, str], pattern: Any, expected: bool) -> None:
    request = Request(cookies=requested)
    criteria = HTTPCriteria(cookies=pattern)
    result = criteria(request)
    assert result == expected


@pytest.mark.parametrize('requested, pattern, expected', [
    (None, None, True),
    (None, {}, False),
    (None, [], False),
    ({'key': 'val'}, {}, True),
    ({'key': 'val'}, {'key': 'val'}, True),
    ({'key': 'val'}, {'key': 'bad'}, False),
    ({'key': 'val', 'extra': ''}, None, True),
    ({'key': 'val', 'extra': ''}, {'key': 'val'}, True),
    ({}, {'key': 'val'}, False),
])
def test_data_matching(requested: Any, pattern: Any, expected: bool) -> None:
    request = Request(data=requested)
    criteria = HTTPCriteria(data=pattern)
    result = criteria(request)
    assert result == expected


@pytest.mark.parametrize('requested, pattern, expected', [
    (None, None, True),
    (None, 'hello', False),
    ('hello', None, True),
    ('hello', 'hello', True),
    ('hello', '', False),
    ('', 'hello', False),
    ('hello', re.compile('hell'), False),
    ('hello', re.compile('he.*'), True),
])
def test_text_matching(requested: Any, pattern: Any, expected: bool) -> None:
    request = Request(text=requested)
    criteria = HTTPCriteria(text=pattern)
    result = criteria(request)
    assert result == expected


@pytest.mark.parametrize('requested, pattern, expected', [
    (None, None, True),
    (None, b'hello', False),
    (b'hello', None, True),
    (b'hello', b'hello', True),
    (b'hello', b'', False),
    (b'', b'hello', False),
    (b'hello', re.compile(b'hell'), False),
    (b'hello', re.compile(b'he.*'), True),
])
def test_body_matching(requested: Any, pattern: Any, expected: bool) -> None:
    request = Request(body=requested)
    criteria = HTTPCriteria(body=pattern)
    result = criteria(request)
    assert result == expected


@pytest.mark.parametrize('requested, pattern, expected', [
    (None, None, True),
    (None, resource(), False),
    (SampleResource('', 'v1', 'pods'), None, True),
    (SampleResource('', 'v1', 'pods'), resource('', 'v1', 'pods'), True),
    (SampleResource('', 'v1', 'pods'), resource('', 'v1', 'jobs'), False),
    (SampleResource('kopf.dev', 'v1', 'pods'), resource('', 'v1', 'pods'), False),
    (SampleResource('', 'v1', 'pods'), resource(plural='pods'), True),
    (SampleResource('kopf.dev', 'v1', 'pods'), resource(plural='pods'), True),
    (SampleResource('', 'v1', 'pods'), resource(), True),
    (SampleResource('kopf.dev', 'v1', 'pods'), resource(), True),
])
def test_resource_matching(requested: Any, pattern: Any, expected: bool) -> None:
    request = Request(resource=requested)
    criteria = K8sCriteria(resource=pattern)
    result = criteria(request)
    assert result == expected


@pytest.mark.parametrize('requested, pattern, expected', [
    (None, None, True),
    (None, 'ns', False),
    ('ns', None, True),
    ('ns', 'ns', True),
    ('ns', 'n*', True),
    ('ns', 'n?', True),
    ('ns', 'xy', False),
    ('NS', 'ns', False),
    ('NS', re.compile('ns', re.I), True),
    ('NS', re.compile('n.*', re.I), True),
    ('NS', re.compile('xy', re.I), False),
])
def test_namespace_matching(requested: Any, pattern: Any, expected: bool) -> None:
    request = Request(namespace=requested)
    criteria = K8sCriteria(namespace=pattern)
    result = criteria(request)
    assert result == expected


@pytest.mark.parametrize('requested, pattern, expected', [
    (None, None, True),
    (None, 'name', False),
    ('name', None, True),
    ('name', 'name', True),
    ('name', 'nam*', True),
    ('name', 'nam?', True),
    ('name', 'xyxy', False),
    ('NAME', 'name', False),
    ('NAME', re.compile('name', re.I), True),
    ('NAME', re.compile('na.*', re.I), True),
    ('NAME', re.compile('na', re.I), False),
])
def test_name_matching(requested: Any, pattern: Any, expected: bool) -> None:
    request = Request(name=requested)
    criteria = K8sCriteria(name=pattern)
    result = criteria(request)
    assert result == expected


@pytest.mark.parametrize('requested, pattern, expected', [
    (None, None, True),
    (None, 'status', False),
    ('status', None, True),
    ('status', 'status', True),
    ('status', 'replicas', False),
    ('STATUS', 'status', False),
    ('STATUS', re.compile('status', re.I), True),
    ('STATUS', re.compile('sta.*', re.I), True),
    ('STATUS', re.compile('sta', re.I), False),
])
def test_subresource_matching(requested: Any, pattern: Any, expected: bool) -> None:
    request = Request(subresource=requested)
    criteria = K8sCriteria(subresource=pattern)
    result = criteria(request)
    assert result == expected


@pytest.mark.parametrize('requested, pattern, expected', [
    (None, None, True),
    (None, True, False),
    (None, False, False),
    (True, None, True),
    (True, True, True),
    (True, False, False),
    (False, None, True),
    (False, True, False),
    (False, False, True),
])
def test_clusterwide_matching(requested: Any, pattern: Any, expected: bool) -> None:
    request = Request(clusterwide=requested)
    criteria = K8sCriteria(clusterwide=pattern)
    result = criteria(request)
    assert result == expected
