import json

import pytest
from pytest_mock import MockerFixture

from kmock._internal.cli import main
from kmock._internal.fetching import _filter_docs


def _make_doc(group_version: str) -> dict:
    return {
        'apiVersion': 'v1',
        'kind': 'APIResourceList',
        'groupVersion': group_version,
        'resources': [
            {'name': 'things', 'kind': 'Thing', 'namespaced': True, 'verbs': ['get', 'list']},
        ],
    }


MULTI_GROUP_DOCS = [
    _make_doc('v1'),
    _make_doc('apps/v1'),
    _make_doc('batch/v1'),
    _make_doc('any.k8s.io/v1'),
    _make_doc('kopf.dev/v1'),
    _make_doc('kopf.dev/v2'),
    _make_doc('helm.cattle.io/v1'),
]


@pytest.fixture(autouse=True)
def _mock_fetcher(mocker: MockerFixture) -> None:
    mocker.patch('kmock._internal.fetching._api_scan', return_value=MULTI_GROUP_DOCS)


def test_default_includes_builtins(capsys: pytest.CaptureFixture[str]) -> None:
    main(['fetch', 'resources'])
    gvs = {doc['groupVersion'] for doc in json.loads(capsys.readouterr().out)}
    assert gvs == {'v1', 'apps/v1', 'batch/v1', 'any.k8s.io/v1'}


def test_include_star_includes_all(capsys: pytest.CaptureFixture[str]) -> None:
    main(['fetch', 'resources', '--include=*'])
    gvs = {doc['groupVersion'] for doc in json.loads(capsys.readouterr().out)}
    assert gvs == {'v1', 'apps/v1', 'batch/v1', 'any.k8s.io/v1',
                   'kopf.dev/v1', 'kopf.dev/v2', 'helm.cattle.io/v1'}


def test_include_group_only(capsys: pytest.CaptureFixture[str]) -> None:
    main(['fetch', 'resources', '--include=kopf.dev'])
    gvs = {doc['groupVersion'] for doc in json.loads(capsys.readouterr().out)}
    assert 'kopf.dev/v1' in gvs
    assert 'kopf.dev/v2' in gvs
    assert 'v1' in gvs  # defaults still present


def test_include_group_version(capsys: pytest.CaptureFixture[str]) -> None:
    main(['fetch', 'resources', '--include=kopf.dev/v1'])
    gvs = {doc['groupVersion'] for doc in json.loads(capsys.readouterr().out)}
    assert 'kopf.dev/v1' in gvs
    assert 'kopf.dev/v2' not in gvs
    assert 'v1' in gvs  # defaults still present


def test_exclude_group_only(capsys: pytest.CaptureFixture[str]) -> None:
    main(['fetch', 'resources', '--exclude=batch'])
    gvs = {doc['groupVersion'] for doc in json.loads(capsys.readouterr().out)}
    assert 'batch/v1' not in gvs
    assert 'v1' in gvs
    assert 'apps/v1' in gvs


def test_exclude_group_version(capsys: pytest.CaptureFixture[str]) -> None:
    main(['fetch', 'resources', '--exclude=apps/v1'])
    gvs = {doc['groupVersion'] for doc in json.loads(capsys.readouterr().out)}
    assert 'apps/v1' not in gvs
    assert 'v1' in gvs
    assert 'batch/v1' in gvs


def test_include_then_exclude_sequential(capsys: pytest.CaptureFixture[str]) -> None:
    main(['fetch', 'resources', '--include=kopf.dev', '--exclude=kopf.dev/v2'])
    gvs = {doc['groupVersion'] for doc in json.loads(capsys.readouterr().out)}
    assert 'kopf.dev/v1' in gvs
    assert 'kopf.dev/v2' not in gvs


def test_include_star_then_exclude(capsys: pytest.CaptureFixture[str]) -> None:
    main(['fetch', 'resources', '--include=*', '--exclude=helm.cattle.io'])
    gvs = {doc['groupVersion'] for doc in json.loads(capsys.readouterr().out)}
    assert 'helm.cattle.io/v1' not in gvs
    assert 'kopf.dev/v1' in gvs
    assert 'kopf.dev/v2' in gvs
    assert 'v1' in gvs


def test_exclude_core_via_bare_version(capsys: pytest.CaptureFixture[str]) -> None:
    main(['fetch', 'resources', '--exclude=v1'])
    gvs = {doc['groupVersion'] for doc in json.loads(capsys.readouterr().out)}
    assert 'v1' not in gvs
    assert 'apps/v1' in gvs


def test_unsupported_filter_rule() -> None:
    with pytest.raises(TypeError, match="Unsupported filter rule"):
        _filter_docs(MULTI_GROUP_DOCS, [object()])
