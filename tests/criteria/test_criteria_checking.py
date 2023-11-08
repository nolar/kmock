import enum
import re
from typing import Any

import pytest

from kmock import Criteria, Request, action, method, resource


class ObjectEnum(enum.Enum):
    A = object()
    B = object()


class StringEnum(enum.Enum):
    A = 'A-Value'
    B = 'B-Value'


class BytesEnum(enum.Enum):
    A = b'A-Value'
    B = b'B-Value'


class NumericEnum(enum.Enum):
    N = 123


class SampleCriteria(Criteria):
    def __call__(self, request: Request) -> bool:
        raise NotImplementedError  # not used; just to override the abstract method


@pytest.mark.parametrize('pat, val', [
    # All scalars are interchangeable, we tolerate auto-conversions normally (without strict()).
    pytest.param(123, 123, id='int-vs-int'),
    pytest.param(123, '123', id='int-vs-str'),
    pytest.param(123, b'123', id='int-vs-bytes'),
    pytest.param('123', 123, id='str-vs-int'),
    pytest.param('123', '123', id='str-vs-str'),
    pytest.param('123', b'123', id='str-vs-bytes'),
    pytest.param(b'123', 123, id='bytes-vs-int'),
    pytest.param(b'123', '123', id='bytes-vs-str'),
    pytest.param(b'123', b'123', id='bytes-vs-bytes'),

    # Regexps are interchangeable with scalars too.
    pytest.param(re.compile(r'\d+'), 123, id='sregexp-vs-int'),
    pytest.param(re.compile(r'\d+'), '123', id='sregexp-vs-str'),
    pytest.param(re.compile(r'\d+'), b'123', id='sregexp-vs-bytes'),
    pytest.param(re.compile(br'\d+'), 123, id='bregexp-vs-int'),
    pytest.param(re.compile(br'\d+'), '123', id='bregexp-vs-str'),
    pytest.param(re.compile(br'\d+'), b'123', id='bregexp-vs-bytes'),

    # Enums from either side match their raw names & values case-insensitively.
    pytest.param(ObjectEnum.A, ObjectEnum.A, id='objectenum-vs-objectenum'),
    pytest.param(StringEnum.A, StringEnum.A, id='stringenum-vs-stringenum'),
    pytest.param(StringEnum.A, StringEnum.A.name.lower(), id='stringenum-vs-name'),
    pytest.param(StringEnum.A.name.lower(), StringEnum.A, id='name-vs-stringenum'),
    pytest.param(StringEnum.A, StringEnum.A.value.lower(), id='stringenum-vs-value'),
    pytest.param(StringEnum.A.value.lower(), StringEnum.A, id='value-vs-stringenum'),
    pytest.param(BytesEnum.A, BytesEnum.A, id='bytesenum-vs-bytesenum'),
    pytest.param(BytesEnum.A, BytesEnum.A.name.lower(), id='bytesenum-vs-name'),
    pytest.param(BytesEnum.A.name.lower(), BytesEnum.A, id='name-vs-bytesenum'),
    pytest.param(BytesEnum.A, BytesEnum.A.value.lower(), id='bytesenum-vs-value'),
    pytest.param(BytesEnum.A.value.lower(), BytesEnum.A, id='value-vs-bytesenum'),
    pytest.param(NumericEnum.N, 123, id='numenum-vs-int'),
    pytest.param(NumericEnum.N, '123', id='numenum-vs-str'),
    pytest.param(NumericEnum.N, b'123', id='numenum-vs-bytes'),
    pytest.param(123, NumericEnum.N, id='int-vs-numenum'),
    pytest.param('123', NumericEnum.N, id='str-vs-numenum'),
    pytest.param(b'123', NumericEnum.N, id='bytes-vs-numenum'),
    pytest.param('N', NumericEnum.N, id='strname-vs-numenum'),
    pytest.param(b'N', NumericEnum.N, id='bytesname-vs-numenum'),
    pytest.param(re.compile(r'\w+'), NumericEnum.N, id='regexpname-vs-numenum'),
    pytest.param(re.compile(r'\d+'), NumericEnum.N, id='regexpvalue-vs-numenum'),

    # Some well-known enums, just to be sure (they are covered by generic case anyway).
    pytest.param(method.GET, 'get', id='method-vs-str'),
    pytest.param(action.LIST, 'list', id='action-vs-str'),
    pytest.param('get', method.GET, id='str-vs-method'),
    pytest.param('list', action.LIST, id='str-vs-action'),

    # Dicts are partially matched, but items are recursively checked.
    pytest.param({'idx': 5}, {'idx': '5'}, id='intdict-vs-strdict'),
    pytest.param({'q': 'query'}, {'q': 'query', 'another': 'anything'}, id='dict-hit'),
    pytest.param({'q': re.compile(r'query.*', re.I)}, {'q': 'QuERy insensitive'}, id='dict-regexp'),

    # Unordered collections declare "any" value.
    pytest.param(range(100, 200), 123, id='range-vs-int'),
    pytest.param(range(100, 200), '123', id='range-vs-str'),
    pytest.param(range(100, 200), b'123', id='range-vs-bytes'),
    pytest.param({123, 456}, 123, id='intset-vs-int'),
    pytest.param({123, 456}, '123', id='intset-vs-str'),
    pytest.param({'123', '456'}, 123, id='strset-vs-int'),
    pytest.param({'123', '456'}, '123', id='strset-vs-str'),
    pytest.param({re.compile(r'\d+')}, 123, id='regexpset-vs-int'),
    pytest.param(frozenset({123, 456}), 123, id='frozenset-vs-int'),

    # Resources & namespaces are matched by their own logic (tested elsewhere).
    pytest.param(resource(group='group'), resource('group', 'v1', 'plural'), id='group'),
    pytest.param(resource(plural='plural'), resource('group', 'v1', 'plural'), id='plural'),
])
def test_matching(pat: Any, val: Any) -> None:
    criteria = SampleCriteria()
    assert criteria._check(pat, val)


