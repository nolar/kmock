from unittest.mock import Mock

import aiohttp
import pytest
import pytest_asyncio
from aiohttp.test_utils import make_mocked_request

from kmock import Request, action, method


@pytest_asyncio.fixture()
async def payload() -> aiohttp.StreamReader:
    protocol = Mock()
    payload = aiohttp.StreamReader(protocol, 2 ** 16)
    return payload


async def test_unknown_method(payload: aiohttp.StreamReader) -> None:
    payload.feed_eof()
    raw = make_mocked_request('UNKNOWN', '/', payload=payload)
    request = await Request._parse(raw)
    assert isinstance(request.method, str)
    assert request.method == 'UNKNOWN'


@pytest.mark.parametrize('method_', [m.value.title() for m in method] + [m.value.lower() for m in method])
@pytest.mark.parametrize('url', ['/', '/path', '/path/subpath'])
async def test_method_path_url(payload: aiohttp.StreamReader, method_: str, url: str) -> None:
    payload.feed_eof()
    raw = make_mocked_request(method_, url, payload=payload)
    request = await Request._parse(raw)
    assert isinstance(request.method, method)
    assert isinstance(request.method, str)
    assert request.method.value == method_.upper()
    assert request.method == method_.upper()
    assert request.url.path == url


@pytest.mark.parametrize('method_', [m.value for m in method])
async def test_params(payload: aiohttp.StreamReader, method_: str) -> None:
    payload.feed_eof()
    raw = make_mocked_request(method_, '/?q=query&watch=true', payload=payload)
    request = await Request._parse(raw)
    assert request.params == {'q': 'query', 'watch': 'true'}
    assert request.url.query == {'q': 'query', 'watch': 'true'}


@pytest.mark.parametrize('method_', [m.value for m in method])
async def test_headers(payload: aiohttp.StreamReader, method_: str) -> None:
    payload.feed_eof()
    headers = {'X-Custom': 'hello', 'Content-Type': 'text/plain'}
    raw = make_mocked_request(method_, '/?q=query&watch=true', headers, payload=payload)
    request = await Request._parse(raw)
    assert request.headers['X-Custom'] == 'hello'
    assert request.headers['Content-Type'] == 'text/plain'


@pytest.mark.parametrize('method_', [m.value for m in method])
async def test_payload_json(payload: aiohttp.StreamReader, method_: str) -> None:
    payload.feed_data(b'{"hello": "world"}')
    payload.feed_eof()
    raw = make_mocked_request(method_, '/', payload=payload)
    request = await Request._parse(raw)
    assert request.data == {"hello": "world"}
    assert request.text == '{"hello": "world"}'
    assert request.body == b'{"hello": "world"}'


@pytest.mark.parametrize('method_', ['PUT', 'PATCH', 'POST', 'DELETE'])  # only the post-methods!
async def test_payload_form(payload: aiohttp.StreamReader, method_: str) -> None:
    payload.feed_data(b'hello=world')
    payload.feed_eof()
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}  # otherwise ignored by aiohttp
    raw = make_mocked_request(method_, '/', payload=payload, headers=headers)
    request = await Request._parse(raw)
    assert request.data == {"hello": "world"}
    assert request.text == 'hello=world'
    assert request.body == b'hello=world'


@pytest.mark.parametrize('method_', ['PUT', 'PATCH', 'POST', 'DELETE'])  # only the post-methods!
async def test_payload_form_corrupted(payload: aiohttp.StreamReader, method_: str) -> None:
    payload.feed_data(b'hello=world')  # NB: does not match the content type!
    payload.feed_eof()
    headers = {'Content-Type': 'multipart/form-data'}  # otherwise ignored by aiohttp
    raw = make_mocked_request(method_, '/', payload=payload, headers=headers)
    request = await Request._parse(raw)
    assert request.data is None
    assert request.text == 'hello=world'
    assert request.body == b'hello=world'


@pytest.mark.parametrize('method_', [m.value for m in method])
async def test_payload_text(payload: aiohttp.StreamReader, method_: str) -> None:
    payload.feed_data(b'Hello, world!')
    payload.feed_eof()
    raw = make_mocked_request(method_, '/', payload=payload)
    request = await Request._parse(raw)
    assert request.data is None
    assert request.text == 'Hello, world!'
    assert request.body == b'Hello, world!'


