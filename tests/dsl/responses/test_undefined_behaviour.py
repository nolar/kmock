from kmock import KubernetesEndpointNotFoundError, KubernetesResourceNotFoundError, \
                  KubernetesScaffold, RawHandler, Server


async def test_undefined_behaviour_in_raw_mock() -> None:
    async with RawHandler() as kmock, Server(kmock):
        resp = await kmock.get('/nonexistent')
        text = await resp.read()
        assert resp.status == 500
        assert b'Undefined server behaviour' in text
        assert b'Consider adding a catch-all fallback reaction' in text
        assert len(kmock.errors) == 1
        assert isinstance(kmock.errors[0], NotImplementedError)


async def test_undefined_endpoint_in_kubernetes_mock() -> None:
    async with KubernetesScaffold() as kmock, Server(kmock):
        resp = await kmock.get('/nonexistent')
        data = await resp.json()
        assert resp.status == 404  # there is always a fallback
        assert data['reason'] == 'Endpoint Not Found'
        assert 'The URL was not found' in data['message']
        assert 'Traceback (most recent call last):' in data['details']['traceback']
        assert len(kmock.errors) == 1
        assert isinstance(kmock.errors[0], KubernetesEndpointNotFoundError)


async def test_undefined_resource_group_in_kubernetes_mock() -> None:
    async with KubernetesScaffold() as kmock, Server(kmock):
        resp = await kmock.get('/apis/unexistent.group')
        data = await resp.json()
        assert resp.status == 404  # there is always a fallback
        assert data['reason'] == 'Resource Not Found'
        assert 'The resource is not declared' in data['message']
        assert 'Traceback (most recent call last):' in data['details']['traceback']
        assert len(kmock.errors) == 1
        assert isinstance(kmock.errors[0], KubernetesResourceNotFoundError)


async def test_undefined_resource_version_in_kubernetes_mock() -> None:
    async with KubernetesScaffold() as kmock, Server(kmock):
        resp = await kmock.get('/apis/unexistent.group/v1')
        data = await resp.json()
        assert resp.status == 404  # there is always a fallback
        assert data['reason'] == 'Resource Not Found'
        assert 'The resource is not declared' in data['message']
        assert 'Traceback (most recent call last):' in data['details']['traceback']
        assert len(kmock.errors) == 1
        assert isinstance(kmock.errors[0], KubernetesResourceNotFoundError)