@pytest.mark.parametrize('pat, val, expected', [
    pytest.param(True, True, True, id='true-vs-true'),
    pytest.param(True, 123, True, id='true-vs-number'),
    pytest.param(True, 'TRue', True, id='true-vs-truestr'),
    pytest.param(True, 'YeS', True, id='true-vs-yesstr'),
    pytest.param(True, 'oN', True, id='true-vs-onstr'),
    pytest.param(True, 'T', True, id='true-vs-tstr'),
    pytest.param(True, '1', True, id='true-vs-1str'),
    pytest.param(True, 'hello', False, id='true-vs-string'),
    pytest.param(True, '', False, id='true-vs-empty'),
    pytest.param(True, 0, False, id='true-vs-zero'),
    pytest.param(True, False, False, id='true-vs-false'),
    pytest.param(True, None, False, id='true-vs-none'),
    pytest.param(False, False, True, id='false-vs-false'),
    pytest.param(False, 0, True, id='false-vs-zero'),
    pytest.param(False, 'FaLSe', True, id='false-vs-falsestr'),
    pytest.param(False, 'oFF', True, id='false-vs-offstr'),
    pytest.param(False, 'F', True, id='false-vs-fstr'),
    pytest.param(False, '0', True, id='false-vs-0str'),
    pytest.param(False, 'hello', False, id='false-vs-string'),
    pytest.param(False, '', False, id='false-vs-empty'),
    pytest.param(False, 123, False, id='false-vs-number'),
    pytest.param(False, True, False, id='false-vs-true'),
    pytest.param(False, None, False, id='false-vs-none'),  # important! despite None evals to False.
])
def test_booleans(pat: Any, val: Any, expected: bool) -> None:
    criteria = SampleCriteria()
    assert criteria._check(pat, val) == expected


def test_regexps_fullmatch_never_partials() -> None:
    criteria = SampleCriteria()
    assert not criteria._check(re.compile(r'hello'), 'hello world')
    assert criteria._check(re.compile(r'hello.*'), 'hello world')
    assert not criteria._check(re.compile(b'hello'), b'hello world')
    assert criteria._check(re.compile(b'hello.*'), b'hello world')


@pytest.mark.parametrize('val', [None, True, False, 'str', {'key': 'val'}, StringEnum.A])
def test_catchall(val: Any) -> None:
    criteria = SampleCriteria()
    assert criteria._check(None, val)


@pytest.mark.parametrize('pat', [
    123,
    '123',
    b'123',
    re.compile(r'123'),
    re.compile(b'123'),
    {'q': '123'},
    {'q': b'123'},
    {'q': re.compile(r'^123$')},
    {'another-pattern': 'hello'},
    method.GET,
    action.LIST,
    ObjectEnum.A,
    StringEnum.A,
    StringEnum.A.name,
    StringEnum.A.value,
    BytesEnum.A,
    BytesEnum.A.name,
    BytesEnum.A.value,
    range(100, 200),
    {123, '123', b'123', re.compile(r'123')},
    frozenset({123, '123', b'123', re.compile(r'123')}),
    resource(group='grp'),
    resource(plural='plural'),
    object(),
], ids=lambda v: f"pat{v!r}")
@pytest.mark.parametrize('val', [
    None,
    True,
    False,
    0,
    '',
    b'',
    456,
    '456',
    b'456',
    {'q': '456'},
    {'q': b'456'},
    {'another-value': 'hello'},
    method.POST,
    action.UPDATE,
    ObjectEnum.B,
    StringEnum.B,
    StringEnum.B.name,
    StringEnum.B.value,
    BytesEnum.B,
    BytesEnum.B.name,
    BytesEnum.B.value,
    {456, '456', b'456'},
    frozenset({456, '456', b'456'}),
    resource('abc', 'v1', 'another'),
    object(),
], ids=lambda v: f"val{v!r}")
def test_mismatching(pat: Any, val: Any) -> None:
    criteria = SampleCriteria()
    assert not criteria._check(pat, val)


# Some cases that were not included in the pairs above:
@pytest.mark.parametrize('pat, val', [
    (True, object()),
    (False, object()),
])
def test_mismatching_extras(pat: Any, val: Any) -> None:
    criteria = SampleCriteria()
    assert not criteria._check(pat, val)
