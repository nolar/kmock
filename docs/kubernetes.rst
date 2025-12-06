==================
Kubernetes mocking
==================

Scaffold & emulator
===================

KMock provides two classes specialized in the Kubernetes API mocking:

:class:`kmock.KubernetesScaffold` provides the basic API endpoints for the cluster information, resource discovery, and Kubernetes-structured errors, but lacks the persistent storage of the objects. The resource meta-information can be added via ``kmock.resources`` associative array.

:class:`kmock.KubernetesEmulator` provides the same as the scaffold class, plus the persistent storages of the objects that can be added, manipulated, and asserted via the ``kmock.objects`` associative array, so as via the API endpoints for the creation, patching, deleting, listing and watching of the resources.

By default, the pytest ``kmock`` fixture uses the most functionally advanced class — the Kubernetes emulator, unless configured otherwise.

Note that the emulator is not a precise replica of the Kubernetes behaviour — it does not do all the sophisticated logic of special-purpose fields, does not merge lists of items, does not do any background processing. It is essentially a database-over-http with the Kubernetes API URLs — it only stores and retrieves the objects "as is".

The only place where it interprets the data is taking the name and namespace of the newly created objects — to form their identifying address in the associative array. After that, the identifying address is inferred from the URLs of the patching & deleting endpoints, not from the data.


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
--------------------

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
        kmock.resources[kmock.resource(group='', version='v1', plural='pods')] = kmock.ResourceInfo()
        kmock.resources[kmock.resource(group='kopf.dev', version='v1', plural='kopfexamples')] = kmock.ResourceInfo()

        # Positional args to the resource class:
        kmock.resources[kmock.resource('', 'v1', 'pods')] = kmock.ResourceInfo()
        kmock.resources[kmock.resource('kopf.dev', 'v1', 'kopfexamples')] = kmock.ResourceInfo()

        # Parseable strings to the resource class:
        kmock.resources[kmock.resource('v1/pods')] = kmock.ResourceInfo()
        kmock.resources[kmock.resource('pods.v1')] = kmock.ResourceInfo()
        kmock.resources[kmock.resource('kopf.dev/v1/kopfexamples')] = kmock.ResourceInfo()
        kmock.resources[kmock.resource('kopfexamples.v1.kopf.dev')] = kmock.ResourceInfo()

        # Parseable strings directly as keys (recommended):
        kmock.resources['v1/pods'] = kmock.ResourceInfo()
        kmock.resources['pods.v1'] = kmock.ResourceInfo()
        kmock.resources['kopf.dev/v1/kopfexamples'] = kmock.ResourceInfo()
        kmock.resources['kopfexamples.v1.kopf.dev'] = kmock.ResourceInfo()

For the presence of the resource, the regular payloads are used, so the resource can be specified without the meta-information this way — and still be visible to the cluster & resource discovery:

.. code-block:: python

    import kmock

    async def test_resource_adding_via_criteria(kmock: kmock.KubernetesScaffold) -> None:
        kmock['list kopf.dev/v1/kopfexamples'] << {'items': []}


Resource meta-information
-------------------------

Only the ``kmock.resources`` associative array allows adding the extended meta-information about the resources beyond the three identifying fields (group, version, plural) — via the :class:`kmock.ResourceInfo`. These extra fields include:

- kind
- singular name
- categories
- subresources
- short names (aka aliases)
- verbs
- namespaced flag (boolean; if False, the the cluster-wide resource; if None, then undefined)

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


Objects persistence
===================

:class:`kmock.KubernetesEmulator` persists the objects added to the cluster and manipualtes their state both via the API endpoints (such as patching, deleting), so via the direct access to the ``kmock.objects`` associative array.

The key of the ``kmock.objects`` associative array is either the 3-item tuple of ``(resource, namespace, name)``, or the 4-item tuple of ``(resource, namespace, name, version)``. The version can be either a number of the version in the history of object's changes, starting with 0, and supporting the negative indexes (-1 for the last version, -2 for the pre-last, so on), or the version can be a slice of integer indexes to pick the slice of the history. If the version is absent, then the latest version of the object is used.

The value of the ``kmock.objects`` associative array is a versioned dict of all previous states of the objects, with the most recent version exposed directly as keys and values of the versioned dict itself. The past versions can be accessed via the ``.history`` attribute (a sequence of individual object versions).

