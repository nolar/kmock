import asyncio
import json
from typing import Any

import pytest

from kmock import KubernetesEmulator, KubernetesError, clusterwide, namespace, resource

pytestmark = pytest.mark.kmock(cls=KubernetesEmulator)


@pytest.fixture(autouse=True)
def _nondiscoverable(kmock: KubernetesEmulator) -> None:
    # Noisy non-discoverable partial resource filters — to increase the branch coverage.
    # Only full 3-component resource identifiers are visible to the API discovery.
    kmock[resource(version='v1', plural='unrelated'), clusterwide()] << None
    kmock[resource(group='kopf.dev', plural='unrelated'), clusterwide()] << None
    kmock[resource(group='kopf.dev', version='v1'), clusterwide()] << None
    kmock[resource(version='v1', plural='unrelated'), namespace('ns')] << None
    kmock[resource(group='kopf.dev', plural='unrelated'), namespace('ns')] << None
    kmock[resource(group='kopf.dev', version='v1'), namespace('ns')] << None
    kmock[resource(group='', plural='unrelated'), clusterwide()] << None
    kmock[resource(group='', version='v1'), clusterwide()] << None
    kmock[resource(group='', plural='unrelated'), namespace('ns')] << None
    kmock[resource(group='', version='v1'), namespace('ns')] << None


async def test_kubernetes_arbitrary_exceptions(kmock: KubernetesEmulator) -> None:
    kmock['/'] << ZeroDivisionError("boo!")
    resp = await kmock.get('/')
    data = await resp.json()
    assert data['apiVersion'] == 'v1'
    assert data['kind'] == 'Status'
    assert data['code'] == 500
    assert data['reason'] == 'ZeroDivisionError'
    assert data['message'] == "ZeroDivisionError('boo!')"


async def test_kubernetes_specialised_exceptions(kmock: KubernetesEmulator) -> None:
    kmock['/'] << KubernetesError(status=567, reason="oops", message="boo!")
    resp = await kmock.get('/')
    data = await resp.json()
    assert data['apiVersion'] == 'v1'
    assert data['kind'] == 'Status'
    assert data['code'] == 567
    assert data['reason'] == 'oops'
    assert data['message'] == "boo!"


async def test_kubernetes_streaming_exceptions(kmock: KubernetesEmulator) -> None:
    kmock['/'] << ({}, ZeroDivisionError("boo!"))
    resp = await kmock.get('/')
    text = await resp.text()
    lines = text.splitlines()
    assert len(lines) == 2
    assert lines[0] == '{}'

    event = json.loads(lines[1])
    assert event['type'] == 'ERROR'

    data = event['object']
    assert data['apiVersion'] == 'v1'
    assert data['kind'] == 'Status'
    assert data['code'] == 500
    assert data['reason'] == 'ZeroDivisionError'
    assert data['message'] == "ZeroDivisionError('boo!')"


async def test_empty_server_resources(kmock: KubernetesEmulator) -> None:
    resp = await kmock.get('/')
    data = await resp.json()
    assert set(data['paths']) == {'/', '/api', '/apis', '/version'}

    resp = await kmock.get('/api')
    data = await resp.json()
    assert set(data) == {'versions'}  # strictly control the unexpected extra keys
    assert set(data['versions']) == {'v1'}

    resp = await kmock.get('/apis')
    data = await resp.json()
    assert set(data) == {'groups'}  # strictly control the unexpected extra keys
    assert not data['groups']


async def test_root_discovery_with_coreapi(kmock: KubernetesEmulator) -> None:
    kmock.resources['v1/pods'] = kmock.ResourceInfo()
    resp = await kmock.get('/')
    data = await resp.json()
    assert set(data['paths']) == {'/', '/api', '/apis', '/version', '/api/v1'}

    resp = await kmock.get('/api')
    data = await resp.json()
    assert set(data) == {'versions'}  # strictly control the unexpected extra keys
    assert set(data['versions']) == {'v1'}

    resp = await kmock.get('/apis')
    data = await resp.json()
    assert set(data) == {'groups'}  # strictly control the unexpected extra keys
    assert not data['groups']


