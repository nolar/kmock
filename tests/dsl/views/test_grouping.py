import pytest

from kmock import RawHandler, Server


@pytest.fixture
async def kmock1(kmock: RawHandler) -> None:
    yield kmock


@pytest.fixture
async def kmock2() -> None:
    async with RawHandler() as kmock, Server(kmock):
        yield kmock


@pytest.fixture
async def prepopulated2(kmock2: RawHandler) -> None:
    for method in ['get', 'post', 'patch']:
        for i in range(5):
            await kmock2.request(method, f'/?idx={i}')


@pytest.fixture
async def prepopulated(kmock: RawHandler) -> None:
    for method in ['get', 'post', 'patch']:
        for i in range(10):
            await kmock.request(method, f'/?idx={i}')


@pytest.mark.usefixtures('prepopulated')
async def test_common_prerequisites(kmock: RawHandler) -> None:
    assert len(kmock['/']) == 30
    assert len(kmock['get']) == 10
    assert len(kmock['post']) == 10
    assert len(kmock[{'idx': '5'}]) == 3


@pytest.mark.usefixtures('prepopulated')
async def test_union_via_operator(kmock: RawHandler) -> None:
    assert len(kmock['get'] | kmock['/']) == 30
    assert len(kmock['get'] | kmock['/path']) == 10
    assert len(kmock['get'] | kmock['post']) == 20


@pytest.mark.usefixtures('prepopulated')
async def test_union_via_sets(kmock: RawHandler) -> None:
    assert len(kmock[{'get', '/'}]) == 30
    assert len(kmock[{'get', '/path'}]) == 10
    assert len(kmock[{'get', 'post'}]) == 20


@pytest.mark.usefixtures('prepopulated')
async def test_intersection_via_operator(kmock: RawHandler) -> None:
    assert len(kmock['get'] & kmock['/']) == 10
    assert len(kmock['get'] & kmock['/path']) == 0
    assert len(kmock['get'] & kmock['post']) == 0


@pytest.mark.usefixtures('prepopulated')
async def test_intersection_via_comma(kmock: RawHandler) -> None:
    assert len(kmock['get', '/']) == 10
    assert len(kmock['get', '/path']) == 0
    # assert len(kmock['get', 'post']) == 0


@pytest.mark.usefixtures('prepopulated')
async def test_intersection_via_chaining(kmock: RawHandler) -> None:
    assert len(kmock['get']['/']) == 10
    assert len(kmock['get']['/path']) == 0
    # assert len(kmock['get']['post']) == 0


@pytest.mark.usefixtures('prepopulated')
async def test_exclusion_via_operator(kmock: RawHandler) -> None:
    assert len(kmock['get'] - kmock[{'idx': '5'}]) == 9
    assert len(kmock['get'] - kmock['/']) == 0
    assert len(kmock['get'] - kmock['post']) == 10
    assert len(kmock['get'] - kmock['post'] - kmock[{'idx': '5'}]) == 9


@pytest.mark.usefixtures('prepopulated')
async def test_inversion(kmock: RawHandler) -> None:
    assert len(~kmock[{'idx': '5'}]) == 27
    assert len(~kmock['/']) == 0
    assert len(~kmock['post']) == 20


@pytest.mark.usefixtures('prepopulated')
async def test_all_at_once(kmock: RawHandler) -> None:
    assert len(kmock[{'idx': '5'}]) == 3
    assert len(~kmock[{'idx': '5'}]) == 27
    assert len(kmock[{'get', 'post'}, {'/', '/path'}]) == 20
    assert len(~kmock[{'get', 'post'}, {'/', '/path'}]) == 10
    assert len(kmock[{'get', 'post'}, {'/', '/path'}] - kmock[{'idx': '5'}]) == 18
    assert len(kmock[{'get', 'post'}, {'/', '/path'}] - ~kmock[{'idx': '5'}]) == 2
    assert len(~kmock[{'get', 'post'}, {'/', '/path'}] - kmock[{'idx': '5'}]) == 9
    assert len(~kmock[{'get', 'post'}, {'/', '/path'}] - ~kmock[{'idx': '5'}]) == 1


@pytest.mark.usefixtures('prepopulated', 'prepopulated2')
async def test_multiple_roots_never_overlap(kmock1: RawHandler, kmock2: RawHandler) -> None:
    assert len(kmock1['get'] & kmock2['post']) == 0
    assert len(kmock1['get'] & kmock2['post'] & kmock2['patch']) == 0
    assert len((kmock1['get'] & kmock2['post']) & (kmock1['patch'] & kmock2['post'])) == 0


@pytest.mark.usefixtures('prepopulated', 'prepopulated2')
async def test_multiple_roots_unionised(kmock1: RawHandler, kmock2: RawHandler) -> None:
    assert len(kmock1['get'] | kmock2['post']) == 15
    assert len(kmock1['get'] | kmock2['post'] | kmock2['patch']) == 20
    assert len((kmock1['get'] | kmock2['post']) | (kmock1['patch'] | kmock2['post'])) == 25


@pytest.mark.usefixtures('prepopulated', 'prepopulated2')
async def test_multiple_roots_never_exclude_others(kmock1: RawHandler, kmock2: RawHandler) -> None:
    assert len(kmock1['get'] - kmock2['post']) == 10
    assert len(kmock2['get'] - kmock1['post']) == 5
    assert len(kmock1['/'] - kmock2['/']) == 30
    assert len(kmock2['/'] - kmock1['/']) == 15


# Mainly for the coverage of the fallback & catch-all branches.
async def test_unsupported_groups(kmock: RawHandler) -> None:
    with pytest.raises(TypeError):
        kmock['get'] - object()
    with pytest.raises(TypeError):
        kmock['get'] | object()
    with pytest.raises(TypeError):
        kmock['get'] & object()
    with pytest.raises(TypeError):
        object() | kmock['get']
    with pytest.raises(TypeError):
        object() & kmock['get']
    with pytest.raises(TypeError):
        (kmock['get'] - kmock['post']) - object()
    with pytest.raises(TypeError):
        (kmock['get'] & kmock['post']) & object()
    with pytest.raises(TypeError):
        (kmock['get'] & kmock['post']) | object()
    with pytest.raises(TypeError):
        (kmock['get'] | kmock['post']) | object()
    with pytest.raises(TypeError):
        (kmock['get'] | kmock['post']) & object()
