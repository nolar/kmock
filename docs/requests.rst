================
Request matching
================

.. highlight:: python

All criteria for a request to match the rule come in the square brackets on a handler or chained to other rules. Alternatively, the criteria can be listed within the single pair of square brackets. Some kinds of criteria can be combined into one — for example, HTTP methods and URLs, Kubernetes actions and resources. These lines are equivalent::

    kmock['get']['/'] << b'hello'
    kmock['get', '/'] << b'hello'
    kmock['get /'] << b'hello'

By default, when there is no criterion at all, all requests match.


HTTP criteria
=============

HTTP routing criteria
---------------------

A :class:`kmock.method` instance (a string enum) is matched strictly against HTTP verbs of the request (case-insensitive). Strings ``"get"``, ``"post"``, ``"patch"``, ``"put"``, ``"delete"``, ``"options"``, ``"head"`` are automatically recognized as HTTP verbs and require no wrappers. Pre-compiled regular expressions can be used too::

    kmock['get'] << b'hello'                    # standard verb
    kmock[kmock.method('store')] << b'hello'          # non-standard verb
    kmock[re.compile('get|post')] << b'hello'   # a pair of verbs at once

A :class:`kmock.path` wrapper for stings and regexps is used strictly against request paths. Both the string and the pattern must match fully, not just prefixed by this URL. To convert it into a prefix, make a regexp and add ``.*`` at the end. Regular strings that start with ``/`` are automatically recognized as paths by convention, so are all regexps::

    kmock['/greetings'] << b'hello'
    kmock[re.compile('/greetings/.*')] << b'hello'
    kmock[kmock.path(re.compile('/greetings/.*'))] << b'hello'

Regular strings are also treated as possible combinations of the method and the path (in that order), but only for known verbs (case-insensitive)::

    kmock['get /greetings'] << b'hello'
    kmock['post /greetings'] << b'hello'


HTTP metadata criteria
----------------------

A :class:`kmock.params` wrapper (a dict) is checked against URL query parameters. It accepts eiter a dict, or a string in the standartized query syntax. These parameters must be present and match. Other paramaters can exist and are ignored. Regular dicts without a wrapper are automatically recognized as query parameters::

    kmock[kmock.params('name=john&mode=formal')] << b'Greetings, John!'
    kmock[{'name': 'john', 'mode': 'formal'}] << b'Greetings, John!'

