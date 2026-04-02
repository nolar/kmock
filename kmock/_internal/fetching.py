import dataclasses
import fnmatch
import json
from typing import Any, TypedDict, cast


class DocResource(TypedDict, total=False):
    name: str
    kind: str
    singularName: str
    namespaced: bool
    verbs: list[str]
    shortNames: list[str]
    categories: list[str]


class Doc(TypedDict, total=False):
    apiVersion: str
    kind: str
    groupVersion: str
    resources: list[DocResource]


@dataclasses.dataclass(frozen=True)
class Include:
    pattern: str


@dataclasses.dataclass(frozen=True)
class Exclude:
    pattern: str


_PREFILTERS: list[Include | Exclude] = [
    Include(''),           # core API (v1)
    Include('apps'),
    Include('autoscaling'),
    Include('batch'),
    Include('policy'),
    Include('*.k8s.io'),   # all k8s.io subgroups
]

# Drop out all fields other than these — to save on the resource file size.
_DOC_KEYS = {'apiVersion', 'kind', 'groupVersion', 'resources'}
_RESOURCE_KEYS = {'name', 'kind', 'singularName', 'namespaced', 'verbs', 'shortNames', 'categories'}


def _get_group(gv: str) -> str:
    if '/' in gv:
        return gv.rsplit('/', 1)[0]
    return ''


def _match_pattern(gvs: set[str], pattern: str) -> set[str]:
    if '/' in pattern:
        return {gv for gv in gvs if fnmatch.fnmatch(gv, pattern)}
    matched = {gv for gv in gvs if fnmatch.fnmatch(_get_group(gv), pattern)}
    # A trick for "v1", which is formally (group="" version="v1"), but must match "v1",
    # so we check the pattern against the full group-version string with no group parsing.
    if not matched:
        matched = {gv for gv in gvs if fnmatch.fnmatch(gv, pattern)}
    return matched


def _filter_docs(docs: list[Doc], filters: list[Include | Exclude]) -> list[Doc]:
    all_gvs = {doc['groupVersion'] for doc in docs}
    selected: set[str] = set()
    for rule in _PREFILTERS + filters:
        match rule:
            case Include(pattern):
                selected |= _match_pattern(all_gvs, pattern)
            case Exclude(pattern):
                selected -= _match_pattern(all_gvs, pattern)
            case _:
                raise TypeError(f"Unsupported filter rule: {rule!r}")
    return [doc for doc in docs if doc['groupVersion'] in selected]


def _strip_doc(doc: Doc) -> Doc:
    stripped = {k: v for k, v in doc.items() if k in _DOC_KEYS and k != 'resources'}
    stripped['resources'] = [
        {k: v for k, v in entry.items() if k in _RESOURCE_KEYS}
        for entry in doc.get('resources', [])
    ]
    return cast(Doc, stripped)


def fetch_resources(
        *,
        filters: list[Include | Exclude] | None = None,
) -> list[Doc]:
    documents = _api_scan()
    documents = _filter_docs(documents, filters=filters or [])
    documents = [_strip_doc(doc) for doc in documents]
    return documents


# Using raw API would be easier and simpler, but that requires self-made authentication,
# especially different token retrieval and rotation techniques or external auth providers.
# Piggybacking like in Kopf is complicated, sophisticated, and too much for this tool.
# Instead, install the heavy `kubernetes` and let it do the job.
def _api_scan() -> list[Doc]:
    from kubernetes import client, config

    config.load_kube_config()
    api_client = client.ApiClient()

    documents: list[Doc] = []

    # Fetch core API versions from /api
    core_data = _api_get(api_client, '/api')
    for version in core_data.get('versions', []):
        doc = _api_get(api_client, f'/api/{version}')
        documents.append(doc)

    # Fetch API groups from /apis
    groups_data = _api_get(api_client, '/apis')
    for group_info in groups_data.get('groups', []):
        for version_info in group_info.get('versions', []):
            gv = version_info['groupVersion']
            doc = _api_get(api_client, f'/apis/{gv}')
            documents.append(doc)

    return documents


def _api_get(api_client: Any, path: str) -> Any:
    response = api_client.call_api(
        path, 'GET',
        _preload_content=False,
        response_type='str',
    )
    data: bytes = response[0].data
    return json.loads(data)
