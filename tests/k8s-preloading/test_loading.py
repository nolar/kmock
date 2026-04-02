import bz2
import gzip
import json
from pathlib import Path

import pytest

from kmock._internal.k8s_views import ResourcesArray

FIXTURES_DIR = Path(__file__).parent / 'fixtures'


@pytest.fixture()
def sample_json() -> str:
    return (FIXTURES_DIR / 'resources.json').read_text()


def test_load_bundled() -> None:
    resources = ResourcesArray()
    resources.load_bundled()
    assert len(resources) >= 10  # roughly 98 or so, can vary when updated
    pods = resources['v1/pods']
    assert pods.kind == 'Pod'
    assert pods.namespaced is True


def test_load_data_str(sample_json: str) -> None:
    resources = ResourcesArray()
    resources.load_data(sample_json)
    assert len(resources) == 3  # pods, services, deployments
    assert 'v1/pods' in resources
    assert 'v1/services' in resources
    assert 'apps/v1/deployments' in resources


def test_load_data_bytes(sample_json: str) -> None:
    resources = ResourcesArray()
    resources.load_data(sample_json.encode('utf-8'))
    assert len(resources) == 3  # pods, services, deployments
    assert 'v1/pods' in resources
    assert 'v1/services' in resources
    assert 'apps/v1/deployments' in resources


def test_load_path_str(tmp_path: Path, sample_json: str) -> None:
    p = tmp_path / 'resources.json'
    p.write_text(sample_json)
    resources = ResourcesArray()
    resources.load_path(str(p))
    assert len(resources) == 3  # pods, services, deployments
    assert 'v1/pods' in resources
    assert 'v1/services' in resources
    assert 'apps/v1/deployments' in resources


def test_load_path_pathlib(tmp_path: Path, sample_json: str) -> None:
    p = tmp_path / 'resources.json'
    p.write_text(sample_json)
    resources = ResourcesArray()
    resources.load_path(p)
    assert len(resources) == 3  # pods, services, deployments
    assert 'v1/pods' in resources
    assert 'v1/services' in resources
    assert 'apps/v1/deployments' in resources


def test_load_path_gz(tmp_path: Path, sample_json: str) -> None:
    p = tmp_path / 'resources.json.gz'
    with gzip.open(p, 'wt', encoding='utf-8') as f:
        f.write(sample_json)
    resources = ResourcesArray()
    resources.load_path(p)
    assert len(resources) == 3  # pods, services, deployments
    assert 'v1/pods' in resources
    assert 'v1/services' in resources
    assert 'apps/v1/deployments' in resources


def test_load_path_bz2(tmp_path: Path, sample_json: str) -> None:
    p = tmp_path / 'resources.json.bz2'
    with bz2.open(p, 'wt', encoding='utf-8') as f:
        f.write(sample_json)
    resources = ResourcesArray()
    resources.load_path(p)
    assert len(resources) == 3  # pods, services, deployments
    assert 'v1/pods' in resources
    assert 'v1/services' in resources
    assert 'apps/v1/deployments' in resources


def test_load_path_zst(tmp_path: Path, sample_json: str) -> None:
    zstd = __import__('pytest').importorskip('compression.zstd')  # python 3.14+
    p = tmp_path / 'resources.zst'
    with zstd.open(p, 'wt', encoding='utf-8') as f:
        f.write(sample_json)
    resources = ResourcesArray()
    resources.load_path(p)
    assert len(resources) == 3  # pods, services, deployments
    assert 'v1/pods' in resources
    assert 'v1/services' in resources
    assert 'apps/v1/deployments' in resources


def test_load_path_not_found(tmp_path: Path) -> None:
    p = tmp_path / 'nonexistent-resources.json'
    resources = ResourcesArray()
    with pytest.raises(FileNotFoundError):
        resources.load_path(p)


def test_load_resource_fields(sample_json: str) -> None:
    resources = ResourcesArray()
    resources.load_data(sample_json)
    pods = resources['v1/pods']
    assert pods.kind == 'Pod'
    assert pods.singular == 'pod'
    assert pods.namespaced is True
    assert pods.verbs == {'get', 'list', 'create', 'update', 'patch', 'delete', 'deletecollection', 'watch'}
    assert pods.shortnames == {'po'}
    assert pods.categories == {'all'}


def test_load_subresources(sample_json: str) -> None:
    resources = ResourcesArray()
    resources.load_data(sample_json)
    assert resources['v1/pods'].subresources == {'status'}
    assert resources['v1/services'].subresources == set()
    assert resources['apps/v1/deployments'].subresources == {'status', 'scale'}


def test_load_additive(sample_json: str) -> None:
    extra = [{'apiVersion': 'v1', 'kind': 'APIResourceList', 'groupVersion': 'batch/v1',
              'resources': [
                  {'name': 'jobs', 'singularName': 'job', 'namespaced': True, 'kind': 'Job', 'verbs': ['get', 'list']},
              ]}]
    resources = ResourcesArray()
    resources.load_data(sample_json)
    resources.load_data(json.dumps(extra))
    assert 'v1/pods' in resources
    assert 'batch/v1/jobs' in resources


def test_load_last_write_wins() -> None:
    doc1 = [{'apiVersion': 'v1', 'kind': 'APIResourceList', 'groupVersion': 'v1',
             'resources': [{'name': 'pods', 'kind': 'Pod', 'namespaced': True, 'verbs': ['get']}]}]
    doc2 = [{'apiVersion': 'v1', 'kind': 'APIResourceList', 'groupVersion': 'v1',
             'resources': [{'name': 'pods', 'kind': 'PodOverridden', 'namespaced': True, 'verbs': ['get', 'list']}]}]
    resources = ResourcesArray()
    resources.load_data(json.dumps(doc1))
    resources.load_data(json.dumps(doc2))
    assert resources['v1/pods'].kind == 'PodOverridden'


def test_load_missing_kind() -> None:
    bad = [{'apiVersion': 'v1', 'groupVersion': 'v1', 'resources': []}]
    resources = ResourcesArray()
    with pytest.raises(ValueError, match="kind"):
        resources.load_data(json.dumps(bad))


def test_load_wrong_kind() -> None:
    bad = [{'apiVersion': 'v1', 'kind': 'APIGroupList', 'groupVersion': 'v1', 'resources': []}]
    resources = ResourcesArray()
    with pytest.raises(ValueError, match="kind"):
        resources.load_data(json.dumps(bad))


def test_load_wrong_api_version() -> None:
    bad = [{'apiVersion': 'v2', 'kind': 'APIResourceList', 'groupVersion': 'v1', 'resources': []}]
    resources = ResourcesArray()
    with pytest.raises(ValueError, match="apiVersion"):
        resources.load_data(json.dumps(bad))


def test_load_missing_group_version() -> None:
    bad = [{'apiVersion': 'v1', 'kind': 'APIResourceList', 'resources': []}]
    resources = ResourcesArray()
    with pytest.raises(ValueError, match="groupVersion"):
        resources.load_data(json.dumps(bad))


def test_load_no_api_version_allowed() -> None:
    """The core /api/v1 response often omits apiVersion -- this must work."""
    doc = [{'kind': 'APIResourceList', 'groupVersion': 'v1',
            'resources': [{'name': 'pods', 'kind': 'Pod', 'namespaced': True, 'verbs': ['get']}]}]
    resources = ResourcesArray()
    resources.load_data(json.dumps(doc))
    assert 'v1/pods' in resources
