from typing import Any

import pytest

import kmock
from kmock import HTTPCriteria, K8sCriteria, action, method, resource

# TODO: we should not normalize anything, because we should not expose these classes to users
#       except for inheritance.
#       if there is any parsing, it should be done via boxes.headers(), etc.


# # Thorough parsing is tested elsewhere. Here, we only smoke-test that it is invoked at all.
# @pytest.mark.parametrize('method_', list(method))
# def test_method_normalization(method_: method) -> None:
#     criteria = HTTPCriteria(method=method_.name.title())
#     assert criteria.method == method_
#
#
# # Thorough parsing is tested elsewhere. Here, we only smoke-test that it is invoked at all.
# @pytest.mark.parametrize('action_', list(action))
# def test_action_normalization(action_: action) -> None:
#     criteria = K8sCriteria(action=action_.name.title())
#     assert criteria.action == action_


# # Thorough parsing is tested elsewhere. Here, we only smoke-test that it is invoked at all.
# @pytest.mark.parametrize('value, expected', [
#     ('pods', resource(plural='pods')),
#     ('pods.v1', resource(group='', version='v1', plural='pods')),
#     ('kopfexamples', resource(plural='kopfexamples')),
#     ('kopfexamples.kopf.dev', resource(group='kopf.dev', plural='kopfexamples')),
#     ('kopfexamples.v2.kopf.dev', resource(group='kopf.dev', version='v2', plural='kopfexamples')),
#     ('kopf.dev/v2/kopfexamples', resource(group='kopf.dev', version='v2', plural='kopfexamples')),
#     ('kopf.dev/kopfexamples', resource(group='kopf.dev', plural='kopfexamples')),
#     ('kopf.dev/v2', resource(group='kopf.dev', version='v2')),
#     ('v1/pods', resource(group='', version='v1', plural='pods')),
#     ('v1', resource(group='', version='v1')),
# ])
# def test_resource_normalization(value: str, expected: resource) -> None:
#     criteria = K8sCriteria(resource=value)
#     assert criteria.resource == expected


# # Thorough parsing is tested elsewhere. Here, we only smoke-test that it is invoked at all.
# @pytest.mark.parametrize('value, expected', [
#     pytest.param({}, {}, id='empty-dict'),
#     pytest.param([], {}, id='empty-list'),
#     pytest.param('?', {}, id='empty-str'),
#     pytest.param(b'', {}, id='empty-bytes'),
#     pytest.param('q=query&empty', {'q': 'query', 'empty': None}, id='str'),
#     pytest.param('??q=query&empty', {'q': 'query', 'empty': None}, id='qstr'),
#     pytest.param(b'q=query&empty', {'q': 'query', 'empty': None}, id='bytes'),
#     pytest.param(b'??q=query&empty', {'q': 'query', 'empty': None}, id='qbytes'),
#     pytest.param({'q': 'query', 'empty': ''}, {'q': 'query', 'empty': ''}, id='dict'),
#     pytest.param([('q', 'query'), ('empty', '')], {'q': 'query', 'empty': ''}, id='pairs'),
# ])
# def test_params_normalization(value: Any, expected: Any) -> None:
#     criteria = HTTPCriteria(params=value)
#     assert criteria.params == expected


# # Thorough parsing is tested elsewhere. Here, we only smoke-test that it is invoked at all.
# @pytest.mark.parametrize('value, expected', [
#     pytest.param({}, {}, id='empty-dict'),
#     pytest.param([], {}, id='empty-list'),
#     pytest.param('', {}, id='empty-str'),
#     pytest.param(b'', {}, id='empty-bytes'),
#     pytest.param('\n \n\n ', {}, id='spaced-str'),
#     pytest.param(b'\n \n\n ', {}, id='spaced-bytes'),
#     pytest.param('H1: value1\n', {'H1': 'value1'}, id='newline-end'),
#     pytest.param('\nH1: value1', {'H1': 'value1'}, id='newline-start'),
#     pytest.param('H1: value1\nH2: value2', {'H1': 'value1', 'H2': 'value2'}, id='newline-middle'),
#     pytest.param('Content-Type: plain/text', {'Content-Type': 'plain/text'}, id='str'),
#     pytest.param({'Content-Type': 'plain/text'}, {'Content-Type': 'plain/text'}, id='dict'),
#     pytest.param([('Content-Type', 'plain/text')], {'Content-Type': 'plain/text'}, id='pairs'),
# ])
# def test_headers_normalization(value: Any, expected: Any) -> None:
#     criteria = HTTPCriteria(headers=value)
#     assert criteria.headers == expected


# # Thorough parsing is tested elsewhere. Here, we only smoke-test that it is invoked at all.
# @pytest.mark.parametrize('value, expected', [
#     pytest.param({}, {}, id='empty-dict'),
#     pytest.param([], {}, id='empty-list'),
#     pytest.param({'session': 'sid1'}, {'session': 'sid1'}, id='dict'),
#     pytest.param([('session', 'sid1')], {'session': 'sid1'}, id='pairs'),
# ])
# def test_cookies_normalization(value: Any, expected: Any) -> None:
#     criteria = HTTPCriteria(cookies=value)
#     assert criteria.cookies == expected


# TODO: body, text, data normalization in HTTPCriteria
