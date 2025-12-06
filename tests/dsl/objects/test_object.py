from collections.abc import Mapping

import pytest

from kmock import Object, ObjectHistory, ObjectVersion


def test_versioned_from_none():
    d = Object(None)
    assert d.history == [None]


def test_versioned_from_dict():
    d = Object({'v': 1})
    assert d.history == [{'v': 1}]


def test_versioned_from_list():
    d = Object([{'v': 1}, None, {'v': 2}])
    assert d.history == [{'v': 1}, None, {'v': 2}]
    assert isinstance(d.history[0], ObjectVersion)
    assert isinstance(d.history[2], ObjectVersion)


def test_versioned_from_iterable():
    d = Object(v for v in [{'v': 1}, None, {'v': 2}])
    assert d.history == [{'v': 1}, None, {'v': 2}]
    assert isinstance(d.history[0], ObjectVersion)
    assert isinstance(d.history[2], ObjectVersion)


def test_versioned_from_unsupported():
    with pytest.raises(TypeError, match="Unsupported history"):
        Object(123)


def test_versioned_repr_empty():
    d = Object()
    r = repr(d)
    assert r == "Object()"


def test_versioned_repr_full():
    d = Object([{'v': 1}, None])
    r = repr(d)
    assert r == "Object([{'v': 1}, None])"


def test_versioned_iter_empty():
    d = Object()
    assert list(d) == []


def test_versioned_iter_full():
    d = Object([{'v': 1, 'key': 'val'}])
    assert list(d) == ['v', 'key']


def test_versioned_iter_softdeleted():
    d = Object([{'v': 1}, None])
    assert list(d) == []


def test_versioned_len_empty():
    d = Object()
    assert len(d) == 0


def test_versioned_len_full():
    d = Object([{'v': 1, 'key': 'val'}])
    assert len(d) == 2


def test_versioned_len_softdeleted():
    d = Object([{'v': 1}, None])
    assert len(d) == 0


def test_versioned_bool_empty():
    d = Object()
    assert not d


def test_versioned_bool_full():
    d = Object([{'v': 1, 'key': 'val'}])
    assert d
    d = Object([{}])
    assert not d


def test_versioned_bool_softdeleted():
    d = Object([{'v': 1}, None])
    assert not d


# Assume that if it works sometimes, it works always — tested in DictVersion.
def test_versioned_pattern_matching_when_self_is_object():
    d = Object([{'v': 1}])
    assert d >= {'v': 1}
    assert d >= {'v': ...}
    assert not d >= {'absent': 'absent'}
    assert {'v': 1} <= d
    assert {'v': ...} <= d
    assert not {'absent': 'absent'} <= d


def test_versioned_pattern_matching_when_self_is_pattern():
    d = Object([{'v': 1}])
    assert d <= {'v': 1}
    assert d <= {'v': 1, 'extra': 'okay'}
    assert not d <= {'absent': 'absent'}
    with pytest.raises(TypeError):
        not d <= 123  # unsupported type
    assert {'v': 1} >= d
    assert {'v': 1, 'extra': 'okay'} >= d
    assert not {'absent': 'absent'} >= d
    with pytest.raises(TypeError):
        123 >= d  # unsupported type


def test_versioned_pattern_matching_softdeleted():
    d = Object([{'v': 1}, None])
    assert d >= {}
    assert not d >= {'v': 1}
    assert not {'v': 1} <= d
    assert {} <= d


def test_versioned_misused_matching():
    d = Object([{'v': 1}])
    with pytest.raises(NotImplementedError, match="semantically meaningless"):
        d > {}
    with pytest.raises(NotImplementedError, match="semantically meaningless"):
        {} < d
    with pytest.raises(NotImplementedError, match="semantically meaningless"):
        d < {}
    with pytest.raises(NotImplementedError, match="semantically meaningless"):
        {} > d


def test_versioned_misused_matching_softdeleted():
    d = Object([{'v': 1}, None])
    with pytest.raises(NotImplementedError, match="semantically meaningless"):
        d > {}
    with pytest.raises(NotImplementedError, match="semantically meaningless"):
        {} < d
    with pytest.raises(NotImplementedError, match="semantically meaningless"):
        d < {}
    with pytest.raises(NotImplementedError, match="semantically meaningless"):
        {} > d


def test_versioned_equality_full():
    d = Object([{'v': 1}])
    assert d == {'v': 1}
    assert not d != {'v': 1}
    assert d != {'v': 1, 'absent': 'absent'}
    assert not d == {'v': 1, 'absent': 'absent'}
    assert not d == 123  # unsupported type


def test_versioned_equality_softdeleted():
    d = Object([{'v': 1}, None])
    assert d == {}
    assert d != {'v': 1}
    assert not d == {'v': 1}
    assert not d != {}
    assert d != 123  # unsupported type


def test_versioned_contains_full():
    d = Object([{'v': 1}])
    assert 'v' in d
    assert 'absent' not in d


