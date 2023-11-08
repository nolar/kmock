import math

import pytest

from kmock import RawHandler, View


@pytest.fixture(params=['root', 'slicer', 'filter', 'or', 'and', 'exclusion'])
def view(request: pytest.FixtureRequest, kmock: RawHandler) -> View:
    if request.param == 'root':
        return kmock
    elif request.param == 'slicer':
        return kmock[1:100:2]
    elif request.param == 'filter':
        return kmock['get']
    elif request.param == 'or':
        return kmock['get'] | kmock['delete']
    elif request.param == 'and':
        return kmock['get'] & kmock['/']
    elif request.param == 'exclusion':
        return kmock['get'] - kmock['delete']
    else:
        raise Exception(f"Unsupported fixture param {request.param!r}")


@pytest.mark.parametrize('priority', [-math.inf, -10, 10, math.inf])
def test_priorities(view: View, priority: float) -> None:
    assert (view << b'').priorities == ()
    assert ((view ** priority) << b'').priorities == (priority,)
    assert ((view ** priority)['get'] << b'').priorities == (priority,)
    assert ((view ** priority)[1:9:2] << b'').priorities == (priority,)
    assert ((view ** priority) ** -priority << b'').priorities == (priority, -priority)
    assert ((view ** -priority) ** priority << b'').priorities == (-priority, priority)


def test_infinities(view: View) -> None:
    assert (view.fallback << b'').priorities == (-math.inf,)
    assert (view.override << b'').priorities == (math.inf,)
    assert (view.fallback['get'] << b'').priorities == (-math.inf,)
    assert (view.override['get'] << b'').priorities == (math.inf,)
    assert (view.fallback[1:9:2] << b'').priorities == (-math.inf,)
    assert (view.override[1:9:2] << b'').priorities == (math.inf,)
