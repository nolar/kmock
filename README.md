# Kubernetes Mock Server in Python

— Kmock-kmock…

— Who's there?

— It's me, a long awaited Kubernetes API mock server!

The rationale behind the library itself is simple: monkey-patching is bad. It makes you test the specific implementation of your HTTP/API client, not the overall communication contract. Realistic servers are an acceptable compromise. The trade-off is only the overhead for the localhost network traffic & HTTP/JSON protocol rendering & parsing. The obvious flaw: you can make mistakes in assumptions what is the supposed response of the remote system.

The rationale behind the library's DSL is simple too: tests must be brief. Brief tests require brief setup & brief assertions. Extensive logic, such as for-cycles, if-conditions, temporary variables, talking with external classes, so on — all this verbosity distracts from the test purpose, leading to fewer tests being written in total.


## All the worst practices at your service

* BECAUSE-I-CAN-driven development — nobody needs it, nobody asked for it.
* Not invented here — there are other alike tools, but I did not like them.
* A 3-week side project 3 years in the making, 90% ready since week four.
* Overengineered from day one.
* Python-based DSL with exsessively overloaded syntax tricks.
* Side effects in supposedly computational operators (`<<`, `>>`).
* Kubernetes in Python. (Who on Earth does that?!)
* Lower-cased naming as in Python builtins rather than CamelCase conventions.
* Around 200%, if not 300% test coverage (some aspects tested twice or more).
* Packaged with setuptools — old but gold.
* Mostly hand-made by organic humans: no code formatters, not much AI.
* Thoughtless AI code & tests for some auxiliary low-level algorithms.
* Contributions are not welcome (but you can try).


## Explanation by examples

```python
import aiohttp


def function_under_test(base_url: str) -> None:
    async with aiohttp.ClientSession(base_url=base_url) as session:
        resp = await session.get('/')
        text = await resp.read()
        resp = await session.post('/hello', json={'name': text.decode()})
        data = await resp.json()
        return data


async def test_me(kmock):
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

Even live streaming is possible. See also:

* [janitor](https://github.com/nolar/janitor) for pytest task- & resource-handling.

```python
import datetime
import asyncio
import aiohttp
import freezegun


@freezegun.freeze_time("2020-01-01T00:00:00")
async def test_k8s_out_of_the_box(kmock, janitor) -> None:

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

    janitor.run(pulse())
    async with aiohttp.ClientSession(base_url='http://localhost', read_timeout=5) as session:
        resp = await session.get('/')
        text = await resp.read()  # this might take some time

    assert text == b'hello, world!\n{"key": "val"}\n3…\n2…\n1…\n2020-01-01T00:00:05'
```

And even an out-of-box Kubernetes stateful server:

```python
import aiohttp
import pytest


@pytest.fixture
def k8surl() -> str:
  return 'http://localhost'


def test_k8s_out_of_the_box(kmock, k8surl: str) -> None:
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
    assert kmock[kmock.resource['pods']][-1].method == 'GET'
```
