# HTTP/API/Kubernetes Mock Server for Python

— Kmock-kmock…

— Who's there?

— It's me, a long awaited Kubernetes API mock server!


## Why?

The main practical purpose is testing Kubernetes operators developed with Kopf, operators migrated to or from Kopf (whether Pythonic or not), and for testing Kopf itself. Kopf is a framework to write Kubernetes operators in Python: https://github.com/nolar/kopf

Developers can use KMock to test any arbitrary HTTP APIs, SDKs, or apps — even without Kubernetes nuances (simply ignore the Kubernetes functionality).

The rationale behind the library design is simple: monkey-patching is bad. It makes you test the specific implementation of your HTTP/API client, not the overall communication contract. Realistic servers are an acceptable compromise. Unlike with realistic servers, which require heavy deployment, KMock works out of the box, and the only trade-off is the overhead for the localhost network traffic & HTTP/JSON rendering & parsing. The obvious flaw: you can make mistakes in your assumptions of what is the supposed response of the server.

The rationale behind the library's DSL is simple too: tests must be brief. Brief tests require brief setup & brief assertions. Extensive logic, such as for-cycles, if-conditions, temporary variables, talking with external classes, so on — all this verbosity distracts from the test purpose, leading to fewer tests being written in total.


## Status

As of Jan'26, the library is freshly released and is in early stages of its life. While the overall concept is stable, some aspects and some features might change with breaking changes. The most probable change is accessing the individual requests: via the `.requests` property instead of the current access via the filters (see `docs/ideas.rst`). This depends on the usage experience by me myself (the author) in the nearest future.

The library was originally hand-made in Nov'2023 (in the pre-AI era) to its 90% readiness, then put on pause and revived in Nov'25 with the intention to release it in any usable form as soon as possible. Over these 2 years, I could forget why I did some things and designed the others one way or another. It might feel inconsistent with the docs and examples in some minor aspects. These inconsistencies should smooth out and disappear as the library matures over time before the v1 major release (now: v0).


## Explanation by examples

See many more examples for every individual feature in the docs:

* https://kmock.readthedocs.io/latest/

```python
import aiohttp
import kmock


async def function_under_test(base_url: str) -> None:
    async with aiohttp.ClientSession(base_url=base_url) as session:
        resp = await session.get('/')
        text = await resp.read()
        resp = await session.post('/hello', json={'name': text.decode()})
        data = await resp.json()
        return data


async def test_simple_http_server(kmock: kmock.RawHandler) -> None:
    # Setup the server side.
    kmock['get /'] << b'john'
    kmock['post /hello'] << (lambda req: {'you-are': req.params.get('name', 'anonymous')})
    never_called = kmock['/'] << b''

    # Work in the client side.
    data = await function_under_test(str(kmock.url))
    assert data == {'you-are': 'john'}

    # Check the server side.
    assert len(kmock) == 2
    assert len(kmock['get']) == 1
    assert len(kmock['post']) == 1
    assert kmock['post'][0].data == {'name': 'john'}
```

Even live streaming is possible.

```python
import datetime
import asyncio
import aiohttp
import freezegun
import kmock


@freezegun.freeze_time("2020-01-01T00:00:00")
async def test_k8s_out_of_the_box(kmock: kmock.RawHandler) -> None:
    kmock['/'] << (
        b'hello', lambda: asyncio.sleep(1), b', world!\n',
        {'key': 'val'},
        lambda: [(f"{i}…\n".encode(), asyncio.sleep(1)) for i in range(3)],
        ...  # live continuation
    )

    async def pulse():
        while True:
            # Broadcast to every streaming request (any method, any URL).
            kmock[...] << (lambda: datetime.datetime.now(tz=datetime.UTC).isoformat(), ...)
            await asyncio.sleep(1)

    asyncio.create_task(pulse())  # we do not clean it up here for brevity

    async with aiohttp.ClientSession(base_url='http://localhost', read_timeout=5) as session:
        resp = await session.get('/')
        text = await resp.read()  # this might take some time

    assert text == b'hello, world!\n{"key": "val"}\n3…\n2…\n1…\n2020-01-01T00:00:05'
```

And even an out-of-box Kubernetes stateful server:

```python
import aiohttp
import kmock
import pytest

@pytest.fixture
def k8surl() -> str:
  return 'http://localhost'

async def test_k8s_out_of_the_box(kmock: kmock.RawHandler, k8surl: str) -> None:
    async with aiohttp.ClientSession(base_url=k8surl) as session:
        pod1 = {'metadata': {'name': 'pod1'}, 'spec': {'key': 'val'}}
        pod2 = {'metadata': {'name': 'pod1'}, 'spec': {'key': 'val'}}
        await session.post('/api/v1/namespace/default/pods', json=pod1)
        await session.post('/api/v1/namespace/default/pods', json=pod2)
        resp = await session.get('/api/v1/namespace/default/pods')
        data = await resp.json()
        assert data['items'] == [pod1, pod2]

    assert len(kmock[kmock.LIST]) == 1
    assert len(kmock[kmock.resource['pods']]) == 3
    assert kmock[kmock.resource('v1/pods')][-1].method == 'GET'
```
