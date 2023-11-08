# When changing this, ensure the docs are synced in intro.rst and around.
# These tests ensure that the docs show adequately runnable examples.

import asyncio
import datetime
import json

import aiohttp
import pytest

import kmock


async def test_http_access(kmock):
    kmock['get /'] << 418 << {'hello': 'world'}
    resp = await kmock.get('/')
    data = await resp.json()
    assert resp.status == 418
    assert data == {'hello': 'world'}


async def test_k8s_list(kmock):
    kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'name1'] = {'spec': 123}
    kmock.objects['kopf.dev/v1/kopfexamples', 'ns2', 'name2'] = {'spec': 456}

    resp = await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples')
    data = await resp.json()
    assert kmock.Object(data) >= {'items': [{'spec': 123}]}


async def test_k8s_watch(kmock):
    # The stream must start BEFORE the activity happens.
    async with kmock.get('/apis/kopf.dev/v1/kopfexamples?watch=true') as resp:
        # Simulate the activity (ignore the responses).
        body = {'metadata': {'namespace': 'ns1', 'name': 'name3'}, 'spec': 789}
        await kmock.post('/apis/kopf.dev/v1/kopfexamples', json=body)
        await kmock.delete('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/name3')
        await asyncio.sleep(0.1)  # the loopback network stack takes some time

        # Read the accumulated stream.
        lines: list[bytes] = resp.content.read_nowait().splitlines()
        events = [json.loads(line.decode()) for line in lines]

    # Close the connection, and assert the results.
    assert len(events) == 2
    assert kmock.Object(events[0]) >= {'type': 'ADDED', 'object': {'spec': 789}}
    assert kmock.Object(events[1]) >= {'type': 'DELETED', 'object': {'spec': 789}}


# A hand-made stream simulation, which ignores the KubernetesEmulator existence above.
@pytest.mark.kmock(port=12345, cls=kmock.RawHandler)
async def test_bizzarily_complex_k8s_simulation(kmock):
    deletion_event = asyncio.Event()
    asyncio.get_running_loop().call_later(6, deletion_event.set)

    gets = kmock['get']
    lists = kmock['list']
    watches = kmock['watch']

    kmock['list kopf.dev/v1/kopfexamples', kmock.namespace('ns1')] << {'items': [],
                                                                       'metadata': {'resourceVersion': 'v1'}}
    kmock['watch kopf.dev/v1/kopfexamples', kmock.namespace('ns1')] << [
        {'type': 'ADDED', 'object': {'spec': {}}},
        lambda: asyncio.sleep(3),
        lambda: {'type': 'MODIFIED', 'object': {'spec': {'time': datetime.datetime.now(tz=datetime.UTC).isoformat()}}},
        deletion_event.wait(),
        [
            {'type': 'DELETED', 'object': {'metadata': {'name': f'demo{i}'}}}
            for i in range(3)
        ],
        410,
    ]

    kmock << 404 << b'{"error": "not served"}' << {'X-MyServer-Info': 'error'}

    await function_under_test(kmock)

    assert len(list(kmock)) == 3
    assert len(list(gets)) == 2
    assert len(list(lists)) == 1
    assert len(list(watches)) == 1
    assert list(watches)[0].params == {'watch': 'true'}
    assert list(watches)[0].headers['X-MyLib-Version'] == '1.2.3'


async def function_under_test(kmock: kmock.RawHandler) -> None:
    resp = await kmock.post('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples')
    assert resp.status == 404
    assert resp.headers['X-MyServer-Info'] == 'error'

    await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples')

    headers = {'X-MyLib-Version': '1.2.3'}
    timeout = aiohttp.ClientTimeout(total=1)
    await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples?watch=true',
                    timeout=timeout, headers=headers)
