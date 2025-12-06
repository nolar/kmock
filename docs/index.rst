===============================
HTTP/API/Kubernetes Mock Server
===============================

KMock is a dummy/mock server to mimick the Kubernetes API, any other API, or bare HTTP servers.

The main practical purpose is testing Kubernetes operators developed with Kopf, operators migrated to or from Kopf (whether Pythonic or not), and for testing Kopf itself. Kopf_ is a framework to write Kubernetes operators in Python.

Usually, the developers populate the server with Kubernetes resources, raw request patterns and their supposed responses, then use the locally running server via **any** HTTP/API client of choice, be that in the same framework in Python or something external (e.g. ``curl``, even ``kubectl``). In the end, the developers assert which endpoints were called, with which specific requests, how many times, so on — thus verifying that the developed client works as intended.

KMock runs well with looptime_, the time dilation/contraction library for asyncio & pytest.

.. _kopf: https://kopf.readthedocs.io/
.. _looptime: https://github.com/nolar/looptime

.. toctree::
   :maxdepth: 2
   :caption: Tutorial:

   intro
   usage
   configuration

.. toctree::
   :maxdepth: 2
   :caption: HTTP/API mocking:

   requests
   responses
   streams
   effects
   assertions

.. toctree::
   :maxdepth: 2
   :caption: Kubernetes mocking:

   kubernetes/handlers
   kubernetes/discovery
   kubernetes/persistence
   kubernetes/assertions

.. toctree::
   :maxdepth: 2
   :caption: Developer's manuals:

   ideas
   scope
   linters

.. toctree::
   :maxdepth: 2
   :caption: Reference:

   packages/kmock