@pytest.mark.parametrize('method_', [m.value for m in method])
@pytest.mark.parametrize('url', [
    '/api/v1/pods',
    '/api/v1/pods/n1',
    '/api/v1/pods/n1/status',
    '/api/v1/pods/n1/sub/res',
    '/api/v1/namespaces/ns1/pods',
    '/api/v1/namespaces/ns1/pods/n1',
    '/api/v1/namespaces/ns1/pods/n1/status',
    '/api/v1/namespaces/ns1/pods/n1/sub/res',
    '/apis/kopf.dev/v1/kopfexamples',
    '/apis/kopf.dev/v1/kopfexamples/n1',
    '/apis/kopf.dev/v1/kopfexamples/n1/status',
    '/apis/kopf.dev/v1/kopfexamples/n1/sub/res',
    '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples',
    '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/n1',
    '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/n1/status',
    '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/n1/sub/res',
])
async def test_k8s_url_with_params_is_parsed_the_same(payload: aiohttp.StreamReader, method_: str, url: str) -> None:
    payload.feed_eof()
    raw1 = make_mocked_request(method_, url, payload=payload)
    raw2 = make_mocked_request(method_, url + '/?q=query', payload=payload)
    request1 = await Request._parse(raw1)
    request2 = await Request._parse(raw2)
    assert request1.action == request2.action
    assert request1.resource == request2.resource
    assert request1.resource == request2.resource
    assert request1.namespace == request2.namespace
    assert request1.clusterwide == request2.clusterwide
    assert request1.subresource == request2.subresource
    assert request1.name == request2.name


@pytest.mark.parametrize('url', [
    '/api/v1/pods',
    '/api/v1/pods/n1',
    '/api/v1/pods/n1/status',
    '/api/v1/pods/n1/sub/res',
    '/api/v1/namespaces/ns1/pods',
    '/api/v1/namespaces/ns1/pods/n1',
    '/api/v1/namespaces/ns1/pods/n1/status',
])
async def test_k8s_apiv1_resource_detection(payload: aiohttp.StreamReader, url: str) -> None:
    payload.feed_eof()
    raw = make_mocked_request('GET', url, payload=payload)
    request = await Request._parse(raw)
    assert request.resource is not None
    assert request.resource.group == ''
    assert request.resource.version == 'v1'
    assert request.resource.plural == 'pods'
    assert request.resource is not None
    assert request.resource.group == ''
    assert request.resource.version == 'v1'
    assert request.resource.plural == 'pods'


@pytest.mark.parametrize('url', [
    '/apis/kopf.dev/v1/kopfexamples',
    '/apis/kopf.dev/v1/kopfexamples/n1',
    '/apis/kopf.dev/v1/kopfexamples/n1/status',
    '/apis/kopf.dev/v1/kopfexamples/n1/sub/res',
    '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples',
    '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/n1',
    '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/n1/status',
    '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/n1/sub/res',
])
async def test_k8s_apis_resource_detection(payload: aiohttp.StreamReader, url: str) -> None:
    payload.feed_eof()
    raw = make_mocked_request('GET', url, payload=payload)
    request = await Request._parse(raw)
    assert request.resource is not None
    assert request.resource.group == 'kopf.dev'
    assert request.resource.version == 'v1'
    assert request.resource.plural == 'kopfexamples'
    assert request.resource is not None
    assert request.resource.group == 'kopf.dev'
    assert request.resource.version == 'v1'
    assert request.resource.plural == 'kopfexamples'


@pytest.mark.parametrize('url, clusterwide, namespace, name, subresource', [
    ('/api/v1/pods', True, None, None, None),
    ('/api/v1/pods/n1', True, None, 'n1', None),
    ('/api/v1/pods/n1/status', True, None, 'n1', 'status'),
    ('/api/v1/pods/n1/sub/res', True, None, 'n1', 'sub/res'),
    ('/api/v1/namespaces/ns1/pods', False, 'ns1', None, None),
    ('/api/v1/namespaces/ns1/pods/n1', False, 'ns1', 'n1', None),
    ('/api/v1/namespaces/ns1/pods/n1/status', False, 'ns1', 'n1', 'status'),
    ('/api/v1/namespaces/ns1/pods/n1/sub/res', False, 'ns1', 'n1', 'sub/res'),
    ('/apis/kopf.dev/v1/kopfexamples', True, None, None, None),
    ('/apis/kopf.dev/v1/kopfexamples/n1', True, None, 'n1', None),
    ('/apis/kopf.dev/v1/kopfexamples/n1/status', True, None, 'n1', 'status'),
    ('/apis/kopf.dev/v1/kopfexamples/n1/sub/res', True, None, 'n1', 'sub/res'),
    ('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples', False, 'ns1', None, None),
    ('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/n1', False, 'ns1', 'n1', None),
    ('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/n1/status', False, 'ns1', 'n1', 'status'),
    ('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/n1/sub/res', False, 'ns1', 'n1', 'sub/res'),
])
async def test_k8s_locality(payload: aiohttp.StreamReader, url: str, clusterwide: bool,
                            namespace: str | None, name: str | None, subresource: str | None) -> None:
    payload.feed_eof()
    raw = make_mocked_request('GET', url, payload=payload)
    request = await Request._parse(raw)
    assert request.clusterwide == clusterwide
    assert request.namespace == namespace
    assert request.subresource == subresource
    assert request.name == name


