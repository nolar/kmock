from typing import Any

import pytest

import kmock
from kmock import Criteria, HTTPCriteria, K8sCriteria, action, method


@pytest.fixture(params=['module', 'handler'])
def src(request) -> Any:
    if request.param == 'module':
        return kmock
    elif request.param == 'handler':
        return kmock.RawHandler()
    else:
        raise ValueError("Unsupported source for kmock namespace.")


@pytest.mark.parametrize('arg', [
    pytest.param(123, id='int'),
    pytest.param('hello', id='str'),
    pytest.param([], id='list-empty'),
    pytest.param(['item'], id='list-filled'),
    pytest.param({}, id='dict-empty'),
    pytest.param({'key': 'value'}, id='dict-filled'),
    pytest.param({'X-Custom': 'blah'}, id='fake-headers1'),
    pytest.param({'Content-Type': 'application/json'}, id='fake-headers2'),
    pytest.param('get', id='fake-method'),
    pytest.param('list', id='fake-action'),
    pytest.param('/path', id='fake-path'),
    pytest.param('?q=query', id='fake-query'),
    pytest.param('get /path?q=query', id='fake-http'),
])
async def test_forced_data(src: Any, arg: Any) -> None:
    criteria = Criteria.guess(src.data(arg))
    assert isinstance(criteria, HTTPCriteria)
    assert criteria.data == arg
    assert criteria.params is ...
    assert criteria.headers is ...
    assert criteria.cookies is ...
    assert criteria.method is ...
    assert criteria.path is ...


async def test_forced_params(src: Any) -> None:
    criteria = Criteria.guess(src.params({'Content-Type': 'application/json'}))
    assert isinstance(criteria, HTTPCriteria)
    assert criteria.params == {'Content-Type': 'application/json'}
    assert criteria.headers is ...
    assert criteria.cookies is ...
    assert criteria.data is ...


async def test_forced_headers(src: Any) -> None:
    criteria = Criteria.guess(src.headers({'NotEvenLikeAHeader': 'blah'}))
    assert isinstance(criteria, HTTPCriteria)
    assert criteria.headers == {'NotEvenLikeAHeader': 'blah'}
    assert criteria.cookies is ...
    assert criteria.params is ...
    assert criteria.data is ...


async def test_forced_cookies(src: Any) -> None:
    criteria = Criteria.guess(src.cookies({'session': 'sid'}))
    assert isinstance(criteria, HTTPCriteria)
    assert criteria.cookies == {'session': 'sid'}
    assert criteria.headers is ...
    assert criteria.params is ...
    assert criteria.data is ...


async def test_forced_method_enum(src: Any) -> None:
    criteria = Criteria.guess(src.method('gEt'))
    assert isinstance(criteria, HTTPCriteria)
    assert criteria.method == method.GET


async def test_forced_method_adhoc(src: Any) -> None:
    criteria = Criteria.guess(src.method('adhoc'))
    assert isinstance(criteria, HTTPCriteria)
    assert isinstance(criteria.method, method)
    assert criteria.method == 'adhoc'


async def test_forced_path(src: Any) -> None:
    criteria = Criteria.guess(src.path('/'))
    assert isinstance(criteria, HTTPCriteria)
    assert criteria.path == '/'
    assert criteria.text is ...
    assert criteria.body is ...


async def test_forced_text(src: Any) -> None:
    criteria = Criteria.guess(src.text('/'))
    assert isinstance(criteria, HTTPCriteria)
    assert criteria.text == '/'
    assert criteria.body is ...
    assert criteria.path is ...


async def test_forced_body(src: Any) -> None:
    criteria = Criteria.guess(src.body(b'/'))
    assert isinstance(criteria, HTTPCriteria)
    assert criteria.body == b'/'
    assert criteria.text is ...
    assert criteria.path is ...


async def test_forced_clusterwide(src: Any) -> None:
    criteria = Criteria.guess(src.clusterwide())
    assert isinstance(criteria, K8sCriteria)
    assert criteria.clusterwide == True
    assert criteria.namespace is ...


async def test_forced_namespaced(src: Any) -> None:
    criteria = Criteria.guess(src.clusterwide(False))
    assert isinstance(criteria, K8sCriteria)
    assert criteria.clusterwide == False
    assert criteria.namespace is ...


async def test_forced_namespace(src: Any) -> None:
    criteria = Criteria.guess(src.namespace('ns1'))
    assert isinstance(criteria, K8sCriteria)
    assert criteria.namespace == 'ns1'
    assert criteria.subresource is ...
    assert criteria.resource is ...
    assert criteria.name is ...


async def test_forced_name(src: Any) -> None:
    criteria = Criteria.guess(src.name('example-pod'))
    assert isinstance(criteria, K8sCriteria)
    assert criteria.name == 'example-pod'
    assert criteria.subresource is ...
    assert criteria.resource is ...


async def test_forced_subresource(src: Any) -> None:
    criteria = Criteria.guess(src.subresource('status'))
    assert isinstance(criteria, K8sCriteria)
    assert criteria.subresource == 'status'
    assert criteria.resource is ...
    assert criteria.name is ...


async def test_forced_action(src: Any) -> None:
    criteria = Criteria.guess(src.action('list'))
    assert isinstance(criteria, K8sCriteria)
    assert isinstance(criteria.action, action)
    assert criteria.action == action.LIST
    assert criteria.resource is ...
    assert criteria.name is ...


async def test_forced_resource(src: Any) -> None:
    criteria = Criteria.guess(src.resource('pods.v1'))
    assert isinstance(criteria, K8sCriteria)
    assert criteria.resource is not ...
    assert criteria.resource.group == ''
    assert criteria.resource.version == 'v1'
    assert criteria.resource.plural == 'pods'
    assert criteria.name is ...
