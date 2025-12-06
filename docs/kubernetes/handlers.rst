===================
Scaffold & emulator
===================

KMock provides two classes specialized in the Kubernetes API mocking:

:class:`kmock.KubernetesScaffold` provides the basic API endpoints for the cluster information, resource discovery, and Kubernetes-structured errors, but lacks the persistent storage of the objects. The resource meta-information can be added via ``kmock.resources`` associative array.

:class:`kmock.KubernetesEmulator` provides the same as the scaffold class, plus the persistent storages of the objects that can be added, manipulated, and asserted via the ``kmock.objects`` associative array, so as via the API endpoints for the creation, patching, deleting, listing and watching of the resources.

By default, the pytest ``kmock`` fixture uses the most functionally advanced class — the Kubernetes emulator, unless configured otherwise.

Note that the emulator is not a precise replica of the Kubernetes behaviour — it does not do all the sophisticated logic of special-purpose fields, does not merge lists of items, does not do any background processing. It is essentially a database-over-http with the Kubernetes API URLs — it only stores and retrieves the objects "as is".

The only place where it interprets the data is taking the name and namespace of the newly created objects — to form their identifying address in the associative array. After that, the identifying address is inferred from the URLs of the patching & deleting endpoints, not from the data.
