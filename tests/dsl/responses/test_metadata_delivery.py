import pytest

import kmock
from kmock import RawHandler, Response

pytestmark = [pytest.mark.kmock(cls=RawHandler), pytest.mark.looptime]


async def test_status_delivery(kmock: kmock.RawHandler) -> None:
    kmock['/'] << Response(status=234)
    resp = await kmock.get('/')
    assert resp.status == 234


async def test_headers_delivery(kmock: kmock.RawHandler) -> None:
    kmock['/'] << kmock.headers({'a': 'b'}) << b''
    resp = await kmock.get('/')
    assert resp.status == 200
    assert resp.headers['a'] == 'b'


async def test_headers_dropping(kmock: kmock.RawHandler) -> None:
    kmock['/'] << kmock.headers({'a': None}) << b''
    resp = await kmock.get('/')
    assert resp.status == 200
    assert 'a' not in resp.headers


async def test_cookies_delivery(kmock: kmock.RawHandler) -> None:
    kmock['/'] << kmock.cookies({'a': 'b'}) << b''
    resp = await kmock.get('/')
    assert resp.status == 200
    assert resp.cookies['a'].value == 'b'


async def test_cookies_deletion(kmock: kmock.RawHandler) -> None:
    kmock['/'] << kmock.cookies({'a': None}) << b''
    resp = await kmock.get('/')
    assert resp.status == 200
    assert resp.cookies['a']['max-age'] == '0'  # or any other ways of deleting it
    assert resp.cookies['a']['expires'] == 'Thu, 01 Jan 1970 00:00:00 GMT'
