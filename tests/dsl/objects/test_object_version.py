from collections.abc import Iterator, Mapping

import pytest

from kmock import ObjectVersion


class ReadOnlyMapping(Mapping[str, str]):  # non-mutable
    def __len__(self) -> int:
        return 1

    def __iter__(self) -> Iterator[str]:
        yield from ['hello']

    def __getitem__(self, key: str) -> str:
        return 'world'


def test_dict_creation_from_empty():
    d = ObjectVersion()
    assert not d
    assert d.raw == {}
    assert dict(d) == {}


def test_dict_creation_from_dict_no_kwargs():
    arg = {'x': 'y'}
    d = ObjectVersion(arg)
    assert dict(d) == {'x': 'y'}


def test_dict_creation_from_dict_with_kwargs():
    arg = {'x': 'y'}
    d = ObjectVersion(arg, a='b')
    assert dict(d) == {'x': 'y', 'a': 'b'}
    assert arg == {'x': 'y'}  # unmodified!


def test_dict_creation_from_mapping_no_kwargs():
    arg = ReadOnlyMapping()
    d = ObjectVersion(arg)
    assert dict(d) == {'hello': 'world'}


def test_dict_creation_from_mapping_with_kwargs():
    arg = ReadOnlyMapping()
    d = ObjectVersion(arg, a='b')
    assert dict(d) == {'hello': 'world', 'a': 'b'}


def test_dict_creation_unwraps_no_kwargs():
    arg = ObjectVersion({'x': 'y'})
    d = ObjectVersion(arg)
    assert dict(d) == {'x': 'y'}


def test_dict_creation_unwraps_with_kwargs():
    arg = ObjectVersion({'x': 'y'})
    d = ObjectVersion(arg, a='b')
    assert dict(d) == {'x': 'y', 'a': 'b'}


def test_dict_creation_decouples_the_arg():
    arg = {'x': 'y'}
    d = ObjectVersion(arg)
    assert d.raw is not arg

    arg['new'] = 'value'
    d['other'] = 'value'
    assert dict(d) == {'x': 'y', 'other': 'value'}
    assert arg == {'x': 'y', 'new': 'value'}


def test_dict_creation_fails_on_unknown():
    with pytest.raises(TypeError, match=r"Unsupported value: \[\('x', 'y'\)\]"):
        ObjectVersion([('x', 'y')])


def test_dict_repr_empty():
    d = ObjectVersion()
    r = repr(d)
    assert r == "ObjectVersion()"


def test_dict_repr_full():
    d = ObjectVersion({'x': 'y'}, a='b')
    r = repr(d)
    assert r == "ObjectVersion({'x': 'y', 'a': 'b'})"


def test_dict_iter_empty():
    d = ObjectVersion()
    assert list(d) == []


def test_dict_iter_full():
    d = ObjectVersion({'x': 'y'}, a='b')
    assert list(d) == ['x', 'a']


def test_dict_bool_empty():
    d = ObjectVersion()
    assert not d


def test_dict_bool_full():
    d = ObjectVersion({'x': 'y'}, a='b')
    assert d


def test_dict_len_empty():
    d = ObjectVersion()
    assert len(d) == 0


def test_dict_len_full():
    d = ObjectVersion({'x': 'y'}, a='b')
    assert len(d) == 2


def test_dict_contains():
    d = ObjectVersion({'x': 'y'}, a='b')
    assert 'x' in d
    assert 'a' in d
    assert 'z' not in d


def test_dict_equality():
    d = ObjectVersion({'x': 'y'}, a='b')
    assert d == {'x': 'y', 'a': 'b'}
    assert d == {'x': ..., 'a': ...}
    assert not d == 123  # unsupported type


def test_dict_inequality():
    d = ObjectVersion({'x': 'y'}, a='b')
    assert d != {'x': 'y'}
    assert d != {'a': 'b'}
    assert d != {'absent': 'absent'}
    assert d != 123  # unsupported type


