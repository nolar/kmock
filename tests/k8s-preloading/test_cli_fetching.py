import bz2
import gzip
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from kmock._internal.cli import main

SAMPLE_DOCS = [
    {
        'apiVersion': 'v1',
        'kind': 'APIResourceList',
        'groupVersion': 'v1',
        'resources': [
            {
                'name': 'pods', 'kind': 'Pod', 'namespaced': True, 'verbs': ['get', 'list'],
                'storageVersionHash': 'xPOwRZ+Yhw8=', 'group': '', 'version': 'v1',
            },
        ],
    },
]


def test_cli_no_command() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_cli_fetch_no_subcommand() -> None:
    with pytest.raises(SystemExit):
        main(['fetch'])


def test_cli_fetch_resources_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    with patch('kmock._internal.fetching._api_scan', return_value=SAMPLE_DOCS):
        main(['fetch', 'resources'])
    captured = capsys.readouterr()
    docs = json.loads(captured.out)
    assert len(docs) == 1
    assert docs[0]['groupVersion'] == 'v1'
    assert docs[0]['resources'][0]['name'] == 'pods'


def test_cli_fetch_resources_to_file(tmp_path: Path) -> None:
    out = tmp_path / 'out.json'
    with patch('kmock._internal.fetching._api_scan', return_value=SAMPLE_DOCS):
        main(['fetch', 'resources', '-o', str(out)])
    docs = json.loads(out.read_text())
    assert len(docs) == 1
    assert docs[0]['groupVersion'] == 'v1'
    assert docs[0]['resources'][0]['name'] == 'pods'


def test_cli_fetch_resources_to_gz(tmp_path: Path) -> None:
    out = tmp_path / 'out.json.gz'
    with patch('kmock._internal.fetching._api_scan', return_value=SAMPLE_DOCS):
        main(['fetch', 'resources', '-o', str(out)])
    with gzip.open(out, 'rt', encoding='utf-8') as f:
        docs = json.loads(f.read())
    assert len(docs) == 1
    assert docs[0]['groupVersion'] == 'v1'
    assert docs[0]['resources'][0]['name'] == 'pods'


def test_cli_fetch_resources_to_bz2(tmp_path: Path) -> None:
    out = tmp_path / 'out.json.bz2'
    with patch('kmock._internal.fetching._api_scan', return_value=SAMPLE_DOCS):
        main(['fetch', 'resources', '-o', str(out)])
    with bz2.open(out, 'rt', encoding='utf-8') as f:
        docs = json.loads(f.read())
    assert len(docs) == 1
    assert docs[0]['groupVersion'] == 'v1'
    assert docs[0]['resources'][0]['name'] == 'pods'


def test_cli_fetch_resources_to_zst(tmp_path: Path) -> None:
    zstd = __import__('pytest').importorskip('compression.zstd')  # python 3.14+
    out = tmp_path / 'out.zst'
    with patch('kmock._internal.fetching._api_scan', return_value=SAMPLE_DOCS):
        main(['fetch', 'resources', '-o', str(out)])
    with zstd.open(out, 'rt', encoding='utf-8') as f:
        docs = json.loads(f.read())
    assert len(docs) == 1
    assert docs[0]['groupVersion'] == 'v1'
    assert docs[0]['resources'][0]['name'] == 'pods'


def test_cli_fetch_resources_strips_unknown_fields(capsys: pytest.CaptureFixture[str]) -> None:
    with patch('kmock._internal.fetching._api_scan', return_value=SAMPLE_DOCS):
        main(['fetch', 'resources'])
    captured = capsys.readouterr()
    docs = json.loads(captured.out)
    entry = docs[0]['resources'][0]
    assert 'storageVersionHash' not in entry
    assert 'group' not in entry
    assert 'version' not in entry
