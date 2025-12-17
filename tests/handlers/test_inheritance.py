"""
We promise that specific inheritance is supported for descendant classes.
This should not be broken.
"""
import aiohttp.web
import attrs
import pytest
from typing_extensions import override

from kmock import RawHandler, Request, Server


@attrs.define
class SampleOverride(RawHandler):

    @override
    async def _handle(self, request: Request) -> aiohttp.web.StreamResponse:
        return aiohttp.web.Response(body=b'hello', status=234, headers={'X-Sample': 'header'})


@attrs.define
class SampleErrorOverride(RawHandler):

    @override
    async def _handle(self, request: Request) -> aiohttp.web.StreamResponse:
        raise ZeroDivisionError("Fatality!")

    @override
    async def _render_error(self, exc: Exception) -> aiohttp.web.StreamResponse:
        assert isinstance(exc, ZeroDivisionError)
        return aiohttp.web.Response(body=b'hello', status=234, headers={'X-Sample': 'header'})


@attrs.define
class SampleErrorStreamOverride(RawHandler):

    @override
    async def _handle(self, request: Request) -> aiohttp.web.StreamResponse:
        # Option 1: the most realistic way with simulated stream with an exception. The empty bytes
        # is needed to start the response writing; stream do not write until something is yielded.
        self << 234 << {'X-Sample': 'header'} << (b'', ZeroDivisionError("Fatality!"))
        return await super()._handle(request)

        # # Option 2: the same, but with explicitly defined structure not via the DSL.
        # payload = (b'', ZeroDivisionError("Fatality!"))
        # response = Response(status=234, headers={'X-Sample': 'header'}, payload=payload)
        # self._payloads = [Reaction(response=response, source=self)]
        # return await super()._handle(request)

        # # Option 3: using some "abstraction leaks" of how the streaming errors are wrapped:
        # response = aiohttp.web.StreamResponse(status=234, headers={'X-Sample': 'header'})
        # await response.prepare(request._raw_request)
        # raise StreamingError(response) from ZeroDivisionError("Fatality!")

    @override
    async def _stream_error(self, exc: Exception, raw_response: aiohttp.web.StreamResponse) -> None:
        assert isinstance(exc, ZeroDivisionError)
        await raw_response.write(b'hello')


@pytest.mark.parametrize('errors, cls', [
    (0, SampleOverride),
    (1, SampleErrorOverride),
    (1, SampleErrorStreamOverride),
])
async def test_inheritance_overrides(cls: type[RawHandler], errors: int) -> None:
    async with cls(strict=False) as kmock, Server(kmock):
        resp = await kmock.get('/')
        text = await resp.read()
        assert resp.headers['X-Sample'] == 'header'
        assert resp.status == 234
        assert text == b'hello'
        assert len(kmock.errors) == errors
        if errors:
            assert isinstance(kmock.errors[0], ZeroDivisionError)
