import collections

from kmock._internal import fetching, references


def parse_group_version(doc: fetching.Doc) -> dict[references.resource, references.ResourceInfo]:
    """
    Parse API responses on a group-verion into resource definitions.

    A single document is one API response from the API discovery endpoint.
    It includes all the primary resources and their sub-resources altogether.
    Separate API groups and versions are fully isolated from each other.

    - ``/api/v1``
    - ``/apis/kopf.dev/v1``

    See an example response with ``kubectl get --raw /api/v1 | jq``.
    """
    api_version = doc.get('apiVersion')
    if api_version is not None and api_version != 'v1':
        raise ValueError(f"Unsupported apiVersion: {api_version!r}, expected 'v1'")

    kind = doc.get('kind')
    if kind != 'APIResourceList':
        raise ValueError(f"Unsupported kind: {kind!r}, expected 'APIResourceList'")

    group_version = doc.get('groupVersion')
    if not group_version:
        raise ValueError("Missing 'groupVersion' field in APIResourceList document")

    if '/' in group_version:
        group, version = group_version.rsplit('/', 1)
    else:
        group = ''
        version = group_version

    # First pass: collect subresources by parent name.
    subresources: dict[str, set[str]] = collections.defaultdict(set)
    for entry in doc.get('resources', []):
        name = entry.get('name', '')
        if '/' in name:
            parent, sub = name.split('/', 1)
            subresources[parent].add(sub)

    # Second pass: create/update ResourceInfo for main resources.
    result: dict[references.resource, references.ResourceInfo] = {}
    for entry in doc.get('resources', []):
        name = entry.get('name', '')
        if '/' in name:
            continue

        resource = references.resource(group, version, name)
        info = references.ResourceInfo(
            kind=entry.get('kind'),
            singular=entry.get('singularName') or None,
            namespaced=entry.get('namespaced'),
            verbs=set(entry.get('verbs', [])),
            shortnames=set(entry.get('shortNames', [])),
            categories=set(entry.get('categories', [])),
            subresources=subresources.get(name, set()),
        )

        result[resource] = info
    return result
