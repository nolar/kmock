==================
Objects assertions
==================

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
        await kmock.resources['kopf.dev/v1/kopfexamples'] = {}

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
        await kmock.resources['kopf.dev/v1/kopfexamples'] = {}

        # Create and modify the resource object several times, then soft-delete it.
        await kmock.post('/apis/kopf.dev/v1/kopfexamples', json={'spec': 123, 'metadata': {'name': 'n1'}})
        await kmock.patch('/apis/kopf.dev/v1/kopfexamples/n1', json={'spec': 456})
        await kmock.patch('/apis/kopf.dev/v1/kopfexamples/n1', json={'spec': 789})
        await kmock.delete('/apis/kopf.dev/v1/kopfexamples/n1')

        # Check that the object's history contains at least these two versions.
        assert kmock.objects['kopf.dev/v1/kopfexamples', None, 'n1'].history >= [{'spec': 123}, {'spec': 789}]
        assert [{'spec': 123}, {'spec': 789}] <= kmock.objects['kopf.dev/v1/kopfexamples', None, 'n1'].history

Mind that the inclusion checks for one item of the pattern strictly to one version only in the most optimial way, so the single pattern item cannot be used for two or more versions. However, the order of items is irrelevant and resembles sets in this regard, despite expressed as lists (mainly because true sets cannot contains mutable and non-hashable dicts; otherwise it would be sets).
