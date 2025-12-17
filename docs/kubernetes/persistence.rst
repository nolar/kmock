===================
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
======================

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
=====================

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
=====================

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
======================

To pre-populate the whole history of the object, assign a list consisting of the object's states and/or soft-deletion markers to the ``kmock.objects`` associative array. The key of the array is a triplet of ``(resource, namespace, name)``.

.. code-block:: python

    import kmock

    async def test_history_prepopulation(kmock: kmock.KubernetesEmulator) -> None:
        kmock.objects['kopf.dev/v1/kopfexamples', 'ns1', 'name1'] = [{'spec': 123}, None]

        # Make sure it is not accessible via the API because it is soft-deleted:
        resp = await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples/name1')
        assert rest.status == 404
