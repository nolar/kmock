import pytest

from kmock import RawHandler, Server


async def test_no_servers_on_url() -> None:
    async with RawHandler() as kmock:
        with pytest.raises(RuntimeError, match=r"There is no running server"):
            kmock.url


async def test_no_servers_on_request() -> None:
    async with RawHandler() as kmock:
        with pytest.raises(RuntimeError, match=r"There is no running server"):
            await kmock.request('get', '/')


async def test_server_registration_in_handler() -> None:
    async with RawHandler() as kmock:
        assert kmock.servers == []
        async with Server(kmock) as srv1, Server(kmock) as srv2:
            assert kmock.servers == [srv1, srv2]
        assert kmock.servers == []


async def test_balanced_access() -> None:
    async with RawHandler() as kmock:
        async with Server(kmock) as srv1, Server(kmock) as srv2:
            await kmock.get('/?q=1')
            await kmock.get('/?q=2')
            await kmock.get('/?q=3')
            await kmock.get('/?q=4')
            assert str(kmock[0].url) == f'{srv1.url}/?q=1'
            assert str(kmock[1].url) == f'{srv2.url}/?q=2'
            assert str(kmock[2].url) == f'{srv1.url}/?q=3'
            assert str(kmock[3].url) == f'{srv2.url}/?q=4'


async def test_explicit_access() -> None:
    async with RawHandler() as kmock:
        async with Server(kmock) as srv1, Server(kmock) as srv2:
            await srv1.client.get('/?q=1')
            await srv1.client.get('/?q=2')
            await srv2.client.get('/?q=3')
            await srv2.client.get('/?q=4')
            assert str(kmock[0].url) == f'{srv1.url}/?q=1'
            assert str(kmock[1].url) == f'{srv1.url}/?q=2'
            assert str(kmock[2].url) == f'{srv2.url}/?q=3'
            assert str(kmock[3].url) == f'{srv2.url}/?q=4'


async def test_user_agent() -> None:
    async with RawHandler()as kmock, Server(kmock, user_agent='sample/user/agent'):
        kmock << b''
        await kmock.get('/')
        requests = list(kmock)
        headers = dict(requests[0].headers)
        assert headers['User-Agent'] == 'sample/user/agent'


async def test_http_methods() -> None:
    async with RawHandler() as kmock, Server(kmock):
        await kmock.get('/')
        await kmock.head('/')
        await kmock.options('/')
        await kmock.put('/', json={})
        await kmock.post('/', json={})
        await kmock.patch('/', json={})
        await kmock.delete('/', json={})
        assert kmock[0].method == 'GET'
        assert kmock[1].method == 'HEAD'
        assert kmock[2].method == 'OPTIONS'
        assert kmock[3].method == 'PUT'
        assert kmock[4].method == 'POST'
        assert kmock[5].method == 'PATCH'
        assert kmock[6].method == 'DELETE'
