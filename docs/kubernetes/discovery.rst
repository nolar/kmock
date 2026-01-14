===================
Resources discovery
===================

:class:`kmock.KubernetesScaffold` (so as its descendant :class:`kmock.KubernetesEmulator`) expose the typical Kubernetes endpoints for the cluster information and resource discovery:

- ``/``
- ``/version``
- ``/api``
- ``/api/v1``
- ``/apis``
- ``/apis/{group}``
- ``/apis/{group}/{version}``

The scaffold & emulator also render the errors in the Kubernetes JSON dict of ``kind: Status`` — the same as Kubernetes itself does.

To discover the information, the API uses the following sources:

- The ``kmock.resources`` associative array — as is, not processed or filtered.
- For the emulator, the ``kmock.objects`` associative array — also not processed or filtered.
- All the regular request criteria with the precisely defined resources, i.e. those with all three identifying fields present: group, version, plural.


Resource identifiers
====================

All three methods allow specifying the resources either as instances of the :class:`kmock.resource`; or instances of any class that has the three identifying fields —``group``, ``version``, ``plural``— such as :class:`kopf.Resource`; or as a string in one of the recognized format with these three fields:

- ``v1/pods``
- ``pods.v1``
- ``kopf.dev/v1/kopfexamples``
- ``kopfexamples.v1.kopf.dev``

For the so called "Core API" (the legacy of Kubernetes before the groups were introduced), the group name is an empty string (``""``), and the version is always ``"v1"`` — specifically this combination is recognized by the resource parser.

Examples addressing the ``kmock.resources`` associative array in all supported ways:

.. code-block:: python

    import kmock

    async def test_resource_addressing(kmock: kmock.KubernetesScaffold) -> None:

        # Explicit kwargs to the resource class:
        kmock.resources[kmock.resource(group='', version='v1', plural='pods')] = {}
        kmock.resources[kmock.resource(group='kopf.dev', version='v1', plural='kopfexamples')] = {}

        # Positional args to the resource class:
        kmock.resources[kmock.resource('', 'v1', 'pods')] = {}
        kmock.resources[kmock.resource('kopf.dev', 'v1', 'kopfexamples')] = {}

        # Parseable strings to the resource class:
        kmock.resources[kmock.resource('v1/pods')] = {}
        kmock.resources[kmock.resource('pods.v1')] = {}
        kmock.resources[kmock.resource('kopf.dev/v1/kopfexamples')] = {}
        kmock.resources[kmock.resource('kopfexamples.v1.kopf.dev')] = {}

        # Parseable strings directly as keys (recommended):
        kmock.resources['v1/pods'] = {}
        kmock.resources['pods.v1'] = {}
        kmock.resources['kopf.dev/v1/kopfexamples'] = {}
        kmock.resources['kopfexamples.v1.kopf.dev'] = {}

For the presence of the resource, the regular payloads are used, so the resource can be specified without the meta-information this way — and still be visible to the cluster & resource discovery:

.. code-block:: python

    import kmock

    async def test_resource_adding_via_criteria(kmock: kmock.KubernetesScaffold) -> None:
        kmock['list kopf.dev/v1/kopfexamples'] << {'items': []}


Resource meta-information
=========================

Only the ``kmock.resources`` associative array allows adding the extended meta-information about the resources beyond the three identifying fields (group, version, plural) — via the :class:`kmock.ResourceInfo` or plain dicts with the same keys. These extra fields/keys include:

- ``kind`` (string, usually capitalized)
- ``singular`` name (string, usally lower-cased)
- ``categories`` (a set of strings)
- ``subresources`` (a set of strings)
- ``shortnames`` (a set of strings; aka aliases)
- ``verbs`` (a set of strings)
- ``namespaced`` flag (boolean; if False, the the cluster-wide resource; if None, then undefined)

The resource meta-information can be added as a single object:

.. code-block:: python

    import kmock

    async def test_resource_information_as_one_object(kmock: kmock.KubernetesScaffold) -> None:
        kmock.resources['v1/pods'] = kmock.ResourceInfo(
            kind='Pod',
            singular='pod',
            shortnames={'po'},
            categories={'category1', 'category2'},
            verbs={'get', 'post', 'patch', 'delete'},
            subresources={'status'},
            namespaced=True,
        )

The resource meta-information can be added as a dictm, in which case it is implicitly converted to a new instance of :class:`kmock.ResourceInfo`:

.. code-block:: python

    import kmock

    async def test_resource_information_as_one_dict(kmock: kmock.KubernetesScaffold) -> None:
        kmock.resources['v1/pods'] = {
            'kind': 'Pod',
            'singular': 'pod',
            'shortnames': {'po'},
            'categories': {'category1', 'category2'},
            'verbs': {'get', 'post', 'patch', 'delete'},
            'subresources': {'status'},
            'namespaced': True,
        }

For brevity, the resource meta-information can be added on a field-by-field basis — in that case, the empty instance of :class:`kmock.ResourceInfo` is created if it is absent:

.. code-block:: python

    import kmock

    async def test_resource_information_field_by_field(kmock: kmock.KubernetesScaffold) -> None:
        kmock.resources['v1/pods'].kind = 'Pod'
        kmock.resources['v1/pods'].singular = 'pod'
        kmock.resources['v1/pods'].shortnames = {'po'}
        kmock.resources['v1/pods'].categories = {'category1', 'category2'}
        kmock.resources['v1/pods'].verbs = {'get', 'post', 'patch', 'delete'}
        kmock.resources['v1/pods'].subresources = {'status'}
        kmock.resources['v1/pods'].namespaced = True

The meta-information is not used anywhere at the runtime of the scaffold or of the emulator, except for the resource discovery endpoints and their responses — which can be used by other Kubernetes clients, such as ``kubectl``:

.. code-block:: python

    import kmock

    async def test_resource_information_discovery(kmock: kmock.KubernetesScaffold) -> None:
        kmock.resources['kopf.dev/v1/kopfexamples'].kind = 'KopfExample'
        kmock.resources['kopf.dev/v1/kopfexamples'].singular = 'kopfexample'
        kmock.resources['kopf.dev/v1/kopfexamples'].shortnames = {'kex'}
        kmock.resources['kopf.dev/v1/kopfexamples'].categories = {'category1', 'category2'}
        kmock.resources['kopf.dev/v1/kopfexamples'].verbs = {'get', 'post', 'patch', 'delete'}
        kmock.resources['kopf.dev/v1/kopfexamples'].subresources = {'status'}
        kmock.resources['kopf.dev/v1/kopfexamples'].namespaced = True

        resp = await kmock.get('/apis/kopf.dev/v1')
        data = await resp.read()
        assert data == {
            'apiVersion': 'v1',
            'kind': 'APIResourceList',
            'groupVersion': f'kopf.dev/v1',
            'resources': [
                {
                    'name': f'kopfexamples',
                    'kind': 'KopfExample',
                    'singularName': 'kopfexample',
                    'shortNames': ['kex'],
                    'categories': ['category1', 'category2'],
                    'verbs': ['get', 'post', 'patch', 'delete'],
                    'namespaced': True,
                },
                {
                    'name': f'kopfexamples/status',
                    'kind': 'KopfExample',
                    'singularName': 'kopfexample',
                    'shortNames': ['kex'],
                    'categories': ['category1', 'category2'],
                    'verbs': ['get', 'post', 'patch', 'delete'],
                    'namespaced': True,
                },
            ],
        }
