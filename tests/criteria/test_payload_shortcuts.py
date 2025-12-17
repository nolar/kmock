from typing import Any

import aiohttp.web
import pytest

import kmock
from kmock import Response


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
def test_forced_data(src: Any, arg: Any) -> None:
    response = Response.guess(src.data(arg))
    assert response.payload == arg
    assert response.headers is None
    assert response.cookies is None
    assert response.status is None
    assert response.reason is None


def test_forced_text(src: Any) -> None:
    response = Response.guess(src.text('/'))
    assert response.payload == '/'
    assert response.status is None
    assert response.reason is None
    assert response.headers is None
    assert response.cookies is None


def test_forced_body(src: Any) -> None:
    response = Response.guess(src.body(b'/'))
    assert response.payload == b'/'
    assert response.status is None
    assert response.reason is None
    assert response.headers is None
    assert response.cookies is None


def test_forced_headers(src: Any) -> None:
    response = Response.guess(src.headers({'NotEvenLikeAHeader': 'blah'}))
    assert response.headers == {'NotEvenLikeAHeader': 'blah'}
    assert response.cookies is None
    assert response.payload is None
    assert response.status is None
    assert response.reason is None


def test_forced_cookies(src: Any) -> None:
    response = Response.guess(src.cookies({'session': 'sid'}))
    assert response.cookies == {'session': 'sid'}
    assert response.headers is None
    assert response.payload is None
    assert response.status is None
    assert response.reason is None


@pytest.mark.parametrize('name', ['path', 'params'])
def test_unsupported_response_shortcuts(src: Any, name: str) -> None:
    with pytest.raises(ValueError, match=r'Unsupported payload type:'):
        Response.guess(getattr(src, name)())


def test_unsupported_aiohttp_response() -> None:
    with pytest.raises(ValueError, match=r'Unsupported payload type:'):
        Response.guess(aiohttp.web.StreamResponse())
