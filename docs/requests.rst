=================
Requests matching
=================

Criteria syntax
===============

All criteria for requests come in the square brackets on the ``kmock`` handler — either chained one after another, or listed within the single pair of square brackets.

Some kinds of criteria can be combined into one: for example, HTTP methods and URLs, Kubernetes actions and resources — they can be combined into single strings. These lines are equivalent:

.. code-block:: python

    import kmock

    async def test_root_get(kmock: kmock:RawHandler) -> None:
        kmock['get']['/'] << b'hello'
        kmock['get', '/'] << b'hello'
        kmock['get /'] << b'hello'

By default, when there is no criterion at all, all requests match.


HTTP criteria
=============

Matching HTTP methods
---------------------

A :class:`kmock.method` instance (a string enum) is matched strictly against HTTP verbs of the request (case-insensitive). Strings ``"get"``, ``"post"``, ``"patch"``, ``"put"``, ``"delete"``, ``"options"``, ``"head"`` are automatically recognized as HTTP verbs and require no wrappers:

.. code-block:: python

    import kmock

    async def test_http_methods(kmock: kmock.RawHandler) -> None:
        # Enum values can be used directly.
        kmock[kmock.method.GET] << b'hello'

        # Standard verbs are recognized are simple string.
        kmock['get'] << b'hello'

        # Non-standard verbs MUST be wrapped.
        kmock[kmock.method('store')] << b'hello'


Matching HTTP paths
-------------------

To match against the request path, use the :class:`kmock.path` wrapper for stings and regexps. Both the string and the pattern must match fully, not just prefixed by this URL. To match the URL paths by prefixes, make a regexp and add ``.*`` at the end.

Regular strings that start with a slash (``/``) are automatically recognized as paths by convention, and so are all regexps regardless of how they start:

.. code-block:: python

    import kmock

    async def test_http_paths(kmock: kmock.RawHandler) -> None:
        # Simple string starting with a slash are URL paths.
        kmock['/greetings'] << b'hello'

        # All regexps are paths regardless of what is in the pattern.
        kmock[re.compile('/greetings/.*')] << b'hello'
        kmock[kmock.path(re.compile('/greetings/.*'))] << b'hello'


Matching HTTP methods + paths
-----------------------------

To check against both the HTTP method and HTTP URL path, use a single space-separated string, with method going first (case-insensitive), and the path after that:

.. code-block:: python

    import kmock

    async def test_http_method_and_path(kmock: kmock.RawHandler) -> None:
        kmock['get /greetings'] << b'hello'
        kmock['post /greetings'] << b'hello'


Matching HTTP query params
--------------------------

A :class:`kmock.params` wrapper (a dict) is checked against URL query parameters. It accepts eiter a dict, or a string in the standartized query syntax. These parameters must be present and match. Other paramaters can exist and are ignored. Regular dicts without a wrapper are automatically recognized as query parameters:

.. code-block:: python

    import kmock

    async def test_http_query_params(kmock: kmock.RawHandler) -> None:
        # Explicit wrapping checks against params regardless of keys' names.
        kmock[kmock.params('name=john&mode=formal')] << b'Greetings, John!'

        # Dicts are checked against params only if they do NOT look like headers.
        kmock[{'name': 'john', 'mode': 'formal'}] << b'Greetings, John!'

The params' values can be either strings or pre-compiled regular patterns. The patterns must match fully, not by partial inclusion. Add ``.*`` at the edges to make it a partial pattern.


Matching HTTP request headers
-----------------------------

To check the request's headers (i.e. coming from client to server), wrap a dict into :class:`kmock.headers`, or filter by raw dict if it contains only the well-known headers and X-prefixed headers:

.. code-block:: python

    import kmock

    async def test_http_headers_as_dicts(kmock: kmock.RawHandler) -> None:
        # Explicit wrapping checks against headers regardless of key names.
        kmock[kmock.headers({'X-API-Token': '123'}] << b'hello'

        # Raw dicts are checked against header only if well-known or X-prefixed.
        kmock[{'X-API-Token': '123'] << b'hello'

Alternatively, headers can be filtered by the standartized string representation of headers in the HTTP  request without dicts — but in this case, the wrapper is mandatory to mark the headers instead of query params or request body:

.. code-block:: python

    import kmock

    async def test_http_headers_as_strings(kmock: kmock.RawHandler) -> None:
        kmock[kmock.headers('X-API-Token: 123')] << b'hello'

The headers' values can be either strings or pre-compiled regular patterns. The patterns must match fully, not by partial inclusion. Add ``.*`` at the edges to make it a partial pattern.


Matching HTTP request cookies
-----------------------------

To check the request's cookies (i.e. coming from client to server), use the :class:`kmock.cookies` wrapper. No string format is supported, and the wrapper is mandatory:

.. code-block:: python

    import kmock

    async def test_http_cookies(kmock: kmock.RawHandler) -> None:
        kmock[kmock.cookies({'session': '123'}] << b'hello'

The cookies' values can be either strings or pre-compiled regular patterns. The patterns must match fully, not by partial inclusion. Add ``.*`` at the edges to make it a partial pattern.


Matching HTTP request body
--------------------------

To check the request's body (also known as payload) in the raw unparsed format, use the :class:`kmock.body` wrapper. It checks the bytes-encoded binary payload. It must match fully. Bytes-typed regular patterns are supported:

.. code-block:: python

    import kmock

    async def test_http_body_bytes(kmock: kmock.RawHandler) -> None:
        kmock[kmock.body(b'input1=value1&input2=value2')] << b'hello'
        kmock[kmock.body(re.compile(b'input1=value1&.*'))] << b'hello'

To check against the request's body decoded as UTF-8 into a string, use the :class:`kmock.text` wrapper:

.. code-block:: python

    import kmock

    async def test_http_body_string(kmock: kmock.RawHandler) -> None:
        kmock[kmock.text('input1=value1&input2=value2')] << b'hello'
        kmock[kmock.text(re.compile('input1=value1&.*'))] << b'hello'


Matching HTTP request JSON
--------------------------

To check the request's JSON payload (parsed), use the :class:`kmock.data` wrapper:

.. code-block:: python

    import kmock

    async def test_http_json_data(kmock: kmock.RawHandler) -> None:
        kmock[kmock.data({'input1': 'value1', 'input2': 'value2'}] << b'hello'


Kubernetes criteria
===================

Kubernetes-like requests are additionally parsed & matched for Kubernetes-specific properties (falls back to ``None`` for all relevant fields if not a Kubernetes-like request).

Note that in all Kubernetes examples here, we use :class:`kmock.RawHandler` instead of :class:`kmock.KubernetesScaffold` or :class:`kmock.KubernetesEmulator` (even if they are activated by default). These Kubernetes criteria work at any level of the handler out of the box — even without Kubernetes-specific behaviour implemented or activated.


Matching Kubernetes resources
-----------------------------

To check requests by the resource type, as identified by the identifying fields taken from the URL (or, for creation, metadata), use the :class:`kmock.resource` wrapper. Only the group, group version, and the plural name are matched, as the only data available in the URLs.

Alternatively, some strings that look like complete resource specifiers, are automatially parsed as resources without wrappers. The following notations are supported:

- ``v1/pods`` (Core API)
- ``pods.v1`` (Core API)
- ``kopf.dev/v1/kopfexamples``
- ``kopfexamples.v1.kopf.dev``

For the so called "Core API" (the legacy of Kubernetes before the groups were introduced), the group name is an empty string (``""``), and the version is always ``"v1"`` — specifically this combination is recognized by the resource parser.

.. code-block:: python

    import kmock

    async def test_k8s_resource_specifiers(kmock: kmock.RawHandler) -> None:
        # All these filters are identical. Use the shortest one:
        kmock[kmock.resource(group='kopf.dev', version='v1', plural='kopfexamples')] << 200
        kmock[kmock.resource('kopf.dev', 'v1', 'kopfexamples')] << 200
        kmock[kmock.resource('kopf.dev/v1/kopfexamples')] << 200
        kmock[kmock.resource('kopfexamples.v1.kopf.dev')] << 200
        kmock['kopf.dev/v1/kopfexamples'] << 200
        kmock['kopfexamples.v1.kopf.dev'] << 200

        # Try listing all resources globally in the cluster.
        # There will be no response data, since we gave no useful payload above.
        # But the request will be counted.
        resp = await kmock.get('/apis/kopf.dev/v1/kopfexamples')
        assert resp.status == 200


Matching Kubernetes actions
---------------------------

To check for Kubernetes-specific actions, use the :class:`kmock.action` instance (a string enum;case-insensitive).

Strings ``"list"``, ``"watch"``, ``"fetch"``, ``"create"``, ``"update"``, (but not ``"delete"``) are automatically recognized as Kubernetes actions and require no wrappers. Note that ``"delete"``, when used as an unwrapped string, is recognized as the HTTP method, not the Kubernetes action — because of the unresolvable name conflict — always wrap this particular Kubernetes action.

.. code-block:: python

    import kmock

    async def test_kubernetes_actions(kmock: kmock.RawHandler) -> None:
        # All these filters are identical. Use the shortest one:
        kmock['list'] << 200
        kmock[kmock.action('list')] << 200

        # Try listing all resources globally in the cluster.
        # There will be no response data, since we gave no useful payload above.
        # But the request will be counted.
        resp = await kmock.get('/apis/kopf.dev/v1/kopfexamples')
        assert resp.status == 200

Kubernetes actions and HTTP methods are not directly equivalent. For example, HTTP "GET" method can lead to either listing, watching, or fetching Kubernetes actions, which are distinguished from each other by the URL structure (HTTP path & query params); HTTP "PUT" method has no relevant Kubernetes action at all.


Matching Kubernetes actions + resources
---------------------------------------

To check against both the Kubernetes action and resource, use a single space-separated string, with the action going first (case-insensitive), and the resource after that:

.. code-block:: python

    import kmock

    async def test_kubernetes_action_and_resource(kmock: kmock.RawHandler) -> None:
        kmock['list pods.v1'] << 200
        kmock['watch kopfexamples.v1.kopf.dev'] << 200

        resp = await kmock.get('/api/v1/pods')
        assert resp.status == 200

        resp = await kmock.get('/apis/kopf.dev/v1/kopfexamples?watch=true')
        assert resp.status == 200


Matching Kubernetes namespaces
------------------------------

To check for Kubernetes namespaces in the URLs (or in the metadata for the object creation), use the :func:`kmock.namespace` function as a criterion. Regexps are supported:

.. code-block:: python

    import kmock

    async def test_kubernetes_namespace_filtering(kmock: kmock.RawHandler) -> None:
        kmock[kmock.namespace('ns1')] << 200
        kmock[kmock.namespace(re.compile('ns.*'))] << 200

        resp = await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples')
        assert resp.status == 200

To check for the cluster-wide or namespaced request regardless of the specific namespace name, use the :func:`kmock.clusterwide` function. ``clusterwide(True)`` matches against cluster-wide requests only (no namespace), ``clusterwide(False)`` matches against namespaced requests only (regardless of the namespace name itself):

.. code-block:: python

    import kmock

    async def test_kubernetes_clusterwide_namespaced_filters(kmock: kmock.RawHandler) -> None:
        kmock[kmock.clusterwide()] << 200          # only clusterwide
        kmock[kmock.clusterwide(True)] << 200      # only clusterwide
        kmock[kmock.clusterwide(False)] << 200     # only namespaced

        # Make a cluster-wide request:
        resp = await kmock.get('/apis/kopf.dev/v1/kopfexamples')
        assert resp.status == 200

        # Make a namespaced request:
        resp = await kmock.get('/apis/kopf.dev/v1/namespaces/ns1/kopfexamples')
        assert resp.status == 200


Matching Kubernetes object names
--------------------------------

To check for individual names of Kubernetes resource objects being requested or processed (as inferred from the URL or, for creation, from the metadata), use the :func:`kmock.name` function. Regexps are supported:

.. code-block:: python

    import kmock

    async def test_kubernetes_object_name_filters(kmock: kmock.RawHandler) -> None:
        kmock[kmock.name('example1')] << 200
        kmock[kmock.name(re.compile('example.*'))] << 200

        resp = await kmock.delete('/apis/kopf.dev/v1/kopfexamples/example1')
        assert resp.status == 200


Matching Kubernetes sub-resources
---------------------------------

To check for the Kubernetes sub-resource name, use the :func:`kmock.subresource` function. Regexps are supported:

.. code-block:: python

    import kmock

    async def test_kubernetes_subresource_filters(kmock: kmock.RawHandler) -> None:
        kmock['v1/replicasets', kmock.subresource('scale')] << 200
        kmock['v1/replicasets', kmock.subresource(re.compile('scale.*'))] << 200

        resp = await kmock.get('/api/v1/replicasets/example1/scale')
        assert resp.status == 200


Matching priorities
===================

Prioritising the matcing rules
------------------------------

Rules can be prioritized relative to each other. The first matching rule with the highest (bigger, greater) priority is used.

To define different priorities, apply the power operator (``**``) to the filter before applying the response payloads. All subsequent filters from that priority will be automatically prioritised the same.

The default priority is zero. Priorities can be positive and negative numbers (integers or floating point).

.. code-block:: python

    import kmock

    async def test_priorities(kmock: kmock.RawHandler) -> None:
        # Two equivalent high-priority rules and responses.
        (kmock ** 100)['get /'] << b'hello'
        (kmock['get /'] ** 100) << b'world'

        # The default non-prioritised rule.
        kmock['get /'] << b'never served'

        resp = await kmock.get('/')
        text = await resp.read()
        assert text == b'hello'


Predefined priorities
---------------------

For user convenience and code readability, there are named properties ``.fallback`` and ``.override`` with priorities -INF and +INF respectively:

.. code-block:: python

    import kmock

    async def test_infinite_priorities(kmock: kmock.RawHandler) -> None:
        # Define the prioritised and non-priorities responses.
        kmock['/greetings'] << b'never served because there is an override below'
        kmock.fallback[re.compile(r'.*')] << 404
        kmock.override['/greetings'] << b'hello'

        # Try the catch-all rule for all URLs.
        resp = await kmock.get('/')
        assert resp.status == 404

        # Try the specifically defined overridden URL.
        resp = await kmock.get('/greetings')
        text = await resp.read()
        assert text == b'hello'


Combining priorities
--------------------

Priorities can be combined. If so, the rules are sorted as if the missing levels of priorities have priority zero. The same values of the 1st-level priority as then sorted by the 2nd-level priority, so on. As a side effect, there could be a fallback to a fallback or an override to an override if needed:

.. code-block:: python

    import kmock

    async def test_second_level_priorities(kmock: kmock.RawHandler) -> None:
        (kmock['get /'] ** 100) ** -1 << b'hello'
        kmock.override.override['/greetings'] << b'hello'
        kmock.fallback.fallback[re.compile('.*')] << 404

.. note::

    Runtime priorities are implemented as tuples of numbers consisting of all priorities that apply to the rule in their order of application — and compare as such. So a fallback to a fallback has the priority ``(-INF, -INF)``, which makes it lesser than e.g. regular 1st-level fallbacks ``(-INF, 0)`` or the default priority for non-prioritised rules ``(0, 0)`` — assuming that all priority tuples are padded to the length of two levels in this example.


Indexes & slices
================

All incoming requests are counted and indexed on arrival within each of the defined filters.

To filter by the sequential number (index) of the request within the scope of each filter separately, use numeric indexes or slices as if used with the lists:

.. code-block:: python

    import kmock

    async def test_sequential_indexes(kmock: kmock.RawHandler) -> None:
        # Only apply to the first three GETs of the root URL.
        kmock['get /'][:3] << b'hello'

        # Start applying only from the 10th GET request to the root URL.
        kmock['get /'][10:] << b'we are back'

        # Apply to the requests 4 to 9.
        kmock['get /'] << b'out of order'

        # Request the same URL 12 times.
        texts: list[bytes] = []
        for i in range(12):
            resp = await kmock.get('/')
            text = await resp.read()
            texts.append(text)

        assert texts == [
            b'hello', b'hello', b'hello',                       # 1st-3rd
            b'out of order', b'out of order', b'out of order',  # 4th-6th
            b'out of order', b'out of order', b'out of order',  # 7th-9th
            b'we are back', b'we are back', b'we are back',     # 10th-12th
        ]

Note that the sequence is scoped to the specific filter, not to the global request indexing, and as the requests arrive into that index — so two separate filters have their own indexes:

.. code-block:: python

    import kmock

    async def test_differently_scoped_slices(kmock: kmock.RawHandler) -> None:
        # First three GETs, all paths.
        kmock['get'][:3] << b'hello'

        # First three roots, all methods.
        kmock['/'][:3] << b'world'

        # And the rest.
        kmock << b'the rest'

        # Request the same URL 12 times.
        texts: list[bytes] = []
        for i in range(10):
            resp = await kmock.get('/')
            text = await resp.read()
            texts.append(text)

        assert texts == [
            # Initially, the requests 1-3 land into the first filter only.
            b'hello', b'hello', b'hello',

            # The global requests 4-6 are seen as the first 1-3 for the second filter.
            b'world', b'world', b'world',

            # The remaining requests 7-10 miss the first wo filters and go to the unlimited one.
            b'the rest', b'the rest', b'the rest', b'the rest',
        ]
