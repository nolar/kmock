===================
Scope & Limitations
===================

Background & Credits
====================

The library was originally designed for testing `Kopf, the Kubernetes Operator framework in Python <https://github.com/nolar/kopf>`_, but extracted as a separate tool. It can be also used to test your operator while migrating to/from Kopf, or for testing any other Kubernetes-related tool (e.g. CLI, a library) written in any language — as long as your tests are in Python.

It is inspired by `aresponses <https://github.com/aresponses/aresponses>`_ by `Bryce Drennan <https://github.com/brycedrennan>`_ but differs from it in that KMock is Kubernetes-specific and makes a few assumptions about the HTTP request structure, which are not applicable to a generic HTTP application. It also does not intercept all the outgoing HTTP calls but only those targeted at a local dummy server. However, it can be used as a replacement of aresponses for arbitrary HTTP requests & broader interception of hostnames (not a drop-in though; requires test rewriting).


Terminology
===========

There are several testing patterns aka "test doubles" involved in testing: dummies, stubs, spies, mocks, and fakes. While these terminology can be questioned and explaining the whole domain is not the purpose of this documentation, it is worth noting that KMock implements most of them at different levels:

* KMock implements the typical structure of the Kubernetes API, thus allowing running the Kubernetes-aiming routines & tools against itself when you need minimally sufficient Kubernetes-like *something* instead of a real heavy-weight Kubernetes cluster — i.e. behaving as a **dummy**.
* KMock responds to the system-under-test with fake responses either provided by users explicitly, or implemented by itself implicitly — i.e. behaving like a **stub**.
* KMock records all the interactions with itself and provides that for assertions in tests — i.e. behaving as a **spy**.
* Kmock matches the actual behaviour of a system-under-test with predefined expectations of such a behaviour based on request filtering criteria, escalating the rest to the default responses like ``404 Not Found`` or ``410 Gone`` or to exceptions — i.e. behaving as a **mock**.

However, KMock does NOT **fake** the full Kubernetes server and does NOT implement all its sophisticated logic of orchestrating the resources, their properties, and life cycles. At best, KMock can be considered as a Kubernetes-like database-over-http tool.
