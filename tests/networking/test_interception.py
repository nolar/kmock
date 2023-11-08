import re

import aiohttp.connector
import pytest

from kmock import AiohttpInterceptor, ResolverFilter


@pytest.mark.parametrize('host, expected_ip', [
    pytest.param('localhost', '127.0.0.1'),
    pytest.param('localhost', '::1'),
    pytest.param('dns.google', '8.8.8.8'),
    pytest.param('dns.google', '8.8.4.4'),
    # if needed, create "something.kopf.dev" and use it instead.
])
async def test_bare_host_resolution(host: str, expected_ip: str) -> None:
    # Ensure that what we test below, is testable at all, and is used by aiohttp.
    connector = aiohttp.connector.TCPConnector()
    resolved = await connector._resolve_host(host, 443)
    hosts = {r['host'] for r in resolved}
    ports = {r['port'] for r in resolved}
    assert expected_ip in hosts
    assert ports == {443}


@pytest.mark.parametrize('host', ['testhost', 'TESTHOST', '127.1.2.3'])
@pytest.mark.parametrize('filter', [
    pytest.param('testhost', id='str'),
    pytest.param(('testhost', 'x'), id='str-tuple'),
    pytest.param(['testhost', 'x'], id='str-list'),
    pytest.param({'testhost', 'x'}, id='str-set'),
    pytest.param(re.compile('test.*', re.I), id='regex'),
    pytest.param((re.compile('test.*', re.I), 'x'), id='regex-tuple'),
    pytest.param([re.compile('test.*', re.I), 'x'], id='regex-list'),
    pytest.param({re.compile('test.*', re.I), 'x'}, id='regex-set'),
])
async def test_interception_by_host_to_host(filter: ResolverFilter, host: str) -> None:
    interceptor = AiohttpInterceptor('127.1.2.3', extra=filter)
    async with interceptor:
        connector = aiohttp.connector.TCPConnector()
        resolved = await connector._resolve_host(host, 99)
        assert len(resolved) == 1
        assert resolved[0]['hostname'] == host  # as requested
        assert resolved[0]['port'] == 99  # not intercepted
        assert resolved[0]['host'] == '127.1.2.3'


@pytest.mark.parametrize('host', ['testhost', 'TESTHOST'])
@pytest.mark.parametrize('filter', [
    pytest.param('testhost', id='str'),
    pytest.param(('testhost', 'x'), id='str-tuple'),
    pytest.param(['testhost', 'x'], id='str-list'),
    pytest.param({'testhost', 'x'}, id='str-set'),
    pytest.param(re.compile('test.*', re.I), id='regex'),
    pytest.param((re.compile('test.*', re.I), 'x'), id='regex-tuple'),
    pytest.param([re.compile('test.*', re.I), 'x'], id='regex-list'),
    pytest.param({re.compile('test.*', re.I), 'x'}, id='regex-set'),
])
async def test_interception_by_host_to_port(filter: ResolverFilter, host: str) -> None:
    interceptor = AiohttpInterceptor('127.1.2.3', 12345, extra=filter)
    async with interceptor:
        connector = aiohttp.connector.TCPConnector()
        resolved = await connector._resolve_host(host, 99)
        assert len(resolved) == 1
        assert resolved[0]['hostname'] == host  # as requested
        assert resolved[0]['port'] == 12345  # intercepted
        assert resolved[0]['host'] == '127.1.2.3'

@pytest.mark.parametrize('host', ['testhost', 'TESTHOST'])
@pytest.mark.parametrize('filter', [
    pytest.param(('testhost', 99), id='str'),
    pytest.param((('testhost', 99), 'x'), id='str-tuple'),
    pytest.param([('testhost', 99), 'x'], id='str-list'),
    pytest.param({('testhost', 99), 'x'}, id='str-set'),
    pytest.param((re.compile('test.*', re.I), 99), id='regex'),
    pytest.param(((re.compile('test.*', re.I), 99), 'x'), id='regex-tuple'),
    pytest.param([(re.compile('test.*', re.I), 99), 'x'], id='regex-list'),
    pytest.param({(re.compile('test.*', re.I), 99), 'x'}, id='regex-set'),
])
async def test_interception_by_port_to_port(filter: ResolverFilter, host: str) -> None:
    interceptor = AiohttpInterceptor('127.1.2.3', 12345, extra=filter)
    async with interceptor:
        connector = aiohttp.connector.TCPConnector()
        resolved = await connector._resolve_host(host, 99)
        assert len(resolved) == 1
        assert resolved[0]['hostname'] == host  # as requested
        assert resolved[0]['port'] == 12345  # intercepted
        assert resolved[0]['host'] == '127.1.2.3'


