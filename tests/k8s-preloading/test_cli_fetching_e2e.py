import json
from pathlib import Path

import pytest

from kmock._internal.cli import main


# Non-mocked, real fetching. Requires a real cluster and `kubernetes` installed.
# Runs in a separate CI job. It tests the API communication with the cluster.
def test_fetch_resources_from_cluster(tmp_path: Path) -> None:
    pytest.importorskip('kubernetes')

    out = tmp_path / 'resources.json'
    main(['fetch', 'resources', '-o', str(out)])
    docs = json.loads(out.read_text())
    gvs = {doc['groupVersion'] for doc in docs}
    assert 'v1' in gvs
    assert 'apps/v1' in gvs

    # Spot-check that pods and deployments are present in the right groups.
    core = next(doc for doc in docs if doc['groupVersion'] == 'v1')
    core_names = {r['name'] for r in core['resources']}
    assert 'pods' in core_names

    apps = next(doc for doc in docs if doc['groupVersion'] == 'apps/v1')
    apps_names = {r['name'] for r in apps['resources']}
    assert 'deployments' in apps_names