A :class:`kmock.headers` wrapper matches against the request headers (client to server). A standartized string representation is possible, but the wrapper is mandatory to mark the headers instead of implicit params::

    kmock[kmock.headers('X-API-Token: 123'}] << b'hello'
    kmock[kmock.headers({'X-API-Token': '123'}] << b'hello'

A :class:`kmock.cookies` wrapper matches against the incoming cookies (client to server). No string format is supported, and the wrapper is mandatory::

    kmock[kmock.cookies({'session': '123'}] << b'hello'

In all three cases of dicts —params, headers, cookies— the values can be either strings or pre-compiled regular patterns. The patterns must match fully, not by partial inclusion. Add ``.*`` at the edges to make it a partial pattern.


HTTP payload criteria
---------------------

A :class:`kmock.body` wrapper checks against the bytes-encoded payload of a request's body. It must match fully. Bytes-typed regular patterns are supported::

    kmock[kmock.body(b'input1=value1&input2=value2')] << b'hello'
    kmock[kmock.body(re.compile(b'input1=value1&.*'))] << b'hello'

A :class:`kmock.text` wrapper is the same, but for the bytes decoded as a UTF-8 text payload of a request's body::

    kmock[kmock.text('input1=value1&input2=value2')] << b'hello'
    kmock[kmock.text(re.compile('input1=value1&.*'))] << b'hello'

A :class:`kmock.data` wrapper checks against the JSON payload of a request's body specifically.

    kmock[kmock.data({'input1': 'value1', 'input2': 'value2'}] << b'hello'


Kubernetes criteria
===================

Kubernetes-like requests are additionally parsed & matched for Kubernetes-specific properties (falls back to ``None`` for all relevant fields if not a Kubernetes-like request).

Kubernetes basic criteria
-------------------------

The :class:`kmock.resource` wrapper matches against a recognized resource, where the resource identity is guessed from the URL. Only the group, group version, and the plural name are matched, as the only data available in the URLs::

    kmock[kmock.resource('kopf.dev', 'v1', 'kopfexamples')] << None

Alternatively, some strings that look like complete resource specifiers, are automatially parsed as resource definitions without wrappers. The following notations are supported::

    kmock['kopf.dev/v1/kopfexamples'] << None
    kmock['kopfexamples.v1.kopf.dev'] << None
    kmock['v1/pods'] << None
    kmock['pods.v1'] << None

The :class:`kmock.action` instance (a string enum) is matched strictly against Kubernees actions(case-insensitive). Strings ``"list"``, ``"watch"``, ``"fetch"``, ``"create"``, ``"update"``, (but not ``"delete"``) are automatically recognized as Kubernetes actions and require no wrappers. Pre-compiled regular expressions can be used too::

    kmock['list'] << None
    kmock[kmock.action('list')] << None
    kmock[kmock.action(re.compile('list|watch'))] << None

Note that ``"delete"``, when used as an unwrapped string, is recognized as an HTTP verb, not a Kubernetes action — because of the unresolvable name conflict. Always wrap this Kubernetes action.

Regular strings are also treated as possible combinations of the action and the resource definition(in that order), but only for known actions (case-insensitive)::

    kmock['list pods.v1'] << None
    kmock['watch kopfexamples.v1.kopf.dev'] << None


Kubernetes naming criteria
--------------------------

The :class:`kmock.clusterwide` function builds a criterion to match against cluster-wide requests only, or to distinguish cluster-wide from non-cluster-wide (means: namespaced regardless of the namespace) requests::

    kmock[kmock.clusterwide()] << None          # only clusterwide
    kmock[kmock.clusterwide(True)] << None      # only clusterwide
    kmock[kmock.clusterwide(False)] << None     # only namespaced

The :class:`kmock.namespace` function builds a criterion to match against Kubernetes namespaces. Regexps are supported::

    kmock[kmock.namespace('ns1')] << None
    kmock[kmock.namespace(re.compile('ns.*'))] << None

The :class:`kmock.name` function builds a criterion to match against the specific name of the resource object. Regexps are supported::

    kmock[kmock.namespace('example1')] << None
    kmock[kmock.namespace(re.compile('example.*'))] << None

The :class:`kmock.subresource` function builds a criterion to match against the specific subresource of the resource object. Regexps are supported::

    kmock[kmock.subresource('scale')] << None
    kmock[kmock.subresource(re.compile('scale.*'))] << None




Priorities
==========

Groups of rules can be priorities relative to each other. The first matching rule with a higher (bigger, greater) priority is used::

    (kmock ** 100)['get /'] << b'hello'
    (kmock['get /'] ** 100) << b'hello'

For convenience and readability, there are named properties ``.fallback`` and ``.override`` with priorities -INF and +INF respectively::

    kmock.fallback['/'] << 404
    kmock.override['/greetings'] << b'hello'

And yes, as a side effect, there could be a fallback to a fallback or an override to an override if needed

    kmock.fallback.fallback['/'] << 404
    kmock.override.override['/greetings'] << b'hello'

The default prirority of everything is zero.

.. note::

    Runtime priorities are implemented as tuples of numbers consisting of all priorities that apply to the rule in their order — and compare as such. So a fallback to a fallback has the priority ``(-INF, -INF, 0)``, which makes it lesser than e.g. regular fallbacks ``(-INF, 0)`` or the default priority ``(0,)``.


Indexes & slices
================

All requests are counted and indexed on arrival within each of the defined filters. This allows filtering the requests by their indexes or slices of indexes::

    kmock['get /'][:3] << b'hello'      # only the first three GETs are served
    kmock['get /'][10:] << b'we are back'   # fix/recover on the 10th request
    kmock['get /'] << b'out of order'   # requests 4-9 go here

Note that the sequence is scoped to the specific filter, so two separate filters have their own indexes::

    kmock['get'][:3] << b'first three gets, all paths'
    kmock['/'][:3] << b'first three roots, all methods'
    kmock << b'the rest'
