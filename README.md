# Kubernetes Mock Server in Python

— Kmock-kmock…

— Who's there?

— It's me, a long awaited Kubernetes API mock server!

The rationale behind the library itself is simple: monkey-patching is bad. It makes you test the specific implementation of your HTTP/API client, not the overall communication contract. Realistic servers are an acceptable compromise. The trade-off is only the overhead for the localhost network traffic & HTTP/JSON protocol rendering & parsing. The obvious flaw: you can make mistakes in assumptions what is the supposed response of the remote system.

The rationale behind the library's DSL is simple too: tests must be brief. Brief tests require brief setup & brief assertions. Extensive logic, such as for-cycles, if-conditions, temporary variables, talking with external classes, so on — all this verbosity distracts from the test purpose, leading to fewer tests being written in total.


## All the worst practices at your service

* BECAUSE-I-CAN-driven development — nobody needs it, nobody asked for it.
* Not invented here — there are other alike tools, but I did not like them.
* A 3-week side project 3 years in the making, 90% ready since week four.
* Overengineered from day one.
* Python-based DSL with exsessively overloaded syntax tricks.
* Side effects in supposedly computational operators (`<<`, `>>`).
* Kubernetes in Python. (Who on Earth does that?!)
* Lower-cased naming as in Python builtins rather than CamelCase conventions.
* Around 200%, if not 300% test coverage (some aspects tested twice or more).
* Packaged with setuptools — old but gold.
* Mostly hand-made by organic humans: no code formatters, not much AI.
* Thoughtless AI code & tests for some auxiliary low-level algorithms.
* Contributions are not welcome (but you can try).
