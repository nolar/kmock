=============
Ideas & TODOs
=============

Undecided ideas
===============

How to interpret ``set`` & ``frozenset``? They can mean "pick a random response of a few possibilities" or as "stream these items in random order" (beause it is an iterable). Note that ``frozenset`` does not have Python syntax sugar, so it is not very convenient to use, unlike set's ``{…}`` syntax. Also, not all content types can be added to sets because they are not hashable (though ``lambda: object()`` can be added instead). Sets currently raise an explicit exception when used, reserved for future interpretation changes.

Is HTTPS support with the self-signed certificates really needed — so that ``https://`` URLs could be intercepted & served too. This adds complexity and a few rather heavy dependencies for a relatively rare situation when the explicitly provided URL (``http://``) cannot be used. Intercepting the external APIs in third-party SDKs will not work anyway without the DNS interception, but the DNS interception only works with ``aiohttp`` clients, despite SDKs often use ``requests`` or other sync libraries.


Rejected ideas
==============