async def test_root_discovery_with_group(kmock: KubernetesEmulator) -> None:
    kmock.resources['kopf.dev/v1/kopfexamples'] = kmock.ResourceInfo()
    resp = await kmock.get('/')
    data = await resp.json()
    assert set(data['paths']) == {'/', '/api', '/apis', '/version', '/apis/kopf.dev', '/apis/kopf.dev/v1'}

    resp = await kmock.get('/api')
    data = await resp.json()
    assert set(data) == {'versions'}  # strictly control the unexpected extra keys
    assert set(data['versions']) == {'v1'}

    resp = await kmock.get('/apis')
    data = await resp.json()
    assert set(data) == {'groups'}  # strictly control the unexpected extra keys
    assert len(data['groups']) == 1
    assert data['groups'][0]['name'] == 'kopf.dev'
    assert data['groups'][0]['versions'] == [{'version': 'v1', 'groupVersion': 'kopf.dev/v1'}]
    assert data['groups'][0]['preferredVersion'] == {'version': 'v1', 'groupVersion': 'kopf.dev/v1'}


async def test_group_discovery(kmock: KubernetesEmulator) -> None:
    kmock.resources['kopf.dev/v1/kopfexamples'] = kmock.ResourceInfo()
    resp = await kmock.get('/apis/kopf.dev')
    data = await resp.json()
    assert data['apiVersion'] == 'v1'
    assert data['kind'] == 'APIGroup'
    assert data['name'] == 'kopf.dev'
    assert data['versions'] == [{'version': 'v1', 'groupVersion': 'kopf.dev/v1'}]
    assert data['preferredVersion'] == {'version': 'v1', 'groupVersion': 'kopf.dev/v1'}


async def test_version_discovery_of_coreapi_from_filters(kmock: KubernetesEmulator) -> None:
    # The extended information and sub-resources are not available in filters.
    kmock[kmock.resource('v1/pods')] << None  # strictly a filter!
    resp = await kmock.get('/api/v1')
    data = await resp.json()
    assert data['apiVersion'] == 'v1'
    assert data['kind'] == 'APIResourceList'
    assert len(data['resources']) == 1
    assert data['resources'][0]['name'] == 'pods'
    assert data['resources'][0]['kind'] == 'Pods'
    assert data['resources'][0]['singularName'] == 'pods'
    assert not data['resources'][0]['shortNames']
    assert not data['resources'][0]['categories']
    assert not data['resources'][0]['verbs']


async def test_version_discovery_of_coreapi_from_resources(kmock: KubernetesEmulator) -> None:
    # The extended information is only used for discovery, so only in this test.
    kmock.resources['v1/pods'] = kmock.ResourceInfo(
        kind='Pod', singular='pod',
        shortnames={'po'}, subresources={'sub'},
        categories={'cat'}, verbs={'get', 'post'},
    )
    resp = await kmock.get('/api/v1')
    data = await resp.json()
    assert data['apiVersion'] == 'v1'
    assert data['kind'] == 'APIResourceList'
    assert len(data['resources']) == 2
    assert data['resources'][0]['name'] == 'pods'
    assert data['resources'][1]['name'] == 'pods/sub'
    assert data['resources'][0]['kind'] == 'Pod'
    assert data['resources'][1]['kind'] == 'Pod'
    assert data['resources'][0]['singularName'] == 'pod'
    assert data['resources'][1]['singularName'] == 'pod'
    assert set(data['resources'][0]['shortNames']) == {'po'}
    assert set(data['resources'][1]['shortNames']) == {'po'}
    assert set(data['resources'][0]['categories']) == {'cat'}
    assert set(data['resources'][1]['categories']) == {'cat'}
    assert set(data['resources'][0]['verbs']) == {'get', 'post'}
    assert set(data['resources'][1]['verbs']) == {'get', 'post'}


