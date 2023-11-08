- HTTPS support with self-signed certs as in kopf's webhooks (as long as the CA is respected by the client, which is under our control too (in fixtures)).
- Should we react to NotImplemented, NotImplementedError, ConnectionError, ConnectionAbortedError, ConnectionRefusedError, ConnectionResetError, InterruptedError, PermissionError with some special behavior? https://docs.python.org/3/library/exceptions.html
- DO reacto to StopAsyncIteration the same as to StopIteration
- after_version, before_version, at_version: str|None
       make the version numeric (that's not what K8s does, but we can afford to do it).
       increment it on every change? or on every request, incl GETs?
- after_looptime, before_looptime, after_delay, before_delay: float|None


- make & publish `pytest-janitor`:
  - strict warnings
  - resource leak checks
  - automatic asyncio task running & killing
  - automatic threads running & joining (& killing?)
  - automatic fixture-tasks, if possible?
  - use it for `background_daemon_killer`, `watcher_in_background`

```python
@pytest.fixture
@janitor.task
async def bg_runner(kmock):
    while True:
        kmock[...] << b'hello'
        await asyncio.sleep(1)


@pytest.fixture
@janitor.task
async def watcher_in_background(settings, resource, worker_spy, stream):

    # Prevent remembering the streaming objects in the mocks.
    async def do_nothing(*args, **kwargs):
        pass

    # Prevent any real streaming for the very beginning, before it even starts.
    stream.feed([])

    # Spawn a watcher in the background.
    await watcher(
        namespace=None,
        resource=resource,
        settings=settings,
        processor=do_nothing,
    )
```
