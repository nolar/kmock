# Spec: Resource Fetching, Bundling, and Loading

## Purpose and Goals

KMock is a mock Kubernetes API server for testing. Currently, users register
resource metadata (kind, verbs, namespaced, shortnames, etc.) manually via
`kmock.resources['v1/pods'].kind = 'Pod'` one field at a time. This is tedious
when an operator interacts with dozens of resource types, and it makes discovery
responses incomplete or inaccurate.

This feature adds the ability to:

1. **Fetch** all resource metadata from a live Kubernetes cluster and save it
   to a YAML or JSON file.
2. **Bundle** a pre-fetched file with the kmock package so users can load
   realistic resource metadata without a live cluster.
3. **Load** resource metadata from the bundled file or arbitrary user files
   into `kmock.resources` (the `ResourcesArray`), making discovery endpoints
   return realistic responses out of the box.


## File Format

The file format is based on Kubernetes **APIResourceList** — the same structure
returned by `/api/v1` and `/apis/<group>/<version>` endpoints. This is the
native API format and carries all the fields that `ResourceInfo` needs: `kind`,
`name` (plural), `singularName`, `namespaced`, `verbs`, `shortNames`,
`categories`, and subresources (as slashed entries like `pods/status`).

### YAML (default)

Multi-document YAML (`---` separated). Each document is one APIResourceList,
corresponding to one API group-version. Example:

```yaml
---
apiVersion: v1
kind: APIResourceList
groupVersion: "v1"
resources:
  - name: pods
    singularName: pod
    namespaced: true
    kind: Pod
    verbs: [get, list, create, update, patch, delete, deletecollection, watch]
    shortNames: [po]
    categories: [all]
  - name: pods/status
    singularName: ""
    namespaced: true
    kind: Pod
    verbs: [get, patch, update]
  - name: services
    singularName: service
    namespaced: true
    kind: Service
    verbs: [get, list, create, update, patch, delete, watch]
    shortNames: [svc]
    categories: [all]
---
apiVersion: v1
kind: APIResourceList
groupVersion: "apps/v1"
resources:
  - name: deployments
    singularName: deployment
    namespaced: true
    kind: Deployment
    verbs: [get, list, create, update, patch, delete, deletecollection, watch]
    shortNames: [deploy]
    categories: [all]
  - name: deployments/status
    singularName: ""
    namespaced: true
    kind: Deployment
    verbs: [get, patch, update]
  - name: deployments/scale
    singularName: ""
    namespaced: true
    kind: Scale
    group: autoscaling
    version: v1
    verbs: [get, patch, update]
```

### Compatibility with raw API output

The file format is intentionally identical to what the Kubernetes API returns
from `/api/v1` and `/apis/<group>/<version>` endpoints. This means users can
manually dump API responses and load them directly into kmock without any
conversion. For example:

```bash
kubectl get --raw /api/v1 > core-v1.json
kubectl get --raw /apis/apps/v1 >> core-v1.json
```

These raw dumps can then be loaded as-is:

```python
kmock.resources.load(file='./core-v1.json')
```

This is a core functional requirement: any valid APIResourceList response
from a Kubernetes cluster must be loadable without modification. This must
be documented prominently in user-facing documentation.

### Parsing

Since YAML is a superset of JSON, the loader always uses the YAML parser
(`yaml.safe_load_all`) regardless of file extension or content. This means
JSON files provided by users (including raw `kubectl get --raw` output) are
handled transparently on the loading side, even though kmock itself always
writes YAML.


## User-Facing API

### Loading resources

```python
from pathlib import Path

def test_me(kmock):
    # Load the bundled resource file (ships with kmock):
    kmock.resources.load()
    
    # Load a custom file (Path or str):
    kmock.resources.load(file='./my-resources.yaml')
    kmock.resources.load(file=Path('./my-resources.yaml'))
    
    # Load from an IO stream:
    with open('./my-resources.yaml') as f:
        kmock.resources.load(file=f)
    
    # Multiple loads are additive (not destructive):
    kmock.resources.load()                              # builtins
    kmock.resources.load(file='./my-crds.yaml')         # custom resources on top
    
    # Strict mode raises on conflicts:
    kmock.resources.load(file='./a.yaml')
    kmock.resources.load(file='./b.yaml', strict=True)  # raises if overlapping resources differ
```

**Method signature:**

```python
def load(
    self,
    file: str | Path | IO[str] | None = None,
    *,
    strict: bool = False,
) -> None:
```

- `file=None` means load the bundled file.
- `file` accepts `str`, `pathlib.Path`, or any readable IO stream.
- `strict=True` raises an error if a resource being loaded already exists in
  the array with different metadata (any field differs). The resource identity
  is determined by `(group, version, plural)`.
- `strict=False` (default) uses last-write-wins for conflicting resources.
- Returns nothing.

### Dumping resources

