import asyncio

import aiohttp
import pytest

from kmock import RawHandler, Reaction, Request, View, method


@pytest.fixture
async def reaction(kmock: RawHandler) -> Reaction:
    # Any payload works that allows the requests to freeze and be seen in kmock[...].
    return kmock << (b'', ...)


@pytest.fixture
async def prepopulated(kmock: RawHandler, reaction: Reaction) -> None:
    resps: list[aiohttp.ClientResponse] = [
        await kmock.request(method, f'/?idx={i}')
        for method in ['get'] for i in range(10)
    ]
    yield
    for resp in resps:
        resp.close()


@pytest.fixture
async def overpopulated(kmock: RawHandler, prepopulated: None) -> None:
    resps: list[aiohttp.ClientResponse] = [
        await kmock.request(method, f'/?idx={i}')
        for method in ['post', 'patch'] for i in range(10)
    ]
    yield
    for resp in resps:
        resp.close()


# Note: the yielded view MUST only see 10x "GET /" requests, nothing else — as defined in tests.
@pytest.fixture(params=[
    'root', 'upto-slicer', 'from-slicer', 'step-slicer', 'filter',
    'or', 'and', 'exclusion', 'priority', 'reaction', 'streamer',
])
def view(request: pytest.FixtureRequest, reaction: Reaction, kmock: RawHandler) -> View:
    if request.param == 'root':
        request.getfixturevalue('prepopulated')
        return kmock
    elif request.param == 'upto-slicer':
        request.getfixturevalue('prepopulated')
        return kmock[:100]
    elif request.param == 'from-slicer':
        request.getfixturevalue('prepopulated')
        return kmock[0:]
    elif request.param == 'step-slicer':
        request.getfixturevalue('prepopulated')
        return kmock[::1]
    elif request.param == 'filter':
        request.getfixturevalue('overpopulated')
        return kmock['get']
    elif request.param == 'or':
        request.getfixturevalue('overpopulated')
        return kmock['get'] | kmock['delete']
    elif request.param == 'and':
        request.getfixturevalue('overpopulated')
        return kmock['get'] & kmock['/']
    elif request.param == 'exclusion':
        request.getfixturevalue('overpopulated')
        return kmock['get'] - kmock['delete']
    elif request.param == 'priority':
        request.getfixturevalue('prepopulated')
        return kmock ** 0
    elif request.param == 'reaction':
        request.getfixturevalue('prepopulated')
        return reaction
    elif request.param == 'streamer':
        request.getfixturevalue('prepopulated')
        return kmock[...]
    else:
        raise Exception(f"Unsupported fixture param {request.param!r}")


@pytest.fixture(params=[
    'root', 'slicer', 'filter', 'or', 'and', 'exclusion', 'priority', 'reaction', 'streamer',
])
def empty_view(request: pytest.FixtureRequest, reaction: Reaction, kmock: RawHandler) -> View:
    if request.param == 'root':
        return kmock
    elif request.param == 'slicer':
        return kmock[100:]
    elif request.param == 'filter':
        return kmock[method.GET]
    elif request.param == 'or':
        return kmock[method.GET] | kmock[method.POST]
    elif request.param == 'and':
        return kmock[method.GET] & kmock['/']
    elif request.param == 'exclusion':
        return kmock[method.GET] - kmock[method.DELETE]
    elif request.param == 'priority':
        return kmock ** 0
    elif request.param == 'reaction':
        return reaction
    elif request.param == 'streamer':
        return kmock[...]
    else:
        raise Exception(f"Unsupported fixture param {request.param!r}")


async def test_empty_view(empty_view: View) -> None:
    assert not empty_view
    assert len(empty_view) == 0
    assert len([req for req in empty_view]) == 0
    assert '/' not in empty_view  # any certain or catch-all criterion
    assert {'idx': '5'} not in empty_view  # any certain or catch-all criterion


async def test_full_view(view: View) -> None:
    assert view
    assert len(view) == 10
    assert len([req for req in view]) == 10
    assert '/' in view
    assert '/wrong' not in view
    assert {'idx': '5'} in view
    assert {'idx': '10'} not in view

    reqs: list[Request] = []
    async for req in view:
        reqs.append(req)
    assert len(reqs) == 10


async def test_response_stats_depend_on_usage(kmock: RawHandler) -> None:
    pattern = kmock['get /?idx=5'] << b'hello'
    assert not list(pattern)
    assert not pattern
    assert len(pattern) == 0
    assert '/' not in pattern

    text = await (await kmock.get('/?idx=5')).read()
    assert text == b'hello'

    assert list(pattern)
    assert pattern
    assert len(pattern) == 1
    assert '/' in pattern


@pytest.mark.looptime
async def test_streamer_stats_depend_on_usage(kmock: RawHandler) -> None:
    pattern = kmock['get /?idx=5'] << ...

    assert not list(pattern)
    assert not pattern
    assert len(pattern) == 0
    assert '/' not in pattern

    loop = asyncio.get_running_loop()
    loop.call_later(11, lambda: pattern[...] << b'hello')
    text = await (await kmock.get('/?idx=5')).read()
    assert text == b'hello'

    assert list(pattern)
    assert pattern
    assert len(pattern) == 1
    assert '/' in pattern