async def test_version_discovery_of_groups_from_filters(kmock: KubernetesEmulator) -> None:
    # The extended information and sub-resources are not available in filters.
    kmock[kmock.resource('kopf.dev/v1/kopfexamples')] << None  # strictly a filter!
    resp = await kmock.get('/apis/kopf.dev/v1')
    data = await resp.json()
    assert data['apiVersion'] == 'v1'
    assert data['kind'] == 'APIResourceList'
    assert len(data['resources']) == 1
    assert data['resources'][0]['name'] == 'kopfexamples'
    assert data['resources'][0]['kind'] == 'Kopfexamples'
    assert data['resources'][0]['singularName'] == 'kopfexamples'
    assert not data['resources'][0]['shortNames']
    assert not data['resources'][0]['categories']
    assert not data['resources'][0]['verbs']


async def test_version_discovery_of_groups_from_resources(kmock: KubernetesEmulator) -> None:
    # The extended information is only used for discovery, so only in this test.
    kmock.resources['kopf.dev/v1/kopfexamples'] = kmock.ResourceInfo(
        kind='KopfExample', singular='kopfexample',
        shortnames={'kex'}, subresources={'sub'},
        categories={'cat'}, verbs={'get', 'post'},
    )
    resp = await kmock.get('/apis/kopf.dev/v1')
    data = await resp.json()
    assert data['apiVersion'] == 'v1'
    assert data['kind'] == 'APIResourceList'
    assert len(data['resources']) == 2
    assert data['resources'][0]['name'] == 'kopfexamples'
    assert data['resources'][1]['name'] == 'kopfexamples/sub'
    assert data['resources'][0]['kind'] == 'KopfExample'
    assert data['resources'][1]['kind'] == 'KopfExample'
    assert data['resources'][0]['singularName'] == 'kopfexample'
    assert data['resources'][1]['singularName'] == 'kopfexample'
    assert set(data['resources'][0]['shortNames']) == {'kex'}
    assert set(data['resources'][1]['shortNames']) == {'kex'}
    assert set(data['resources'][0]['categories']) == {'cat'}
    assert set(data['resources'][1]['categories']) == {'cat'}
    assert set(data['resources'][0]['verbs']) == {'get', 'post'}
    assert set(data['resources'][1]['verbs']) == {'get', 'post'}


@pytest.mark.parametrize('url', ['/api/v1', '/apis/kopf.dev/v1'])
async def test_discovery_skips_unrelated_filters(kmock: KubernetesEmulator, url: str) -> None:
    kmock[resource('', 'v1', 'pods')] << None
    kmock[resource('kopf.dev', 'v1', 'kopfexamples')] << None
    kmock[resource('unrelated.dev', 'v1', 'distractor')] << None
    resp = await kmock.get(url)
    data = await resp.json()
    assert data['apiVersion'] == 'v1'
    assert data['kind'] == 'APIResourceList'
    assert len(data['resources']) == 1
    assert data['resources'][0]['name'] in {'pods', 'kopfexamples'}  # but not a distractor!


@pytest.mark.parametrize('url', ['/api/v1', '/apis/kopf.dev/v1'])
async def test_discovery_skips_unrelated_resources(kmock: KubernetesEmulator, url: str) -> None:
    kmock.resources['', 'v1', 'pods'] = kmock.ResourceInfo()
    kmock.resources['kopf.dev', 'v1', 'kopfexamples'] = kmock.ResourceInfo()
    kmock.resources['unrelated.dev', 'v1', 'distractor'] = kmock.ResourceInfo()
    resp = await kmock.get(url)
    data = await resp.json()
    assert data['apiVersion'] == 'v1'
    assert data['kind'] == 'APIResourceList'
    assert len(data['resources']) == 1
    assert data['resources'][0]['name'] in {'pods', 'kopfexamples'}  # but not a distractor!


async def test_server_version(kmock: KubernetesEmulator) -> None:
    resp = await kmock.get('/version')
    data = await resp.json()
    assert data['major'] == '1'
    assert data['minor'] == '26'


async def test_initial_empty_state(kmock: KubernetesEmulator) -> None:
    assert not kmock.objects
    kmock.resources['kopf.dev/v1/kopfexamples'].namespaced = True

    resp = await kmock.get('/apis/kopf.dev/v1/kopfexamples')
    data = await resp.json()
    assert data['items'] == []

    resp = await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples')
    data = await resp.json()
    assert data['items'] == []