def test_dict_misused_matching_with_gt():
    d = ObjectVersion()
    with pytest.raises(NotImplementedError, match=r"semantically meaningless"):
        assert d > {'x': 'y'}


def test_dict_misused_matching_with_lt():
    d = ObjectVersion()
    with pytest.raises(NotImplementedError, match=r"semantically meaningless"):
        assert d < {'x': 'y'}


def test_dict_partial_matching_when_self_is_object():
    d = ObjectVersion({'x': 'y'}, a='b')
    assert d >= {'x': 'y'}
    assert d >= {'a': 'b'}
    assert d >= {'x': 'y', 'a': 'b'}
    assert not d >= {'wrong': 'value'}


def test_dict_partial_matching_when_self_is_pattern():
    d = ObjectVersion({'x': 'y'}, a='b')
    assert not d <= {'x': 'y'}
    assert not d <= {'a': 'b'}
    assert d <= {'x': 'y', 'a': 'b'}
    assert not d <= {'wrong': 'value'}
    with pytest.raises(TypeError):
        d <= 123  # unsupported type


def test_dict_partial_mismatching():
    d = ObjectVersion({'x': 'y'}, a='b')
    assert not d >= {'absent': 'absent'}
    with pytest.raises(TypeError):
        d >= 123  # unsupported type


# From now on, we believe the <= and >= are symmetric and focus on details.
def test_dict_nested_matching():
    d = ObjectVersion({'spec': {'x': 'y', 'a': 'b'}})
    assert d >= {'spec': {'x': 'y'}}
    assert d >= {'spec': {'a': 'b'}}
    assert d >= {'spec': {'x': 'y', 'a': 'b'}}


def test_dict_presence_absence_of_keys():
    d = ObjectVersion({'spec': {'x': 'y', 'a': 'b'}})
    assert d >= {'spec': ...}
    assert d >= {'spec': {'x': ...}}
    assert not d >= {'absent': ...}
    assert not d >= {'spec': {'absent': ...}}


def test_dict_getting_wraps_dicts():
    d = ObjectVersion({'spec': {'x': 'y', 'a': 'b'}})
    sub = d['spec']
    assert isinstance(sub, ObjectVersion)
    assert sub == {'x': 'y', 'a': 'b'}


def test_dict_getting_wraps_mappings():
    d = ObjectVersion({'spec': ReadOnlyMapping()})
    sub = d['spec']
    assert isinstance(sub, ObjectVersion)
    assert sub == {'hello': 'world'}


def test_dict_getting_returns_scalars():
    d = ObjectVersion({'spec': {'x': 'y', 'a': 'b'}})
    assert d['spec']['x'] == 'y'
    assert isinstance(d['spec']['x'], str)


def test_dict_getting_of_absent():
    d = ObjectVersion()
    with pytest.raises(KeyError):
        d['absent']


def test_dict_setting_adds():
    d = ObjectVersion({'spec': {'x': 'y', 'a': 'b'}})
    d['new'] = 'value'
    assert d == {'spec': {'x': 'y', 'a': 'b'}, 'new': 'value'}


def test_dict_setting_overwrites():
    d = ObjectVersion({'spec': {'x': 'y', 'a': 'b'}})
    d['spec'] = {'hello': 'world'}
    assert d == {'spec': {'hello': 'world'}}


def test_dict_setting_unwraps():
    d = ObjectVersion({'spec': {'x': 'y', 'a': 'b'}})
    d['spec'] = ObjectVersion({'hello': 'world'})
    assert d.raw == {'spec': {'hello': 'world'}}
    assert not isinstance(d.raw['spec'], ObjectVersion)


def test_dict_deletion():
    d = ObjectVersion({'spec': {'x': 'y', 'a': 'b'}, 'other': 'remains'})
    del d['spec']
    assert d == {'other': 'remains'}


def test_dict_is_slotted():
    d = ObjectVersion()
    with pytest.raises(AttributeError):
        d.xyz = None
