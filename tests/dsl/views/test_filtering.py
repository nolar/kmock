import functools
from typing import Any

import pytest

from kmock import HTTPCriteria, RawHandler, Request


@pytest.fixture
async def prepopulated(kmock: RawHandler) -> None:
    for method in ['get', 'post', 'patch']:
        for i in range(10):
            await kmock.request(method, f'/?idx={i}')


def true_no_args() -> bool:
    return True


def false_no_args() -> bool:
    return False


def idx5_one_arg(request: Request) -> bool:
    return request.params.get('idx') == '5'


# NB: Criteria guessing & creation are tested elsewhere with more details.
# We only need to test that the […] syntax maps to those criteria properly.
@pytest.mark.usefixtures('prepopulated')
async def test_guessed_criteria(kmock: RawHandler) -> None:
    view1 = kmock['get']
    view2 = kmock[{'idx': '5'}]
    view3 = kmock['get', {'idx': '5'}]
    assert len(view1) == 10
    assert len(view2) == 3
    assert len(view3) == 1


@pytest.mark.usefixtures('prepopulated')
async def test_direct_criteria(kmock: RawHandler) -> None:
    view1 = kmock[HTTPCriteria(method='get')]
    view2 = kmock[HTTPCriteria(params={'idx': '5'})]
    view3 = kmock[HTTPCriteria(method='get', params={'idx': '5'})]
    assert len(view1) == 10
    assert len(view2) == 3
    assert len(view3) == 1


@pytest.mark.usefixtures('prepopulated')
@pytest.mark.parametrize('expected, fn', [
    # Simple functions.
    pytest.param(30, true_no_args, id='fn-true-no-args'),
    pytest.param(0, false_no_args, id='fn-false-no-args'),
    pytest.param(3, idx5_one_arg, id='fn-idx5-one-arg'),

    # Partials.
    pytest.param(30, functools.partial(true_no_args), id='partial-true-no-args'),
    pytest.param(0, functools.partial(false_no_args), id='partial-false-no-args'),
    pytest.param(3, functools.partial(idx5_one_arg), id='partial-idx5-one-arg'),

    # Lambdas.
    pytest.param(0, lambda: False, id='lambda-no-args-false'),
    pytest.param(30, lambda: True, id='lambda-no-args-true'),
    pytest.param(27, lambda req: req.params.get('idx') != '5', id='lambda-one-arg-not5'),
    pytest.param(3, lambda req: req.params.get('idx') == '5', id='lambda-one-arg-idx5'),
])
async def test_callbacks(kmock: RawHandler, expected: int, fn: Any) -> None:
    view = kmock[fn]
    assert len(view) == expected


async def test_no_op_filtering(kmock: RawHandler) -> None:
    assert kmock[None] is kmock
    assert kmock[None][None] is kmock
    assert kmock[None, None] is kmock
    assert kmock[(None, None)] is kmock
    assert kmock[[None, None]] is kmock
    assert kmock[{None}] is kmock
    assert kmock[{None}, (None, None)] is kmock
    assert kmock[{None}, [None, None]] is kmock
    assert kmock[set()] is kmock
    assert kmock[frozenset()] is kmock


async def test_optimization_of_criteria(kmock: RawHandler) -> None:
    filter1 = kmock['get']
    filter2 = filter1['/']
    assert filter2._source is kmock  # two same-typed filters squashed
    assert isinstance(filter2.criteria, HTTPCriteria)


async def test_nonoptimization_of_criteria_1(kmock: RawHandler) -> None:
    filter1 = kmock[true_no_args]  # not even an OptiCriteria
    filter2 = filter1['/']
    assert filter2._source is filter1
    assert isinstance(filter2.criteria, HTTPCriteria)


async def test_nonoptimization_of_criteria_2(kmock: RawHandler) -> None:
    filter1 = kmock['get']  # an OptiCriteria/HTTPCriteria
    filter2 = filter1['list v1/pods']  # an OptiCriteria, but not the same type
    assert filter2._source is filter1
    assert not isinstance(filter2.criteria, HTTPCriteria)


async def test_unsupported_filters(kmock: RawHandler) -> None:
    with pytest.raises(NotImplementedError, match=r"Unsupported filtering criteria"):
        kmock[object()]
    with pytest.raises(NotImplementedError, match=r"Unsupported filtering criteria"):
        kmock['']
