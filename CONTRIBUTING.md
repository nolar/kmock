# Contributing

Code style guidelines:

* **120 chars** per line of code max. Prefer 100 when possible. Perfer 80 chars per line in docstrings.
* **No code formatters.** Use the common sense and blend into the existing code style.
* **Make all classes slotted.** Prefer ``@attrs.define``, avoid ``dataclasses``.
* **Prefer keyword arguments** (``@attrs.define(kw_only=True)`` for classes), unless the interface is intentionally positional and has no more than 2-3 arguments and there can be no more in the future.
* **Keep names brief:** only one verb for methods; only one noun for properties; no public names with 2+ words. Use thesaurus to find shorter synonyms or alternative names.
* **Keep APIs brief:** add syntax tricks to express the intentions the same as you would speak them out loud.
* **Annotate types** fully and strictly. Use precise generics like ``Sequence``, ``Collection``, ``Iterable``, ``Iterator``.
* **Avoid ``Any``** — it is a code smell — unless it is a value for passing through and the code does not use it.
* **Hide ``aiohttp``** — as an implementation detail. The low-level implementation can change,t he API should not. Keep the methods/properties referring to ``aiohttp`` protected (starting with an underscore).
* **Explain the problem** in the PRs. Provide syntax examples.

Class naming:

[PEP-8](https://peps.python.org/pep-0008/#class-names) says:

> Class names should normally use the CapWords convention.
> The naming convention for functions may be used instead in cases
> where the interface is documented and used primarily as a callable.

* For internal classes, use **CamelCase** as usually.
* For DSL shortcuts (boxes/enums, such as `method()`, `action()`, `headers()`, `data()`, `body()`, etc.), use **single-word lower-cased** names: they must behave as callables that accept well-documented arguments and return some "black box" with undefined signature (no methods, no fields, no properties), which should only be passed back to the library, which unwraps them into the real data.
* Where applicable, utilise Python's builtins, such as `range()`, `slice()`, etc.