@pytest.mark.parametrize('nsurl', [
    pytest.param('', id='clusterwide'),
    pytest.param('namespaces/ns/', id='namespaced'),
])
async def test_listing_of_empty_but_known(kmock: KubernetesEmulator, nsurl: str) -> None:
    kmock.resources['kopf.dev/v1/kopfexamples'] = kmock.ResourceInfo()
    resp = await kmock.get(f'/apis/kopf.dev/v1/{nsurl}kopfexamples')
    data = await resp.json()
    assert data['items'] == []


@pytest.mark.parametrize('ns, nsurl', [
    pytest.param(None, '', id='clusterwide'),
    pytest.param('ns', 'namespaces/ns/', id='namespaced'),
])
async def test_listing_of_existing(kmock: KubernetesEmulator, nsurl: str, ns: str | None) -> None:
    body1 = {'spec': 123}
    body2 = {'spec': 456}
    kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'] = body1
    kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n2'] = body2
    resp = await kmock.get(f'/apis/kopf.dev/v1/{nsurl}kopfexamples')
    data = await resp.json()
    assert resp.status == 200
    assert data['items'] == [body1, body2]


async def test_listing_cross_namespaces(kmock: KubernetesEmulator) -> None:
    kmock.objects['kopf.dev/v1/kopfexamples', 'unrelated-ns', 'n1'] = {}
    resp = await kmock.get('/apis/kopf.dev/v1/namespaces/ns/kopfexamples')
    data = await resp.json()
    assert resp.status == 200
    assert data['items'] == []


# Only that way: a cluster-wide request sees all namespaces, but not vice versa.
async def test_listing_of_all_namespaces(kmock: KubernetesEmulator) -> None:
    kmock.objects['kopf.dev/v1/kopfexamples', 'ns', 'n1'] = {'spec': 123}
    resp = await kmock.get('/apis/kopf.dev/v1/kopfexamples')
    data = await resp.json()
    assert resp.status == 200
    assert data['items'] == [{'spec': 123}]


@pytest.mark.parametrize('nsurl', [
    pytest.param('', id='clusterwide'),
    pytest.param('namespaces/ns/', id='namespaced'),
])
async def test_listing_with_unrelated(kmock: KubernetesEmulator, nsurl: str) -> None:
    kmock.objects['kopf.dev/v1/unrelated', 'ns', 'n1'] = {'spec': 999}
    kmock.objects['kopf.dev/v1/kopfexamples', 'ns', 'n1'] = {'spec': 123}
    resp = await kmock.get(f'/apis/kopf.dev/v1/{nsurl}kopfexamples')
    data = await resp.json()
    assert resp.status == 200
    assert data['items'] == [{'spec': 123}]


@pytest.mark.parametrize('nsurl', [
    pytest.param('', id='clusterwide'),
    pytest.param('namespaces/ns/', id='namespaced'),
])
async def test_listing_of_unknown(kmock: KubernetesEmulator, nsurl: str) -> None:
    kmock.resources['kopf.dev/v1/unrelated-distractor'] = kmock.ResourceInfo()
    resp = await kmock.get(f'/apis/kopf.dev/v1/{nsurl}unknownresources')
    assert resp.status == 404


