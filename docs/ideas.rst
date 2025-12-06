=============
Ideas & TODOs
=============

Undecided ideas
===============

Unordered sets
--------------

How to interpret ``set`` & ``frozenset``? They can mean "pick a random response of a few possibilities" or as "stream these items in random order" (beause it is an iterable). Note that ``frozenset`` does not have Python syntax sugar, so it is not very convenient to use, unlike set's ``{…}`` syntax. Also, not all content types can be added to sets because they are not hashable (though ``lambda: object()`` can be added instead). Sets currently raise an explicit exception when used, reserved for future interpretation changes.


HTTPS support
-------------

Is HTTPS support with the self-signed certificates really needed — so that ``https://`` URLs could be intercepted & served too. This adds complexity and a few rather heavy dependencies for a relatively rare situation when the explicitly provided URL (``http://``) cannot be used. Intercepting the external APIs in third-party SDKs will not work anyway without the DNS interception, but the DNS interception only works with ``aiohttp`` clients, despite SDKs often use ``requests`` or other sync libraries.


Resource janitor
----------------

Some sample tests are conveniently spawn a task and nobody cleans this this task after the test, which leads to ``ResourceWarning`` (or errors, if the tests run in strict mode: treat all warnings as error). These resources stay unawaited if the test fails, too. Not good.

Originally, there was an idea to implement a separate library which provides a pytets fixture ``janitor`` or ``bin``, to which you can pass all the resources to be "properly handled" in the test's teardown. This might take some time to implement and publish this library properly. Meanwhile, the sample/demo tests just allow the resource leakage — for the sake of brevity.

Once implemented, adjust all sample/demo tests to inject the spawned tasks into such a "bin" instead of verbosely cancelling them in the happy path only.


Requests accessing
------------------

Currently, the incoming requests are accessible on the root handler or the individual filters directly as a number-indexed sequences: ``kmock[0]``, etc — as it was originally implemented in a proof-of-concept.

This slightly contradicts the similar assertions practices of the Kubernetes classes with their ``.objects`` and ``.resources`` properties for readability.

Consider if it is more viable to expose the requests as ``kmock.requests``, ``kmock['get /'].requests``, etc — for code readability. Also, this will separate the already overloaded DSL signatures of ``View`` and descendants from the very narrow extra use-case.

This will break the library's API/DSL, but it is okay for the early versions. Some backward compatibility can be maintained anyway.


Rejected ideas
==============
