import socket

import aiohttp.test_utils
import pytest

from kmock import RawHandler, Server


class MyServer(aiohttp.test_utils.RawTestServer):
    pass


async def test_custom_server_class() -> None:
    async with RawHandler() as kmock, Server(kmock, server_cls=MyServer) as server:
        assert isinstance(server._managed_server, MyServer)
        # assert isinstance(server.handler._server, MyServer)


async def test_custom_client_class() -> None:
    client = aiohttp.ClientSession()  # ignore the url, we do not test it here
    async with RawHandler() as kmock, Server(kmock, client_fct=lambda url: client) as server:
        assert isinstance(server._managed_client, aiohttp.ClientSession)
        assert server._managed_client is client


# TODO: socket.AF_INET6; BUT aiohttp improperly renders an IPv6 URL (no [] in http://[::1]:123456)
@pytest.fixture(params=[socket.AF_INET])
def family(request: pytest.FixtureRequest) -> socket.AddressFamily:
    return request.param


@pytest.fixture(params=range(3))  # a few local IPs to be sure, but not too many
def local_ip(request: pytest.FixtureRequest, family: socket.AddressFamily) -> str:
    index: int = request.param
    hostname = socket.gethostname()

    ips = {ip for *_, (ip, *_) in socket.getaddrinfo(host=hostname, port=None, family=family)}
    ips -= {'127.0.0.1'}  # the hard-coded default, testing it makes no sense
    ips = {ip for ip in ips if not ip.endswith('.0')}  # MacOS includes these useless IPs
    if not ips:
        pytest.skip("No suitable IPs found (i.e. not the default 127.0.0.1).")
    if index >= len(ips):
        pytest.skip(f"This machine has less than {index+1} IPs of {family.name}: {ips}")

    # Sorting key is for better diversity: avoid focusing on the overrepresented prefix/network.
    # E.g. [fe80::1, fe80::603e:5fff:fe86:807a, fe80::1056:de9b:556c:76be………, $real_ips]
    return sorted(ips, key=lambda ip: ''.join(reversed(ip)))[index]


async def test_host_binding(local_ip: str) -> None:
    async with RawHandler() as kmock, Server(kmock, host=local_ip) as server:
        assert server.host == local_ip
        assert server._managed_server.host == local_ip
        assert server._managed_interceptor.host == local_ip
        assert local_ip in str(kmock.url)
        async with aiohttp.ClientSession() as client:  # does it work at all?
            kmock << b'hello'
            resp = await client.get(kmock.url)
            text = await resp.read()
            assert text == b'hello'


async def test_port_binding(unused_tcp_port: int) -> None:
    async with RawHandler() as kmock, Server(kmock, port=unused_tcp_port) as server:
        assert server.port == unused_tcp_port
        assert server._managed_server.port == unused_tcp_port
        assert server._managed_interceptor.port == unused_tcp_port
        assert str(kmock.url).endswith(f':{unused_tcp_port}')
        async with aiohttp.ClientSession() as client:  # does it work at all?
            kmock << b'hello'
            resp = await client.get(kmock.url)
            text = await resp.read()
            assert text == b'hello'


@pytest.mark.parametrize('port', [None, 0])
async def test_port_allocation(port: int | None) -> None:
    async with RawHandler() as kmock, Server(kmock, port=port) as server:
        assert server.port > 0
        assert server._managed_server.port > 0
        assert server._managed_interceptor.port > 0
        assert str(kmock.url).endswith(f':{server.port}')
        async with aiohttp.ClientSession() as client:  # does it work at all?
            kmock << b'hello'
            resp = await client.get(kmock.url)
            text = await resp.read()
            assert text == b'hello'


async def test_client_binding_to_the_server_url() -> None:
    async with RawHandler() as kmock, Server(kmock) as srv:
        unrelated_port = srv.port - 1
        with pytest.raises(aiohttp.ClientConnectorError):  # aiohttp raises it that way
            await kmock.get(f'http://127.0.0.1:{unrelated_port}')


async def test_interceptor_activation() -> None:
    # Interception is verbosely tested in a nearby test file. Here, only test that it is used.
    async with RawHandler() as kmock, Server(kmock, hostnames='testhost') as server:
        assert server._managed_interceptor.extra == 'testhost'
        async with aiohttp.ClientSession() as client:  # does it work at all?
            kmock << b'hello'
            resp = await client.get('http://testhost:65535')
            text = await resp.read()
            assert text == b'hello'