```python
import kmock
from pathlib import Path


def dump(kmock: kmock.KubernetesScaffold) -> None:
    # Dump current resources to a file:
    kmock.resources.dump(file='./resources.yaml')
    kmock.resources.dump(file=Path('./resources.yaml'))

    # Dump to an IO stream:
    with open('./resources.yaml', 'w') as f:
        kmock.resources.dump(file=f)
```

**Method signature:**

```python
def dump(
    self,
    file: str | Path | IO[str],
) -> None:
```

- Writes YAML format (multi-document, 2-space indentation).
- Groups resources by their `(group, version)` into separate APIResourceList
  documents.
- Always YAML — JSON output is only available via the CLI.

### Conflict semantics

A **conflict** occurs when two loads provide a resource with the same
`(group, version, plural)` but with different values for any field: `kind`,
`singular`, `namespaced`, `verbs`, `shortNames`, `categories`, or
`subresources`.

- `strict=False` (default): the new values silently overwrite the old ones
  (last-write-wins).
- `strict=True`: raises an exception describing the conflict. The specific
  exception class is an implementation detail but should be descriptive.


## Subresource Handling

In APIResourceList responses, subresources appear as separate entries with
slashed names (e.g., `pods/status`, `deployments/scale`). The dump/fetch
commands store them exactly as the API returns them — as separate entries
in the `resources` array.

The loader must parse the slashed names and attach subresources to their
parent resource's `ResourceInfo.subresources` set. For example, an entry
with `name: pods/status` adds `"status"` to the `subresources` set of the
`pods` resource.

### Open question

The current internal model stores subresources as a `set[str]` of names on
the parent `ResourceInfo`. It may be worth revisiting this to store
subresources as independent `ResourceInfo` entries with their own metadata
(kind, verbs, etc.), since the API does return per-subresource metadata.
This is deferred for now — the current `set[str]` approach is sufficient.


## CLI: `kmock fetch resources`

### Installation

The CLI requires the `kubernetes` Python client, installed via an optional
extra:

```
pip install kmock[fetcher]
```

This adds `kubernetes` as an optional dependency under the `fetcher` extra
in `pyproject.toml`.

### Entry point

The CLI main function lives in `kmock/__main__.py`, enabling both:

- `python -m kmock fetch resources`
- `kmock fetch resources` (via console_scripts)

```toml
[project.scripts]
kmock = "kmock.__main__:main"
```

The `kmock/__main__.py` module imports and delegates to the CLI
implementation in `kmock/_internal/cli.py`. The `__main__.py` file itself
is minimal — just the entry point glue:

```python
from kmock._internal.cli import main

if __name__ == "__main__":
    main()
```

The CLI uses a subcommand structure (`kmock fetch resources`, etc.) because
more subcommands are planned in the future.

### Usage

```
kmock fetch resources [--output-file FILE]
```

- Connects to the current Kubernetes cluster (using the active kubeconfig
  context, same as `kubectl`).
- Iterates over all API groups and versions via the discovery API.
- Collects all APIResourceList responses.
- Writes the result as multi-document YAML (2-space indentation) to stdout
  or to a file.

**Flags:**

- `--output-file FILE` or `-f FILE`: write to file instead of stdout.

### Implementation notes

- Use the official `kubernetes` Python client (`kubernetes.client.ApisApi`
  and similar) to enumerate groups and fetch resource lists.
- The fetch command must work against any Kubernetes cluster version.
- No authentication configuration beyond what `kubernetes.config.load_kube_config()`
  provides by default (i.e., use the active kubeconfig).


## Bundled Resource File

A pre-fetched, gzip-compressed resource file is bundled with the package at:

```
kmock/_internal/data/resources.yaml.gz
```

This file is generated manually by running the fetch command against a recent
Kubernetes cluster, compressing it with gzip, and committing to the repository.
It is regenerated from time to time when deemed necessary — there is no version
pinning or automatic update mechanism. Staleness is acceptable.

### Size estimates (from a default k3d/k3s cluster)

- 29 API group-versions, 160 resource entries (including subresources)
- Uncompressed YAML: ~30 KB
- Gzip-compressed: ~2.9 KB
- Bzip2-compressed: ~2.8 KB (marginal gain over gzip, not worth the extra dependency)

Gzip is used because Python's `gzip` module is in the standard library.

These estimates were obtained using the ad-hoc experiment script
`_fetch_experiment.py` in this spec directory, which fetched resources from
a running k3d/k3s cluster. The raw output also comes to this directory.

The file must be included in the package distribution via `pyproject.toml`
package data configuration.

`kmock.resources.load()` (with no arguments) loads this bundled file using
`importlib.resources` or `pathlib.Path(__file__).parent / 'data/resources.yaml.gz'`
to locate it within the installed package, decompressing it with `gzip.open()`
before passing to the YAML parser.

There is no support for loading user-provided gzip-compressed files via the
`file` parameter. Users who need to load compressed files can decompress
them into an IO stream and pass that to `load(file=stream)`.