async def test_missed_interception_by_host() -> None:
    interceptor = AiohttpInterceptor('127.1.2.3', 12345, extra='testhost')
    async with (interceptor):
        connector = aiohttp.connector.TCPConnector()
        resolved = await connector._resolve_host('localhost', 80)
        hosts = {r['host'] for r in resolved}
        ports = {r['port'] for r in resolved}
        assert '127.0.0.1' in hosts
        assert ports == {80}


async def test_missed_interception_by_port() -> None:
    interceptor = AiohttpInterceptor('127.1.2.3', 12345, extra=('localhost', 99))
    async with (interceptor):
        connector = aiohttp.connector.TCPConnector()
        resolved = await connector._resolve_host('localhost', 80)
        hosts = {r['host'] for r in resolved}
        ports = {r['port'] for r in resolved}
        assert '127.0.0.1' in hosts
        assert ports == {80}


async def test_self_interception() -> None:
    interceptor = AiohttpInterceptor('127.1.2.3', 12345)
    async with interceptor:
        connector = aiohttp.connector.TCPConnector()
        resolved = await connector._resolve_host('127.1.2.3', 99)
        assert {r['port'] for r in resolved} == {99}


async def test_nested_interception() -> None:
    interceptor1 = AiohttpInterceptor('127.1.2.3', 12345, extra={'testhost', 'otherhost'})
    interceptor2 = AiohttpInterceptor('127.2.3.4', 23456, extra='otherhost')
    async with interceptor1, interceptor2:
        connector = aiohttp.connector.TCPConnector()
        resolved1 = await connector._resolve_host('testhost', 80)
        resolved2 = await connector._resolve_host('otherhost', 443)
        assert len(resolved1) == 1
        assert len(resolved2) == 1
        assert resolved1[0]['hostname'] == 'testhost'
        assert resolved2[0]['hostname'] == 'otherhost'
        assert resolved1[0]['host'] == '127.1.2.3'
        assert resolved2[0]['host'] == '127.2.3.4'
        assert resolved1[0]['port'] == 12345
        assert resolved2[0]['port'] == 23456


async def test_double_entering() -> None:
    interceptor = AiohttpInterceptor('127.1.2.3', 12345, extra='testhost')
    async with interceptor:
        with pytest.raises(RuntimeError, match=r'.*cannot be entered twice.*'):
            await interceptor.__aenter__()


async def test_premature_exiting() -> None:
    interceptor = AiohttpInterceptor('127.1.2.3', 12345, extra='testhost')
    with pytest.raises(RuntimeError, match=r'.*was not entered.*'):
        await interceptor.__aexit__(None, None, None)


async def test_inconsistent_nesting() -> None:
    interceptor1 = AiohttpInterceptor('127.1.2.3', 12345, extra='testhost')
    interceptor2 = AiohttpInterceptor('127.1.2.3', 12345, extra='testhost')
    with pytest.raises(RuntimeError, match=r'.*resolver chain is inconsistent.*'):
        async with interceptor1:
            await interceptor2.__aenter__()

    # Now, the proper exiting sequence to restore the state.
    await interceptor2.__aexit__(None, None, None)
    await interceptor1.__aexit__(None, None, None)


async def test_unsupported_host() -> None:
    with pytest.raises(TypeError, match=r'Unsupported filter:'):
        interceptor = AiohttpInterceptor(object())
        async with interceptor:
            connector = aiohttp.connector.TCPConnector()
            await connector._resolve_host('localhost', 99)


async def test_unsupported_extras() -> None:
    with pytest.raises(TypeError, match=r'Unsupported filter:'):
        interceptor = AiohttpInterceptor('127.1.2.3', extra=object())
        async with interceptor:
            connector = aiohttp.connector.TCPConnector()
            await connector._resolve_host('localhost', 99)
