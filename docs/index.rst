===============================
HTTP/API/Kubernetes Mock Server
===============================

KMock is a dummy/mock server to mimick the Kubernetes API or any other API.

Usually, the developer populates the server with K8s resources, raw request patterns, and supposed responses, then uses the server via **any** HTTP client, be that in the same framework in Python or something external (e.g. ``curl``, even ``kubectl``). In the end, the developer asserts which endpoints were called, with which specific requests, how many times, so on — thus verifying that the client works as intended.

KMock runs well with looptime_, the time dilation/contraction library for asyncio & pytest.

.. _looptime: https://github.com/nolar/looptime

.. toctree::
   :maxdepth: 2
   :caption: Tutorial:

   contributing
