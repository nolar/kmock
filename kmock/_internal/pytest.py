from typing import Any, AsyncIterator

import attrs
import pytest
import pytest_asyncio

from kmock._internal import apps, k8s

# By default, use the most feature-full class, both mock- & tcp/http-wise.
DEFAULT_CLS: type[apps.RawHandler] = k8s.KubernetesEmulator


@pytest.fixture()
def _kmock_aresponses(request: pytest.FixtureRequest) -> None:
    # This fixture is separated from `kmock` because it is sync — to retrieve another async fixture.
    # Initialize `aresponses` strictly before `kmock` if it is used in the test at all.
    # If not used, assume that it is not retrieved at runtime later.
    if 'aresponses' in request.fixturenames:
        request.getfixturevalue('aresponses')  # or fail trying


def pytest_configure(config: Any) -> None:
    config.addinivalue_line('markers', "kmock: configure the Kubernetes/API Mock Server.")


def pytest_addoption(parser: pytest.Parser) -> None:
    default_cls_name = f'{DEFAULT_CLS.__module__}.{DEFAULT_CLS.__name__}'
    parser.addini('kmock_cls', "A class to use for kmock.", default=default_cls_name)
    parser.addini('kmock_limit', "How many requests a single server can serve at most.")
    parser.addini('kmock_strict', "Fail the test on teardown if there were errors?", type='bool', default=False)


@pytest.fixture()
def kmock_options(request: pytest.FixtureRequest) -> dict[str, Any]:
    """
    The keyword arguments passed to the mock server.

    By default, all kwargs from the ``kmark`` markers are assembled.
    This allows overriding the KMock behaviour on a per-parameter,
    per-function, per-module, per-package level, or on the session level.

    The special kwarg ``cls`` can be used to override the class of the server.
    By default, it is the most feature-full class from the library.
    """
    default_cls_name = f'{DEFAULT_CLS.__module__}.{DEFAULT_CLS.__name__}'
    clsname: str = request.config.getini('kmock_cls') or default_cls_name
    limit: str = request.config.getini('kmock_limit')
    strict: bool = request.config.getini('kmock_strict')

    if not clsname or '.' not in clsname:
        raise pytest.UsageError("kmock_cls must look like 'package.class'.")

    try:
        mod = __import__(clsname.rsplit('.', 1)[0])
        cls = getattr(mod, clsname.rsplit('.', 1)[-1])
    except AttributeError:
        raise pytest.UsageError(f"kmock_cls refers to non-existent class {clsname!r}")

    options: dict[str, Any] = {
        key: val for key, val in {
            'cls': cls,
            'limit': int(limit) if limit else None,
            'strict': strict,
        }.items() if val is not None
    }

    for marker in reversed(list(request.node.iter_markers('kmock'))):  # farthest to closest
        options.update(marker.kwargs)
    return options


# NB: PyCharm detects the fixture types by their return annotations,
# though the proper annotation would be AsyncIterator[RawHandler], not RawHandler itself.
@pytest_asyncio.fixture()
async def kmock(kmock_options: dict[str, Any], _kmock_aresponses: None) -> AsyncIterator[apps.RawHandler]:
    """
    KMock with a bundled server & associated client ready to use out-of-the-box.
    """
    cls: type[apps.RawHandler] = kmock_options.pop('cls', DEFAULT_CLS)
    server_fields = {field.name for field in attrs.fields(apps.Server)}
    server_fields = {name.strip('_') for name in server_fields}
    server_kwargs = {key: val for key, val in kmock_options.items() if key in server_fields}
    handler_kwargs = {key: val for key, val in kmock_options.items() if key not in server_kwargs}
    async with cls(**handler_kwargs) as kmock, apps.Server(kmock, **server_kwargs):
        yield kmock