The following API URLs are available in the Kubernetes emulator:

- ``/``
- ``/version``
- ``/api``
- ``/api/v1``
- ``/api/v1/{plural}``
- ``/api/v1/{plural}/{name}``
- ``/api/v1/namespaces/{namespace}/{plural}``
- ``/api/v1/namespaces/{namespace}/{plural}/{name}``
- ``/apis``
- ``/apis/{group}``
- ``/apis/{group}/{version}``
- ``/apis/{group}/{version}/{plural}``  (cluser-wide access)
- ``/apis/{group}/{version}/{plural}/{name}``  (cluster-wide resources only)
- ``/apis/{group}/{version}/namespaces/{namespace}/{plural}``  (namespaced access)
- ``/apis/{group}/{version}/namespaces/{namespace}/{plural}/{name}``  (namespaced resources only)


Objects pre-population
----------------------

To pre-populate the objects in the Kubernetes cluster, assign the object's content to the ``kmock.objects`` associative array. The key of the array is a triplet of ``(resource, namespace, name)``.

For the cluster-wide objects, namespace should be ``None``. For the namespaced objects, it should be a string.

.. code-block:: python

    import kmock

    async def test_object_prepopulation(kmock: kmock.KubernetesEmulator) -> None:
        kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'name1'] = {'spec': 123}

        # Make sure it is accessible via the API:
        resp = await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/name1')
        data = await resp.json()
        assert rest.status == 200
        assert data == {'spec': 123}


Objects soft-deletion
---------------------

When the object is deleted via the API, its history does not disappear. Instead, a soft-deletion marker ``None`` is stored as the latest version, thus preventing any access to the object as a dict.

After the soft-deletion, a new object with the same identifier (resource, namespace, name) can be created via the API. The soft-deleted objects also disappear from the lists, and accessing them returns HTTP code 404.

.. code-block:: python

    import kmock

    async def test_object_soft_deletion(kmock: kmock.KubernetesEmulator) -> None:
        # Create the object first:
        kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'name1'] = {'spec': 123}

        # Make sure it is accessible via the API:
        resp = await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/name1')
        data = await resp.json()
        assert rest.status == 200
        assert data == {'spec': 123}

        # Soft-delete the object via the API:
        resp = await kmock.delete('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/name1')
        assert resp.status == 200

        # Make sure it is not accessible via the API anymore:
        resp = await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/name1')
        assert rest.status == 404

        # Check its history via the associative array (None is the soft-deletion marker):
        assert ('kopf.dev/v1/kopfexamples', 'ns1', 'name1') in kmock.objects
        assert kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'name1', -1] is None
        assert kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'name1', -2] == {'spec': 123}


Objects hard-deletion
---------------------

When the object is deleted via the Python code, not only the object disappears from the lists & other API endpoints, but all its history also goes away — as if it never existed.

To hard-delete the object, delete its identifying key from the ``kmock.objects`` associative array:

.. code-block:: python

    import kmock

    async def test_object_hard_deletion(kmock: kmock.KubernetesEmulator) -> None:
        # Create the object first:
        kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'name1'] = {'spec': 123}

        # Make sure it is accessible via the API:
        resp = await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/name1')
        data = await resp.json()
        assert rest.status == 200
        assert data == {'spec': 123}

        # Hard-delete the object from the associative array:
        del kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'name1']

        # Make sure it is not accessible anymore (and no history to check for):
        resp = await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/name1')
        assert rest.status == 404
        assert ('kopf.dev/v1/kopfexamples', 'ns1', 'name1') not in kmock.objects


History pre-population
----------------------

To pre-populate the whole history of the object, assign a list consisting of the object's states and/or soft-deletion markers to the ``kmock.objects`` associative array. The key of the array is a triplet of ``(resource, namespace, name)``.

.. code-block:: python

    import kmock

    async def test_history_prepopulation(kmock: kmock.KubernetesEmulator) -> None:
        kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'name1'] = [{'spec': 123}, None]

        # Make sure it is not accessible via the API because it is soft-deleted:
        resp = await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/name1')
        assert rest.status == 404


Objects assertions
==================

Asserting the objects entirely
------------------------------

Both the versioned dict and individual versions of the object behave like regular dicts — i.e. their keys and values can be accessed or iterated, the whole dict can be compared with ``==`` or ``!=``.