def test_versioned_contains_softdeleted():
    d = Object([{'v': 1}, None])
    assert 'v' not in d
    assert 'absent' not in d


def test_versioned_getting_full():
    d = Object([{'v': 1, 'spec': {'key': 'val'}}])
    assert d['v'] == 1
    assert d['spec']['key'] == 'val'
    assert isinstance(d['spec'], ObjectVersion)


def test_versioned_getting_softdeleted():
    d = Object([{'v': 1}, None])
    with pytest.raises(KeyError):
        d['v']


def test_versioned_setting_full():
    d = Object([{'v': 1}])
    d['v'] = 2
    d['new'] = 'value'
    assert d.history == [{'v': 2, 'new': 'value'}]


def test_versioned_setting_softdeleted():
    d = Object([{'v': 1}, None])
    d['v'] = 2
    assert d == {'v': 2}


def test_versioned_deleting_full():
    d = Object([{'v': 1, 'old': 'value'}])
    del d['old']
    assert d.history == [{'v': 1}]


def test_versioned_deleting_softdeleted():
    d = Object([{'v': 1}, None])
    with pytest.raises(KeyError):
        del d['v']


def test_versioned_clearing_full():
    d = Object([{'v': 1}])
    d.clear()
    assert d.history == [{}]


def test_versioned_clearing_softdeleted():
    d = Object([{'v': 1}, None])
    d.clear()
    assert d.history == [{'v': 1}, None]  # no new item added


def test_versioned_softdeleting_full():
    d = Object([{'v': 1}])
    d.delete()
    assert d.history == [{'v': 1}, None]


def test_versioned_softdeleting_twice():
    d = Object([{'v': 1}, None])
    d.delete()
    assert d.history == [{'v': 1}, None, None]


def test_versioned_populating_empty():
    d = Object()
    d.create({'v': 2})
    assert d.history == [{'v': 2}]


def test_versioned_populating_softdeleted():
    d = Object([{'v': 1}, None])
    d.create({'v': 2})
    assert d.history == [{'v': 1}, None, {'v': 2}]


def test_versioned_populating_full():
    d = Object([{'v': 1, 'key': 'val'}])
    d.create({'v': 2})
    assert d.history == [{'v': 1, 'key': 'val'}, {'v': 2}]


def test_versioned_patching_full():
    d = Object([{'v': 1}])
    d.patch({'v': 2}, new='value')
    assert d.history == [{'v': 1}, {'v': 2, 'new': 'value'}]


def test_versioned_patching_empty():
    d = Object()
    d.patch({'v': 2})
    assert d.history == [{'v': 2}]


def test_versioned_patching_softdeleted():
    d = Object([{'v': 1}, None])
    d.patch({'v': 2})
    assert d.history == [{'v': 1}, None, {'v': 2}]


def test_versioned_checking_empty_when_full():
    d = Object([{'v': 1}])
    assert not d.empty


def test_versioned_checking_empty_when_empty():
    d = Object()
    assert d.empty


def test_versioned_checking_empty_when_softdeleted():
    d = Object([{'v': 1}, None])
    assert not d.empty


def test_versioned_checking_softdeleted_when_empty():
    d = Object()
    assert d.deleted


def test_versioned_checking_softdeleted_when_full():
    d = Object([{'v': 1}])
    assert not d.deleted


def test_versioned_checking_softdeleted_when_softdeleted():
    d = Object([{'v': 1}, None])
    assert d.deleted


def test_versioned_last_full():
    d = Object([{'v': 1}, {'v': 2}])
    assert d.last == {'v': 2}


def test_versioned_last_empty():
    d = Object()
    with pytest.raises(ValueError, match="no last seen state"):
        d.last


def test_versioned_last_softdeleted():
    d = Object([{'v': 1}, {'v': 2}, None, None])
    assert d.last == {'v': 2}


def test_versioned_raw_full():
    d = Object([{'v': 1}, {'v': 2}])
    assert d.raw == {'v': 2}
    assert not isinstance(d.raw, ObjectVersion)


def test_versioned_raw_empty():
    d = Object()
    with pytest.raises(ValueError, match="The object is soft-deleted"):
        d.raw


def test_versioned_raw_softdeleted():
    d = Object([{'v': 1}, {'v': 2}, None, None])
    with pytest.raises(ValueError, match="The object is soft-deleted"):
        d.raw


def test_versioned_history_getting():
    d = Object([{'v': 1}, {'v': 2}, None, None])
    assert d.history == [{'v': 1}, {'v': 2}, None, None]


def test_versioned_history_setting():
    d = Object([{'v': 1}, {'v': 2}, None, None])
    d.history = [{'v': 1}, {'v': 3}]
    assert d.history == [{'v': 1}, {'v': 3}]


def test_versioned_history_deleting():
    d = Object([{'v': 1}, {'v': 2}, None, None])
    del d.history
    assert d.history == []


def test_versioned_is_slotted():
    d = Object([{'v': 1}])
    with pytest.raises(AttributeError):
        d.xyz = 123
