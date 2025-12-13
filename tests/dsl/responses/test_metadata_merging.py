import aiohttp.web
import pytest

from kmock import Response


def test_unsupported_combining() -> None:
    response1 = Response()
    with pytest.raises(TypeError):
        response1 + object()


def test_ambiguous_statuses() -> None:
    response1 = Response(status=200)
    response2 = Response(status=300)
    with pytest.warns(UserWarning, match=r"Ambiguous statuses"):
        response = response1 + response2
    assert response.status == 300


def test_ambiguous_reasons() -> None:
    response1 = Response(reason='ok')
    response2 = Response(reason='not ok')
    with pytest.warns(UserWarning, match=r"Ambiguous reasons"):
        response = response1 + response2
    assert response.reason == 'not ok'


def test_ambiguous_headers() -> None:
    response1 = Response(headers={'x': '123', 'a': '100'})
    response2 = Response(headers={'x': '456', 'b': '200'})
    with pytest.warns(UserWarning, match=r"Ambiguous headers"):
        response = response1 + response2
    assert response.headers == {'x': '456', 'a': '100', 'b': '200'}


def test_ambiguous_cookies() -> None:
    response1 = Response(cookies={'x': '123', 'a': '100'})
    response2 = Response(cookies={'x': '456', 'b': '200'})
    with pytest.warns(UserWarning, match=r"Ambiguous cookies"):
        response = response1 + response2
    assert response.cookies == {'x': '456', 'a': '100', 'b': '200'}


def test_ambiguous_content_1() -> None:
    response1 = Response(payload=aiohttp.web.StreamResponse())
    response2 = Response(payload=b'hello')
    with pytest.warns(UserWarning, match=r"Ambiguous content"):
        response = response1 + response2
    assert response.payload == b'hello'


def test_ambiguous_content_2() -> None:
    response1 = Response(payload=b'hello')
    response2 = Response(payload=aiohttp.web.StreamResponse())
    with pytest.warns(UserWarning, match=r"Ambiguous content"):
        response = response1 + response2
    assert response.payload is response2.payload


def test_aiohttp_response_1() -> None:
    response1 = Response(payload=aiohttp.web.StreamResponse())
    response2 = Response()
    response = response1 + response2
    assert response.payload is response1.payload


def test_aiohttp_response_2() -> None:
    response1 = Response()
    response2 = Response(payload=aiohttp.web.StreamResponse())
    response = response1 + response2
    assert response.payload is response2.payload


def test_tuples_combined() -> None:
    response1 = Response(payload=(b'hello',))
    response2 = Response(payload=(b'world',))
    response = response1 + response2
    assert response.payload == (b'hello', b'world')


def test_scalar_and_tuple_combined() -> None:
    response1 = Response(payload=b'hello')
    response2 = Response(payload=(b'world',))
    response = response1 + response2
    assert response.payload == (b'hello', b'world')


def test_tuple_and_scalar_combined() -> None:
    response1 = Response(payload=(b'hello',))
    response2 = Response(payload=b'world')
    response = response1 + response2
    assert response.payload == (b'hello', b'world')


def test_scalars_combined() -> None:
    response1 = Response(payload=b'hello')
    response2 = Response(payload=b'world')
    response = response1 + response2
    assert response.payload == (b'hello', b'world')
