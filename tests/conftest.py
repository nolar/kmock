from collections.abc import Collection

import pytest

# import kmock.pytest
# from kmock import RawHandler

# def pytest_collection_modifyitems(config: pytest.Config, items: Collection[pytest.Item]) -> None:
#     # The simplest raw mock is enough for OUR tests, unless the tests specifically require more.
#     # (Unlike with the end users, to whom we offer the most enhanced functionality out of the box.)
#     mark = pytest.mark.kmock(cls=RawHandler)
#     for item in items:
#         item.add_marker(mark)


# def pytest_collection_finish(session: pytest.Session) -> None:
#     # The simplest raw mock is enough for OUR tests, unless the tests specifically require more.
#     # (Unlike with the end users, to whom we offer the most enhanced functionality out of the box.)
#     mark = pytest.mark.kmock(cls=RawHandler)
#     for item in session.items:
#         item.add_marker(mark, append=True)

# def pytest_sessionstart(session: pytest.Session) -> None:
#     # The simplest raw mock is enough for OUR tests, unless the tests specifically require more.
#     # (Unlike with the end users, to whom we offer the most enhanced functionality out of the box.)
#     kmock.pytest.DEFAULT_CLS = RawHandler

# TODO:
#   - k8s specifics:
#     - k8s resource discovery endpoints (ResourceMock)
#     - k8s resource manipulation endpoints (DummyObjectsMock)
#     - k8s resource tracking endpoints (TrackingKMock)
#   👉 in kopf: ensure that Resource/Selector are subclasses of ResourceProtocol/SelectorProtocol

# TODO: docs finally: proof-read in Grammarly, check the flow