@pytest.mark.parametrize('ns, nsurl', [
    pytest.param(None, '', id='clusterwide'),
    pytest.param('ns', 'namespaces/ns/', id='namespaced'),
])
async def test_fetching_of_existing(kmock: KubernetesEmulator, ns: str | None, nsurl: str) -> None:
    body1 = {'spec': 123}
    kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'] = body1
    resp = await kmock.get(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/n1')
    data = await resp.json()
    assert resp.status == 200
    assert data == body1


@pytest.mark.parametrize('nsurl', [
    pytest.param('', id='clusterwide'),
    pytest.param('namespaces/ns/', id='namespaced'),
])
async def test_fetching_cross_namespaces(kmock: KubernetesEmulator, nsurl: str) -> None:
    kmock.objects['kopf.dev/v1/kopfexamples', 'another-ns', 'n1'] = {}
    resp = await kmock.get(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/n1')
    data = await resp.json()
    assert resp.status == 404
    assert data['code'] == 404
    assert data['reason'] == 'Object Not Found'


@pytest.mark.parametrize('nsurl', [
    pytest.param('', id='clusterwide'),
    pytest.param('namespaces/ns/', id='namespaced'),
])
async def test_fetching_of_absent(kmock: KubernetesEmulator, nsurl: str) -> None:
    kmock.resources['kopf.dev/v1/kopfexamples'] = kmock.ResourceInfo()
    resp = await kmock.get(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/nonexistent')
    assert resp.status == 404


@pytest.mark.parametrize('nsurl', [
    pytest.param('', id='clusterwide'),
    pytest.param('namespaces/ns/', id='namespaced'),
])
async def test_fetching_of_unknown(kmock: KubernetesEmulator, nsurl: str) -> None:
    resp = await kmock.get(f'/apis/kopf.dev/v1/{nsurl}unknownresources/n1')
    assert resp.status == 404


@pytest.mark.parametrize('ns, nskey', [
    pytest.param(None, {}, id='clusterwide'),
    pytest.param('ns', {'namespace': 'ns'}, id='namespaced'),
])
async def test_creation_when_absent(kmock: KubernetesEmulator, ns: str | None, nskey: Any) -> None:
    kmock.resources['kopf.dev/v1/kopfexamples'] = kmock.ResourceInfo()
    body1 = {'metadata': {'name': 'n1', **nskey}, 'spec': 123}
    resp = await kmock.post('/apis/kopf.dev/v1/kopfexamples', json=body1)
    data = await resp.json()
    assert resp.status == 200
    assert kmock.Object(data) >= {'spec': 123}
    assert len(kmock.objects) == 1
    assert kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'] >= body1

    # Extra-check via the API:
    resp = await kmock.get('/apis/kopf.dev/v1/kopfexamples')
    data = await resp.json()
    assert resp.status == 200
    assert data['items'] == [body1]


@pytest.mark.parametrize('ns, nskey', [
    pytest.param(None, {}, id='clusterwide'),
    pytest.param('ns', {'namespace': 'ns'}, id='namespaced'),
])
async def test_creation_when_softdeleted(kmock: KubernetesEmulator, ns: str | None, nskey: Any) -> None:
    kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'] = [{}, None]
    body1 = {'metadata': {'name': 'n1', **nskey}, 'spec': 123}
    resp = await kmock.post('/apis/kopf.dev/v1/kopfexamples', json=body1)
    data = await resp.json()
    assert resp.status == 200
    assert kmock.Object(data) >= {'spec': 123}
    assert kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1', -1] >= {'spec': 123}


@pytest.mark.parametrize('ns, nskey', [
    pytest.param(None, {}, id='clusterwide'),
    pytest.param('ns', {'namespace': 'ns'}, id='namespaced'),
])
async def test_creation_over_existing(kmock: KubernetesEmulator, ns: str | None, nskey: Any) -> None:
    kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'] = {}
    body1 = {'metadata': {'name': 'n1', **nskey}}
    resp = await kmock.post('/apis/kopf.dev/v1/kopfexamples', json=body1)
    data = await resp.json()
    assert resp.status == 409
    assert data['code'] == 409
    assert data['reason'] == 'Object Already Exists'


# This is to cover the namespace-narrowing logic of picked objects on cluster-wide POSTs.
async def test_creation_with_same_name_cross_namespace(kmock: KubernetesEmulator) -> None:
    kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'n1'] = {}
    body1 = {'metadata': {'name': 'n1', 'namespace': 'ns2'}}
    resp = await kmock.post('/apis/kopf.dev/v1/kopfexamples', json=body1)
    data = await resp.json()
    assert resp.status == 200
    assert data == body1


@pytest.mark.parametrize('ns, nsurl', [
    pytest.param(None, '', id='clusterwide'),
    pytest.param('ns', 'namespaces/ns/', id='namespaced'),
])
async def test_patching_of_existing(kmock: KubernetesEmulator, ns: str | None, nsurl: str) -> None:
    body1 = {'metadata': {'name': 'n1'}, 'spec': 123}
    patch = {'spec': 456}
    body2 = {'metadata': {'name': 'n1'}, 'spec': 456}
    kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'] = body1
    resp = await kmock.patch(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/n1', json=patch)
    data = await resp.json()
    assert resp.status == 200
    assert data == body2
    assert kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'] == body2


@pytest.mark.parametrize('ns, nsurl', [
    pytest.param(None, '', id='clusterwide'),
    pytest.param('ns', 'namespaces/ns/', id='namespaced'),
])
async def test_patching_of_softdeleted(kmock: KubernetesEmulator, ns: str | None, nsurl: str) -> None:
    kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'] = [{}, None]
    resp = await kmock.patch(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/n1', json={})
    data = await resp.json()
    assert resp.status == 404
    assert data['code'] == 404
    assert data['reason'] == 'Object Not Found'


async def test_patching_of_absent(kmock: KubernetesEmulator) -> None:
    kmock.resources['kopf.dev/v1/kopfexamples'] = kmock.ResourceInfo()
    resp = await kmock.patch('/apis/kopf.dev/v1/kopfexamples/n1', json={})
    data = await resp.json()
    assert resp.status == 404
    assert data['code'] == 404
    assert data['reason'] == 'Object Not Found'


async def test_patching_of_unknown(kmock: KubernetesEmulator) -> None:
    resp = await kmock.patch('/apis/kopf.dev/v1/unknownresources/n1', json={})
    data = await resp.json()
    assert resp.status == 404
    assert data['code'] == 404
    assert data['reason'] == 'Object Not Found'


@pytest.mark.parametrize('ns, nsurl', [
    pytest.param(None, '', id='clusterwide'),
    pytest.param('ns', 'namespaces/ns/', id='namespaced'),
])
async def test_deletion_without_finalizer(kmock: KubernetesEmulator, ns: str | None, nsurl: str) -> None:
    body1 = {'metadata': {'name': 'n1'}, 'spec': 123}
    kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'] = body1
    resp = await kmock.delete(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/n1')
    data = await resp.json()
    assert resp.status == 200
    assert kmock.Object(data) >= {'spec': 123}
    assert kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'].deleted


@pytest.mark.parametrize('ns, nsurl', [
    pytest.param(None, '', id='clusterwide'),
    pytest.param('ns', 'namespaces/ns/', id='namespaced'),
])
async def test_deletion_with_finalizer(kmock: KubernetesEmulator, ns: str | None, nsurl: str) -> None:
    body1 = {'metadata': {'name': 'n1', 'finalizers': ['test']}, 'spec': 123}
    kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'] = body1

    resp = await kmock.delete(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/n1')
    assert resp.status == 200
    assert not kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'].deleted
    assert kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1']['metadata']['deletionTimestamp'] is not None

    patch = {'metadata': {'finalizers': []}}
    resp = await kmock.patch(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/n1', json=patch)
    assert resp.status == 200
    assert kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'].deleted


@pytest.mark.parametrize('ns, nsurl', [
    pytest.param(None, '', id='clusterwide'),
    pytest.param('ns', 'namespaces/ns/', id='namespaced'),
])
async def test_deletion_of_softdeleted(kmock: KubernetesEmulator, ns: str | None, nsurl: str) -> None:
    kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'] = [{}, None]
    resp = await kmock.delete(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/n1')
    data = await resp.json()
    assert resp.status == 404
    assert data['code'] == 404
    assert data['reason'] == 'Object Not Found'


@pytest.mark.parametrize('ns, nsurl', [
    pytest.param(None, '', id='clusterwide'),
    pytest.param('ns', 'namespaces/ns/', id='namespaced'),
])
async def test_deletion_twice(kmock: KubernetesEmulator, ns: str | None, nsurl: str) -> None:
    kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'] = {'metadata': {'finalizers': ['test']}}
    resp = await kmock.delete(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/n1')
    assert resp.status == 200
    assert kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1']['metadata']['deletionTimestamp'] is not None

    ts = kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1']['metadata']['deletionTimestamp']
    resp = await kmock.delete(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/n1')
    assert resp.status == 200
    assert kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1']['metadata']['deletionTimestamp'] == ts


async def test_deletion_of_absent(kmock: KubernetesEmulator) -> None:
    kmock.resources['kopf.dev/v1/kopfexamples'] = kmock.ResourceInfo()
    resp = await kmock.delete('/apis/kopf.dev/v1/kopfexamples/n1')
    data = await resp.json()
    assert resp.status == 404
    assert data['code'] == 404
    assert data['reason'] == 'Object Not Found'


async def test_deletion_of_unknown(kmock: KubernetesEmulator) -> None:
    resp = await kmock.delete('/apis/kopf.dev/v1/unknownresources/n1')
    data = await resp.json()
    assert resp.status == 404
    assert data['code'] == 404
    assert data['reason'] == 'Object Not Found'


@pytest.mark.parametrize('nskey, list_url, obj_url', [
    pytest.param({}, '', '', id='clusterwide'),
    pytest.param({'namespace': 'ns'}, '', 'namespaces/ns/', id='global'),
    pytest.param({'namespace': 'ns'}, 'namespaces/ns/', 'namespaces/ns/', id='namespaced'),
])
async def test_streamed_events(kmock: KubernetesEmulator, list_url: str, obj_url: str, nskey: Any) -> None:
    kmock.resources['kopf.dev/v1/kopfexamples'] = kmock.ResourceInfo()
    body1 = {'metadata': {'name': 'n1', **nskey, 'finalizers': ['test']}, 'spec': 123}
    patch1 = {'spec': 456}
    body2 = {'metadata': {'name': 'n1', **nskey, 'finalizers': ['test']}, 'spec': 456}
    body3 = {'metadata': {'name': 'n1', **nskey, 'finalizers': ['test'], 'deletionTimestamp': ...}, 'spec': 456}
    patch2 = {'metadata': {'finalizers': []}}
    body4 = {'metadata': {'name': 'n1', **nskey, 'finalizers': [], 'deletionTimestamp': ...}, 'spec': 456}

    async with kmock.get(f'/apis/kopf.dev/v1/{list_url}kopfexamples?watch=true') as resp:
        await kmock.post(f'/apis/kopf.dev/v1/{list_url}kopfexamples', json=body1)
        await kmock.patch(f'/apis/kopf.dev/v1/{obj_url}kopfexamples/n1', json=patch1)
        await kmock.delete(f'/apis/kopf.dev/v1/{obj_url}kopfexamples/n1')
        await kmock.patch(f'/apis/kopf.dev/v1/{obj_url}kopfexamples/n1', json=patch2)
        await asyncio.sleep(0.01)  # give it time to feed the events
        payload: bytes = resp.content.read_nowait()
        events = [json.loads(line) for line in payload.splitlines()]

    # NB: The important aspect is the event stream of the deletion with finalizers:
    # - the deletion causes MODIFIED (deletionTimestamp added), but not yet DELETED.
    # - the last patching (finalizers removal) causes MODIFIED+DELETED.
    assert resp.status == 200
    assert len(events) == 5
    assert kmock.Object(events[0]) == {'type': 'ADDED', 'object': body1}  # create
    assert kmock.Object(events[1]) == {'type': 'MODIFIED', 'object': body2}  # patch1
    assert kmock.Object(events[2]) == {'type': 'MODIFIED', 'object': body3}  # delete
    assert kmock.Object(events[3]) == {'type': 'MODIFIED', 'object': body4}  # patch2
    assert kmock.Object(events[4]) == {'type': 'DELETED', 'object': body4}  # patch2


@pytest.mark.parametrize('ns, nsurl', [
    pytest.param(None, '', id='clusterwide'),
    pytest.param('ns', '', id='global'),
    pytest.param('ns', 'namespaces/ns/', id='namespaced'),
])
async def test_streaming_initial(kmock: KubernetesEmulator, nsurl: str, ns: str) -> None:
    kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n1'] = {'spec': 123}
    kmock.objects['kopf.dev/v1/kopfexamples', ns, 'n2'] = {'spec': 456}

    async with kmock.get(f'/apis/kopf.dev/v1/{nsurl}kopfexamples?watch=true') as resp:
        await asyncio.sleep(0.01)  # give it time to feed the events
        payload: bytes = resp.content.read_nowait()
        events = [json.loads(line) for line in payload.splitlines()]

    assert resp.status == 200
    assert len(events) == 2
    assert kmock.Object(events[0]) == {'type': 'ADDED', 'object': {'spec': 123}}
    assert kmock.Object(events[1]) == {'type': 'ADDED', 'object': {'spec': 456}}


async def test_streaming_unrelated_resources(kmock: KubernetesEmulator) -> None:
    async with kmock.get(f'/apis/kopf.dev/v1/namespaces/ns/kopfexamples?watch=true') as resp:
        await kmock.post(f'/apis/kopf.dev/v1/unrelated', json={})
        await asyncio.sleep(0.01)  # give it time to feed the events
        payload: bytes = resp.content.read_nowait()
        events = [json.loads(line) for line in payload.splitlines()]
    assert resp.status == 200
    assert len(events) == 0


async def test_streaming_unrelated_namespaces(kmock: KubernetesEmulator) -> None:
    async with kmock.get(f'/apis/kopf.dev/v1/namespaces/ns/kopfexamples?watch=true') as resp:
        await kmock.post(f'/apis/kopf.dev/v1/namespaces/unrelated/kopfexamples', json={})
        await asyncio.sleep(0.01)  # give it time to feed the events
        payload: bytes = resp.content.read_nowait()
        events = [json.loads(line) for line in payload.splitlines()]
    assert resp.status == 200
    assert len(events) == 0


# Such a generic parameterization is only for the overall test, not for the detailed ones.
# Over-generalisation makes tests difficult to read & maintain — we want all URLs & names nearby.
@pytest.mark.parametrize('nskey, nsurl', [
    pytest.param({}, '', id='clusterwide'),
    pytest.param({'namespace': 'ns1'}, 'namespaces/ns/', id='namespaced'),
])
async def test_lifecycle(kmock: KubernetesEmulator, nskey: dict[str, Any], nsurl: str) -> None:
    kmock.resources['kopf.dev/v1/kopfexamples'] = kmock.ResourceInfo()
    body1 = {'spec': 123, 'metadata': {'name': 'n1', **nskey}}
    patch = {'spec': 456}
    body2 = {'spec': 456, 'metadata': {'name': 'n1', **nskey}}

    resp = await kmock.post(f'/apis/kopf.dev/v1/{nsurl}kopfexamples', json=body1)
    data = await resp.json()
    assert data == body1

    resp = await kmock.get(f'/apis/kopf.dev/v1/{nsurl}kopfexamples')
    data = await resp.json()
    assert data['items'] == [body1]

    resp = await kmock.get(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/n1')
    data = await resp.json()
    assert data == body1

    resp = await kmock.patch(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/n1', json=patch)
    data = await resp.json()
    assert data == body2

    resp = await kmock.get(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/n1')
    data = await resp.json()
    assert data == body2

    # It is unlocked (no finalizers):
    resp = await kmock.delete(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/n1')
    data = await resp.json()
    assert data == body2
    assert resp.status == 200

    resp = await kmock.get(f'/apis/kopf.dev/v1/{nsurl}kopfexamples/n1')
    assert resp.status == 404

    resp = await kmock.get(f'/apis/kopf.dev/v1/{nsurl}kopfexamples')
    data = await resp.json()
    assert resp.status == 200
    assert data['items'] == []

    actions = [req.action.value for req in kmock[resource('kopf.dev', 'v1', 'kopfexamples')]]
    assert actions == ['CREATE', 'LIST', 'FETCH', 'UPDATE', 'FETCH', 'DELETE', 'FETCH', 'LIST']