## Loading Internals

### Parsing an APIResourceList document

Each YAML document is expected to be a dict with:

- `apiVersion: v1`
- `kind: APIResourceList`
- `groupVersion: "<group>/<version>"` or `"<version>"` (for core API)

Fail loudly if any of these are missing or unexpected.

The `groupVersion` field is parsed:

- `"v1"` → group=`""` (or `None`), version=`"v1"`
- `"apps/v1"` → group=`"apps"`, version=`"v1"`

Each entry in `resources` is processed:

1. If `name` contains a `/` (e.g., `pods/status`), it is a subresource.
   Split on `/` to get parent plural and subresource name. Add the
   subresource name to the parent's `ResourceInfo.subresources` set.
   Skip creating a separate resource entry for it (for now).

2. Otherwise, create/update a `ResourceInfo` with:
   - `kind` from `kind`
   - `singular` from `singularName`
   - `namespaced` from `namespaced`
   - `verbs` from `verbs`
   - `shortnames` from `shortNames`
   - `categories` from `categories`

3. The resource key is `resource(group, version, plural)` where `plural`
   is the `name` field.

### Additive behavior

Multiple `load()` calls accumulate resources. A second load does not clear
previously loaded resources. For each resource in the file:

- If the resource key does not exist: create it.
- If it exists and `strict=False`: overwrite with new values.
- If it exists and `strict=True`: compare all fields. If any differ, raise.

### Error handling

- Malformed YAML: raise (PyYAML's error).
- Document missing `apiVersion`, `kind`, or `groupVersion`: raise with a
  descriptive error message.
- `kind` is not `APIResourceList`: raise.
- `apiVersion` is not `v1`: raise.
- Unexpected/extra fields in resource entries: silently ignore (e.g.,
  `storageVersionHash`).
- File not found: raise (standard IOError).


## Dependencies

### New required dependency

- `PyYAML` — added to `dependencies` in `pyproject.toml`. Required because
  the bundled file loading uses it, and that's core functionality.

### New optional dependency

- `kubernetes` — added under a `fetcher` optional extra:

```toml
[project.optional-dependencies]
fetcher = ["kubernetes"]
```


## Package Structure Changes

```
kmock/
  __main__.py           # NEW: entry point for `python -m kmock` and console_scripts
  _internal/
    cli.py              # NEW: CLI subcommand dispatch and argument parsing
    fetching.py         # NEW: fetch logic (kubernetes client interaction)
    loading.py          # NEW: load/dump logic (YAML parsing, ResourcesArray population)
    data/
      resources.yaml.gz # NEW: bundled resource file (gzip-compressed)
  __init__.py           # possibly export load-related types if needed
```

The `load()` and `dump()` methods are added to `ResourcesArray` in
`k8s_views.py`, but the heavy lifting (YAML parsing, file I/O) is
delegated to `loading.py` to keep `k8s_views.py` focused on the
data structure.


## Deferred / Out of Scope

- **`@pytest.mark.kmock(resources=...)` integration**: abandoned for now.
  Loading is always explicit in test code via `kmock.resources.load()`.
- **JSON output**: not supported. All dumps are YAML.
- **Subresource metadata storage**: the loader discards per-subresource
  metadata (kind, verbs) and only stores the subresource name in the parent's
  `subresources` set. Storing subresources as independent `ResourceInfo`
  entries with full metadata is an open question for later.
- **Bundled file size**: ~2.9 KB gzip-compressed for a default k3d/k3s
  cluster (~30 KB uncompressed). Not a concern.
- **Concurrency safety**: `load()` mutates `ResourcesArray` and is not
  async-safe. This is consistent with how `kmock.resources` is already used —
  population happens during test setup, not during concurrent request handling.
- **`kmock.objects.dump()` and `kmock.objects.load()`**: planned for a future
  spec. The `dump()`/`load()` methods on `ResourcesArray` are not related to
  these future features, but the naming is intentionally parallel.


## Example End-to-End Workflow

### Fetching from a live cluster

```bash
pip install kmock[fetcher]
kmock fetch resources > my-cluster-resources.yaml
kmock fetch resources -f my-cluster-resources.yaml
```

### Using in tests

```python
import pytest
from kmock import KubernetesEmulator

async def test_operator_discovery(kmock):
    # Load all standard k8s resources
    kmock.resources.load()

    # Layer on custom CRDs (fetched from a dev cluster or hand-written)
    kmock.resources.load(file='./tests/fixtures/my-crds.yaml')

    # Now discovery endpoints return realistic responses
    # for both builtins and custom resources
    ...
```

### Dumping from kmock (for debugging/inspection)

```python
async def test_debug(kmock):
    kmock.resources.load()
    kmock.resources['mygroup.io/v1/myresources'].kind = 'MyResource'
    kmock.resources.dump(file='./debug-resources.yaml')
```