@pytest.mark.parametrize('action_, method_, url', [
    (action.LIST, 'GET', '/api/v1/pods'),
    (action.LIST, 'GET', '/api/v1/namespaces/ns1/pods'),
    (action.LIST, 'GET', '/apis/kopf.dev/v1/kopfexamples'),
    (action.LIST, 'GET', '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples'),
    (action.WATCH, 'GET', '/api/v1/pods?watch=true'),
    (action.WATCH, 'GET', '/api/v1/namespaces/ns1/pods?watch=true'),
    (action.WATCH, 'GET', '/apis/kopf.dev/v1/kopfexamples?watch=true'),
    (action.WATCH, 'GET', '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples?watch=true'),
    (action.FETCH, 'GET', '/api/v1/pods/n1'),
    (action.FETCH, 'GET', '/api/v1/namespaces/ns1/pods/n1'),
    (action.FETCH, 'GET', '/apis/kopf.dev/v1/kopfexamples/n1'),
    (action.FETCH, 'GET', '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/n1'),
    (action.CREATE, 'POST', '/api/v1/pods'),
    (action.CREATE, 'POST', '/api/v1/namespaces/ns1/pods'),
    (action.CREATE, 'POST', '/apis/kopf.dev/v1/kopfexamples'),
    (action.CREATE, 'POST', '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples'),
    (action.UPDATE, 'PATCH', '/api/v1/pods/n1'),
    (action.UPDATE, 'PATCH', '/api/v1/namespaces/ns1/pods/n1'),
    (action.UPDATE, 'PATCH', '/apis/kopf.dev/v1/kopfexamples/n1'),
    (action.UPDATE, 'PATCH', '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/n1'),
    (action.DELETE, 'DELETE', '/api/v1/pods/n1'),
    (action.DELETE, 'DELETE', '/api/v1/namespaces/ns1/pods/n1'),
    (action.DELETE, 'DELETE', '/apis/kopf.dev/v1/kopfexamples/n1'),
    (action.DELETE, 'DELETE', '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/n1'),
    (None, 'POST', '/api/v1/pods/n1'),
    (None, 'POST', '/api/v1/namespaces/ns1/pods/n1'),
    (None, 'POST', '/apis/kopf.dev/v1/kopfexamples/n1'),
    (None, 'POST', '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/n1'),
    (None, 'PATCH', '/api/v1/pods'),
    (None, 'PATCH', '/api/v1/namespaces/ns1/pods'),
    (None, 'PATCH', '/apis/kopf.dev/v1/kopfexamples'),
    (None, 'PATCH', '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples'),
    (None, 'DELETE', '/api/v1/pods'),
    (None, 'DELETE', '/api/v1/namespaces/ns1/pods'),
    (None, 'DELETE', '/apis/kopf.dev/v1/kopfexamples'),
    (None, 'DELETE', '/apis/kopf.dev/v1/namespaces/ns1/kopfexamples'),
])
async def test_k8s_action(payload: aiohttp.StreamReader, method_: str, url: str, action_: action | None) -> None:
    payload.feed_eof()
    raw = make_mocked_request(method_, url, payload=payload)
    request = await Request._parse(raw)
    assert request.action == action_


async def test_k8s_absent_for_http(payload: aiohttp.StreamReader) -> None:
    payload.feed_eof()
    raw = make_mocked_request('GET', '/', payload=payload)
    request = await Request._parse(raw)
    assert request.action is None
    assert request.name is None
    assert request.subresource is None
    assert request.clusterwide is None
    assert request.namespace is None
    assert request.resource is None
    assert request.resource is None