In this example, we check and assert that the object precisely equals our expected dict.

.. code-block:: python

    import kmock

    async def test_object_equality(kmock: kmock.KubernetesEmulator) -> None:

        # Create and modify the resource object.
        await kmock.post('/apis/kopf.dev/v1/kopfexamples', json={'spec': 123, 'metadata': {'name': 'n1'}})
        await kmock.patch('/apis/kopf.dev/v1/kopfexamples/n1', json={'spec': 456})

        # Check that the object's latest version is as expected.
        assert kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'n1'] = {'spec': 456, 'metadata': {'name': 'n1'}}}

        # Check that the previous version of the object is also as expected (both ways work).
        assert kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'n1', -2] = {'spec': 123, 'metadata': {'name': 'n1'}}}
        assert kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'n1'].history[-2] = {'spec': 123, 'metadata': {'name': 'n1'}}}


Asserting the objects partially
-------------------------------

In addition to the regular dict operations, the objects can use the set-like comparison operators ``>=`` and ``<=`` to check for the partial dict matching. It means, that the "bigger" dict can contain more actual keys than the "smaller" dict, while the "smaller" dict is a subset of the "bigger" dict and all its keys-values must match.

In this example, we check and assert that the object and its preceding version precisely equal our expected dicts with all their keys.

.. code-block:: python

    import kmock

    async def test_object_equality(kmock: kmock.KubernetesEmulator) -> None:

        # Create and modify the resource object.
        await kmock.post('/apis/kopf.dev/v1/kopfexamples', json={'spec': 123, 'metadata': {'name': 'n1'}})
        await kmock.patch('/apis/kopf.dev/v1/kopfexamples/n1', json={'spec': 456})

        # Check that the object's latest version is as expected.
        assert kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'n1'] = {'spec': 456, 'metadata': {'name': 'n1'}}}

        # Check that the previous version of the object is also as expected (both ways work).
        assert kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'n1', -2] = {'spec': 123, 'metadata': {'name': 'n1'}}}
        assert kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'n1'].history[-2] = {'spec': 123, 'metadata': {'name': 'n1'}}}


Asserting the key presence
--------------------------

To match against fluctuating values, the triple-dot ``...`` (aka ``Ellipsis``) can be used in the pattern. It matches any values, the only requirement is that the key is present. This works both for full or partial assertions of the objects.

A typical example is the ``deletionTimestamp`` of an object that is marked for deletion, but its currently blocked by the finalizers. Not that in this example, the deletion timestamp uses the current time, which is always different, but we only check for the key presence, not the value. Besides the deletion timestamp, the object also has the finalizers in the metadata, so as the spec — but we ignore these fields in the partial match.

.. code-block:: python

    import kmock

    async def test_key_presence(kmock: kmock.KubernetesEmulator) -> None:
        # Pre-populate the object as blocked from deletion with finalizers:
        kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'name1'] = {
            'metadata': {'finalizers': ['blocker']}
            'spec': 123,
        }

        # Soft-delete the object via the API (actually, mark for the future deletion):
        resp = await kmock.delete('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/name1')
        assert rest.status == 200

        # Make sure the object is still present because it is blocked from deletion:
        resp = await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/name1')
        data = await resp.json()
        assert rest.status == 200

        # Check the key presence regardless of the actual value, which can vary:
        assert kmock.Object(data) >= {'metadata': {'deletionTimestamp': ...}}
        assert kmock.Object({'metadata': {'deletionTimestamp': ...}}) <= data


Asserting the arbitrary dicts
-----------------------------

If a dict comes from the API or any third-party client/source, it is not automatically wrapped into the class with the advanced comparison of partial dict matching. The developer can wrap either side using the :class:`kmock.Object` class to activate the partial comparison logic.

Always remember that the pattern must take the "smaller" side in the ``>=`` and ``<=`` operations, and the actual dict must take the "bigger" side as potentially containing more keys & data than expected.

.. code-block:: python

    import kmock

    async def test_api_response(kmock: kmock.KubernetesEmulator) -> None:

        # Create the resource object via the API.
        resp = await kmock.post('/apis/kopf.dev/v1/kopfexamples', json={'spec': 123, 'metadata': {'name': 'n1'}})
        data = await resp.json()  # this is a raw dict
        assert resp.status == 200

        # Check that the object contains the metadata, but ignore its actual value.
        assert kmock.Object(data) >= {'metadata': ..., 'spec': 123}
        assert kmock.Object({'metadata': ..., 'spec': 123}) <= data


