"""
Note there is another `test_criteria_matching.py` — for verbose testing
of all possible combinations and edge cases. Here, only the overall testing
of the whole chain (server -> parsed request -> criteria -> reactions).

Assume that criteria matching is tested elsewhere for more details & edge cases.
Only focus on testing the sufficiently diverse requests here, but end-to-end.
"""
import asyncio
import json
from typing import Any

import pytest

from kmock import RawHandler, Request


async def test_the_simplest(kmock: RawHandler) -> None:
    kmock << b'hello'
    resp = await kmock.post('/')
    text = await resp.read()

    assert resp.status == 200
    assert text == b'hello'
    assert len(kmock) == 1
    assert len(kmock['/']) == 1
    assert len(kmock['get']) == 0
    assert len(kmock['post']) == 1


async def test_hardcoded_reaction(kmock: RawHandler) -> None:
    kmock['post /items'] << 201 << {'id': 123, 'name': 'sample item'}
    kmock.fallback << 404 << {'error': 'not found'}

    resp = await kmock.post('/items')
    data = await resp.json()

    assert resp.status == 201
    assert data == {'id': 123, 'name': 'sample item'}
    assert len(kmock) == 1
    assert 'post /items' in kmock

    resp = await kmock.get('/items')
    data = await resp.json()

    assert resp.status == 404
    assert data == {'error': 'not found'}
    assert len(kmock) == 2
    assert 'post /items' in kmock
    assert 'get /items' in kmock

    assert len(kmock['/items']) == 2
    assert len(kmock['get']) == 1
    assert len(kmock['post']) == 1


async def test_interactive_reaction(kmock: RawHandler) -> None:
    kmock['post /items'] << (
        lambda req: {'id': req.id, 'name': (req.data or {}).get('name', 'default')}
    )

    resp = await kmock.post('/items')
    data = await resp.json()
    assert data == {'id': 0, 'name': 'default'}

    resp = await kmock.post('/items', json={'name': 'desired'})
    data = await resp.json()
    assert data == {'id': 1, 'name': 'desired'}

    assert len(kmock) == 2


async def test_stateful_simulation(kmock: RawHandler) -> None:
    dbase: dict[Request, Any] = {}
    kmock['post /items'] << 201 >> dbase
    kmock['get /items?watch=true'] << dbase.values()  # a live dict view (iterable) -> stream
    kmock['get /items'] << (lambda: [req.data for req in dbase])
    kmock.fallback << 404

    await kmock.post('/items', json={'name': '1st'})
    await kmock.post('/items', json={'name': '2nd'})
    jsons = [req.data for req in dbase]
    assert jsons == [{'name': '1st'}, {'name': '2nd'}]

    resp = await kmock.get('/items')
    data = await resp.json()
    assert data == [{'name': '1st'}, {'name': '2nd'}]

    resp = await kmock.get('/items?watch=true')
    text = await resp.read()
    assert text == b'{"name": "1st"}\n{"name": "2nd"}\n'


@pytest.mark.looptime
async def test_arbitrary_stream(kmock: RawHandler) -> None:
    loop = asyncio.get_running_loop()

    stream = kmock['get ?stream=true'] << 222 << b"hello, world! -> " << "json-string" << ...
    loop.call_at(3.45, lambda: stream[...] << {'time': loop.time()} << ...)
    loop.call_at(4.56, lambda: stream[...] << (lambda req: {'path': req.url.path}))

    times_and_lines = []
    resp = await kmock.get('/any-path?stream=true')
    async for line in resp.content:
        times_and_lines.append((loop.time(), line))

    assert resp.status == 222
    assert loop.time() == 4.56
    assert times_and_lines == [
        (0.0, b'hello, world! -> "json-string"\n'),
        (3.45, b'{"time": 3.45}\n'),
        (4.56, b'{"path": "/any-path"}\n'),
    ]


@pytest.mark.looptime
async def test_kubernetes_watch_stream(kmock: RawHandler) -> None:
    loop = asyncio.get_running_loop()

    stream = kmock['watch pods'] << ({'type': 'ADDED', 'object': {'status': 'new'}}, ...)
    loop.call_at(3.45, lambda: stream[...] << {'type': 'MODIFIED', 'object': {'status': 'old'}} << ...)
    loop.call_at(4.56, lambda: stream[...] << (lambda req: {'type': 'DELETED', 'object': {'status': req.namespace}}))

    times_and_items = []
    resp = await kmock.get('/api/v1/namespaces/ns1/pods?watch=true')
    async for line in resp.content:
        times_and_items.append((loop.time(), json.loads(line)))

    assert resp.status == 200
    assert loop.time() == 4.56
    assert times_and_items == [
        (0, {'type': 'ADDED', 'object': {'status': 'new'}}),
        (3.45, {'type': 'MODIFIED', 'object': {'status': 'old'}}),
        (4.56, {'type': 'DELETED', 'object': {'status': 'ns1'}}),
    ]


# Don't do this normally!
@pytest.mark.looptime
async def test_cross_entangled_madness(kmock: RawHandler, looptime: int) -> None:
    loop = asyncio.get_running_loop()

    kmock['/monitor'] << b"The report will follow shortly.\n" << ...
    monitor_resp = await kmock.get('/monitor')  # and keep it open

    # Feed into the stream on the first 6 requests only. Stop it when done.
    kmock[:6] << b"Noted." >> (lambda req: (
        kmock['/monitor'][...] << (
            (lambda req: print(req)),
            f"Time={loop.time():.1f}s. ".encode(),
            f"Got idx={req.params['idx']}. ".encode(),
            f"I saw {len(kmock['get'])} GETs. ".encode(),
            f"{len(kmock['get', ...])} is/are streaming now.".encode(),
            b"\n",
            ...
        ))
    )
    kmock >> (lambda: kmock['/monitor', ...] << None) << b"Done."

    # Let it work for some time.
    texts = []
    for idx in range(6):
        resp = await kmock.get('/whatever', params={'idx': idx})
        text = await resp.read()
        texts.append(text)
        await asyncio.sleep(1)

    monitor_text = await monitor_resp.read()

    assert looptime == 6
    assert texts == [b"Noted.", b"Noted.", b"Noted.", b"Noted.", b"Noted.", b"Done."]
    assert monitor_text == (
        b"The report will follow shortly.\n"
        b"Time=0.0s. Got idx=0. I saw 2 GETs. 1 is/are streaming now.\n"
        b"Time=1.0s. Got idx=1. I saw 3 GETs. 1 is/are streaming now.\n"
        b"Time=2.0s. Got idx=2. I saw 4 GETs. 1 is/are streaming now.\n"
        b"Time=3.0s. Got idx=3. I saw 5 GETs. 1 is/are streaming now.\n"
        b"Time=4.0s. Got idx=4. I saw 6 GETs. 1 is/are streaming now.\n"
    )
