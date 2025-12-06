import sys

import aiohttp.test_utils
import aiohttp.web
import pytest
from typing_extensions import override

from kmock import KMockError, RawHandler, Server
from kmock._internal import rendering


class FailingHandler(RawHandler):
    async def _handle(self, request: rendering.Request) -> aiohttp.web.StreamResponse:
        raise ZeroDivisionError("Boo!")

    @override
    async def _render_error(self, exc: Exception) -> aiohttp.web.StreamResponse:
        return aiohttp.web.Response(body=b'an error was here')


async def test_handler_is_inactive_at_creation() -> None:
    kmock = RawHandler()
    assert not kmock.active
    assert not kmock.clients


async def test_handler_activation() -> None:
    kmock = RawHandler()
    async with kmock:
        assert kmock.active
        assert not kmock.clients


async def test_handler_remains_inactive_in_active_server() -> None:
    kmock = RawHandler()
    async with Server(kmock):
        assert not kmock.active


async def test_errors_unavailable_when_inactive() -> None:
    kmock = RawHandler()
    with pytest.raises(RuntimeError, match=r".*only when used as context managers.*"):
        kmock.errors


async def test_inactive_server_connection_info_preserved() -> None:
    server = Server(RawHandler(), host='1.2.3.4', port=12345)
    assert server.host == '1.2.3.4'
    assert server.port == 12345


async def test_inactive_server_connection_info_unavailable() -> None:
    server = Server(RawHandler())
    assert server.host == '127.0.0.1'
    with pytest.raises(RuntimeError, match=r"The server is not active and has no URL yet"):
        server.url
    with pytest.raises(RuntimeError, match=r"The server is not active and has no port yet"):
        server.port
    with pytest.raises(RuntimeError, match=r"The server is not active and has no client yet"):
        server.client
    with pytest.raises(RuntimeError, match=r"The server is not active and has no underlying server yet"):
        server.server


async def test_active_server_registers_a_client_in_handler() -> None:
    kmock = RawHandler()
    async with Server(kmock) as server:
        assert len(kmock.clients) == 1
        assert kmock.clients[0] == server.client


async def test_active_server_connection_info() -> None:
    async with Server(RawHandler()) as server:
        assert server.server is not None
        assert isinstance(server.server, aiohttp.test_utils.BaseTestServer)


async def test_active_server_entered_twice() -> None:
    async with Server(RawHandler()) as server:
        with pytest.raises(RuntimeError, match=r"The server can be started/entered only once"):
            async with server:
                pass


# The server is introduced to tests only to have a realistic (non-simulated) aiohttp.ClientRequest.
async def test_request_errors_escalate_directly_when_inactive() -> None:
    kmock = FailingHandler()
    async with Server(kmock) as server:
        resp = await server._managed_client.get('/')
        text = await resp.read()
        assert resp.status == 500
        assert text.startswith(b'500 Internal Server Error\n\nTraceback')
        assert text.endswith(b'\nZeroDivisionError: Boo!\n')  # not our replacing text!


async def test_request_errors_accumulate_when_active() -> None:
    async with FailingHandler() as kmock, Server(kmock):
        assert not kmock.errors
        resp = await kmock.get('/')
        text = await resp.read()
        assert len(kmock.errors) == 1
        assert isinstance(kmock.errors[0], ZeroDivisionError)
        assert text == b'an error was here'


async def test_request_errors_accumulate_isolated_across_levels() -> None:
    async with FailingHandler() as kmock, Server(kmock):
        await kmock.get('/')
        async with kmock:
            await kmock.get('/')
            await kmock.get('/')
            assert len(kmock.errors) == 2
            assert isinstance(kmock.errors[0], ZeroDivisionError)
            assert isinstance(kmock.errors[1], ZeroDivisionError)
        assert len(kmock.errors) == 1
        assert isinstance(kmock.errors[0], ZeroDivisionError)


async def test_request_errors_escalate_alone() -> None:
    with pytest.raises(Exception) as exc:
        async with FailingHandler(strict=True) as kmock, Server(kmock):
            await kmock.get('/')
    assert isinstance(exc.value, ZeroDivisionError)


@pytest.mark.skipif(sys.version_info >= (3, 11), reason="ExceptionGroup is only supported in 3.11+")
async def test_request_errors_escalate_as_one_of_many() -> None:
    with pytest.raises(Exception) as exc:
        async with FailingHandler(strict=True) as kmock, Server(kmock):
            await kmock.get('/')
            await kmock.get('/')
    assert isinstance(exc.value, ZeroDivisionError)


@pytest.mark.skipif(sys.version_info < (3, 11), reason="ExceptionGroup is only supported in 3.11+")
async def test_request_errors_escalate_in_groups() -> None:
    with pytest.raises(Exception) as exc:
        async with FailingHandler(strict=True) as kmock, Server(kmock):
            await kmock.get('/')
            await kmock.get('/')
    assert isinstance(exc.value, ExceptionGroup)
    assert len(exc.value.exceptions) == 2
    assert isinstance(exc.value.exceptions[0], ZeroDivisionError)
    assert isinstance(exc.value.exceptions[1], ZeroDivisionError)


async def test_request_errors_can_be_cleared() -> None:
    async with FailingHandler(strict=True) as kmock, Server(kmock):
        await kmock.get('/')
        await kmock.get('/')
        kmock.errors[:] = []


async def test_request_errors_can_be_removed() -> None:
    with pytest.raises(ZeroDivisionError):
        async with FailingHandler(strict=True) as kmock, Server(kmock):
            await kmock.get('/')
            await kmock.get('/')
            del kmock.errors[1]


async def test_request_errors_can_be_replaced() -> None:
    with pytest.raises(RuntimeError, match=r"simulated"):
        async with FailingHandler(strict=True) as kmock, Server(kmock):
            await kmock.get('/')
            kmock.errors[0] = RuntimeError("simulated")


async def test_escalated_errors_have_higher_priority_than_accumulated_errors() -> None:
    with pytest.raises(RuntimeError, match=r'simulated code error'):
        async with FailingHandler(strict=True) as kmock, Server(kmock):
            await kmock.get('/')
            raise RuntimeError('simulated code error')


@pytest.mark.skipif(sys.version_info < (3, 11), reason="ExceptionGroup is only supported in 3.11+")
async def test_escalated_groups_have_higher_priority_than_accumulated_errors() -> None:
    # NB: the escalated error is NEVER accumulated as it does not come from a handler.
    with pytest.raises(ExceptionGroup) as exc:
        async with FailingHandler(strict=True) as kmock, Server(kmock):
            await kmock.get('/')
            async with kmock:
                await kmock.get('/')
                await kmock.get('/')

    # It is the error from the inner context manager, not from the outer one.
    assert len(exc.value.exceptions) == 2
    assert isinstance(exc.value.exceptions[0], ZeroDivisionError)
    assert isinstance(exc.value.exceptions[1], ZeroDivisionError)


# NB: it is not about errors in general, but this is a single test for limits, so let it be here.
async def test_limiting() -> None:
    async with RawHandler(limit=1) as kmock, Server(kmock):
        kmock << b'hello'
        resp1 = await kmock.get('/')
        text1 = await resp1.read()
        resp2 = await kmock.get('/')
        text2 = await resp2.read()
        assert text1 == b'hello'
        assert b'Too many requests' in text2
        assert len(kmock.errors) == 1
        assert isinstance(kmock.errors[0], KMockError)