History assertions
==================

Every object in the ``kmock.objects`` associative array contains the full history of that object as it is being manipulated via the API (or via the API-like methods :meth:`kmock.KubernetesEmulator.create`, :meth:`kmock.KubernetesEmulator.patch`, :meth:`kmock.KubernetesEmulator.delete` to the extent). In particular, all API deletions are stored as soft-deletion markers ``None``.

To access that history, either the property :attr:`kmock.Object.history`, or the 4th item of the object key in the associative array can be used. However, the history can also be checked as a whole.


Asserting the history entirely
------------------------------

To check if the history precisely match the expected one, use the ``==`` and/or ``!=`` operators.

During this check, the objects are also checked with the precise comparison, so all fields of the actual objects must be expected in the involved patterns. The history must also contain all the expected soft-deletion markers ``None``, and the order of items must match precisely.

In this example, the full actual history of the object is checked and asserted, with all object versions containing all fields. In particular, the metadata fields are preserved in all versions, despite absent in the patches — that is because patches overwrite only the new fields (recursively) and leave the unaffected fields in place.

.. code-block:: python

    import kmock

    async def test_history_precisely(kmock: kmock.KubernetesEmulator) -> None:
        # Declare the resource as supported.
        await kmock.resources['kopf.dev/v1/kopfexamples'] = kmock.ResourceInfo()

        # Create and modify the resource object several times, then soft-delete it.
        await kmock.post('/apis/kopf.dev/v1/kopfexamples', json={'spec': 123, 'metadata': {'name': 'n1'}})
        await kmock.patch('/apis/kopf.dev/v1/kopfexamples/n1', json={'spec': 456})
        await kmock.patch('/apis/kopf.dev/v1/kopfexamples/n1', json={'spec': 789})
        await kmock.delete('/apis/kopf.dev/v1/kopfexamples/n1')

        # Check that the object's history contains at least these two versions.
        assert kmock.objects['kopf.dev/v1/kopfexamples', None, 'n1'].history == [
            {'spec': 123, 'metadata': {'name': 'n1'}},
            {'spec': 456, 'metadata': {'name': 'n1'}},
            {'spec': 789, 'metadata': {'name': 'n1'}},
            None,
        ]


Asserting the history partially
-------------------------------

To check if the history contained particular versions, the partial comparison operators ``>=`` and ``<=`` can be used — similar to set-like checks for the subset inclusion.

During this check, the individual objects are also checked using the partial dict matching, so the objects can contain more actual fields than specified in the historic patterns.

In this example, the history must contain the versions that include spec 123 and 789, but potentially can contain more versions and deletion markers.

.. code-block:: python

    import kmock

    async def test_history_inclusion(kmock: kmock.KubernetesEmulator) -> None:
        # Declare the resource as supported.
        await kmock.resources['kopf.dev/v1/kopfexamples'] = kmock.ResourceInfo()

        # Create and modify the resource object several times, then soft-delete it.
        await kmock.post('/apis/kopf.dev/v1/kopfexamples', json={'spec': 123, 'metadata': {'name': 'n1'}})
        await kmock.patch('/apis/kopf.dev/v1/kopfexamples/n1', json={'spec': 456})
        await kmock.patch('/apis/kopf.dev/v1/kopfexamples/n1', json={'spec': 789})
        await kmock.delete('/apis/kopf.dev/v1/kopfexamples/n1')

        # Check that the object's history contains at least these two versions.
        assert kmock.objects['kopf.dev/v1/kopfexamples', None, 'n1'].history >= [{'spec': 123}, {'spec': 789}]
        assert [{'spec': 123}, {'spec': 789}] <= kmock.objects['kopf.dev/v1/kopfexamples', None, 'n1'].history

Mind that the inclusion checks for one item of the pattern strictly to one version only in the most optimial way, so the single pattern item cannot be used for two or more versions. However, the order of items is irrelevant and resembles sets in this regard, despite expressed as lists (mainly because true sets cannot contains mutable and non-hashable dicts; otherwise it would be sets).
