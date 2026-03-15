#!/usr/bin/env python3
"""Ad-hoc experiment: fetch all APIResourceLists from a live cluster."""
import json
import os.path
import yaml
import kubernetes
from kubernetes.client import ApiClient

kubernetes.config.load_kube_config()
client = ApiClient()

documents = []

# Core API: /api/v1
resp = client.call_api('/api/v1', 'GET', _preload_content=False)
data = json.loads(resp[0].data)
documents.append(data)

# Grouped APIs: /apis
resp = client.call_api('/apis', 'GET', _preload_content=False)
groups_data = json.loads(resp[0].data)

for group in groups_data.get('groups', []):
    for version_info in group.get('versions', []):
        gv = version_info['groupVersion']
        try:
            resp = client.call_api(f'/apis/{gv}', 'GET', _preload_content=False)
            data = json.loads(resp[0].data)
            documents.append(data)
        except Exception as e:
            print(f"# SKIP {gv}: {e}")

output_file = os.path.join(os.path.dirname(__file__), '_fetched_resources.yaml')
with open(output_file, 'w') as f:
    for doc in documents:
        # Strip storageVersionHash to reduce noise
        for res in doc.get('resources', []):
            res.pop('storageVersionHash', None)
        yaml.safe_dump(doc, f, default_flow_style=False, indent=2, sort_keys=False)
        f.write('---\n')

import os
size = os.path.getsize(output_file)
total_resources = sum(len(d.get('resources', [])) for d in documents)
total_groups = len(documents)
print(f"Groups/versions: {total_groups}")
print(f"Total resource entries: {total_resources}")
print(f"File size: {size} bytes ({size / 1024:.1f} KB)")
