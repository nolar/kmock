import pytest

from kmock import Criteria, HTTPCriteria, RawHandler, Request


@pytest.fixture
async def prepopulated(kmock: RawHandler) -> None:
    for i in range(10):
        await kmock.get(f'/?idx={i}')


@pytest.mark.usefixtures('prepopulated')
async def test_individual_requests_by_numeric_index(kmock: RawHandler) -> None:
    view = kmock[HTTPCriteria(method='get')]
    request = view[0]
    assert isinstance(request, Request)
    assert request.params['idx'] == '0'
    request = view[-1]
    assert isinstance(request, Request)
    assert request.params['idx'] == '9'


@pytest.mark.usefixtures('prepopulated')
async def test_limiting_from_below(kmock: RawHandler) -> None:
    view = kmock[5:]
    idxs = [req.params['idx'] for req in view]
    assert idxs == ['5', '6', '7', '8', '9']


@pytest.mark.usefixtures('prepopulated')
async def test_limiting_from_above(kmock: RawHandler) -> None:
    view = kmock[:5]
    idxs = [req.params['idx'] for req in view]
    assert idxs == ['0', '1', '2', '3', '4']


@pytest.mark.usefixtures('prepopulated')
async def test_limiting_on_both_sides(kmock: RawHandler) -> None:
    view = kmock[3:7]
    idxs = [req.params['idx'] for req in view]
    assert idxs == ['3', '4', '5', '6']


@pytest.mark.usefixtures('prepopulated')
async def test_stepping_by_1(kmock: RawHandler) -> None:
    view = kmock[::1]
    idxs = [req.params['idx'] for req in view]
    assert idxs == ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']


@pytest.mark.usefixtures('prepopulated')
async def test_stepping_by_2(kmock: RawHandler) -> None:
    view = kmock[::2]
    idxs = [req.params['idx'] for req in view]
    assert len(view) == 5
    assert idxs == ['0', '2', '4', '6', '8']


@pytest.mark.usefixtures('prepopulated')
async def test_stepping_by_3(kmock: RawHandler) -> None:
    view = kmock[::3]
    idxs = [req.params['idx'] for req in view]
    assert idxs == ['0', '3', '6', '9']


@pytest.mark.usefixtures('prepopulated')
async def test_borders_with_steps(kmock: RawHandler) -> None:
    view = kmock[3:8:2]
    idxs = [req.params['idx'] for req in view]
    assert idxs == ['3', '5', '7']


@pytest.mark.usefixtures('prepopulated')
async def test_nested_slicing_successful(kmock: RawHandler) -> None:
    view = kmock['get'][3:8:2]
    idxs = [req.params['idx'] for req in view]
    assert idxs == ['3', '5', '7']


@pytest.mark.usefixtures('prepopulated')
async def test_nested_slicing_empty(kmock: RawHandler) -> None:
    view = kmock['post'][3:8:2]
    assert len(view) == 0


@pytest.mark.usefixtures('prepopulated')
async def test_chained_slicing_1(kmock: RawHandler) -> None:
    view = kmock[::2][::2]  # "every 4th", the same as [::4]
    idxs = [req.params['idx'] for req in view]
    assert idxs == ['0', '4', '8']


@pytest.mark.usefixtures('prepopulated')
async def test_chained_slicing_2(kmock: RawHandler) -> None:
    view = kmock[3:8][1:][:2]  # [0-9]->[3-7]->[4-7]->[4-5]
    idxs = [req.params['idx'] for req in view]
    assert idxs == ['4', '5']


@pytest.mark.usefixtures('prepopulated')
async def test_post_filered_successful(kmock: RawHandler) -> None:
    view = kmock['get'][3:8:2]
    idxs = [req.params['idx'] for req in view]
    assert idxs == ['3', '5', '7']


@pytest.mark.usefixtures('prepopulated')
async def test_post_filered_empty(kmock: RawHandler) -> None:
    view = kmock[3:8:2]['post']
    assert len(view) == 0


async def test_response_slicing(kmock: RawHandler) -> None:
    # No gaps! Gaps raise the "undefined behaviour" — this is a different story.
    kmock['/'][:1] << b'hello'
    kmock['/'][:3] << b'world'
    kmock['/'][5:9] << b'5to9'
    kmock['/'][::2] << b'evens'
    kmock['/'][1::2] << b'odds'
    texts = [await (await kmock.get('/')).read() for _ in range(13)]
    assert texts == [
        b'hello', b'world', b'world', b'odds', b'evens',  # idx=0-4
        b'5to9', b'5to9', b'5to9', b'5to9',  # idx=5-8
        b'odds', b'evens', b'odds', b'evens',  # idx=9-12
    ]
