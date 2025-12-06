from collections.abc import Iterable, Mapping

import pytest

import kmock
from kmock import ObjectHistory, ObjectVersion


def test_empty_history():
    h = ObjectHistory()
    assert not h
    assert len(h) == 0
    assert list(h) == []


def test_history_from_list():
    v1 = ObjectVersion({'v': 1})
    v2 = ObjectVersion({'v': 2})
    h = ObjectHistory([v1, None, v2])
    assert h
    assert len(h) == 3
    assert list(h) == [v1, None, v2]


def test_history_repr_empty():
    h = ObjectHistory()
    r = repr(h)
    assert r == "ObjectHistory()"


def test_history_repr_full():
    h = ObjectHistory([None, {'v': 1}])
    r = repr(h)
    assert r == "ObjectHistory([None, {'v': 1}])"


def test_history_equality():
    h = ObjectHistory([None, {'v': 1}])
    assert h == [None, {'v': 1}]
    assert not h == 123  # unsupported type


def test_history_inequality():
    h = ObjectHistory([None, {'v': 1}])
    assert h != [None, {'v': 2}]
    assert h != 123  # unsupported type


def test_history_subset():
    h = ObjectHistory([None, {'v': 1}])
    assert h >= [{'v': 1}]
    assert h >= [None]
    assert not h >= [{'v': 2}]
    with pytest.raises(TypeError):
        h >= 123  # unsupported type


def test_history_possibilities():
    h = ObjectHistory([None, {'v': 1}])
    assert h <= [None, {'v': 1}]  # both must be present
    assert h <= [{'v': 1}, None, {'v': 2}]
    assert not h <= [{'v': 1}, {'v': 2}]  # None is absent
    assert not h <= [None, {'v': 2}]  # v1 is absent
    assert not h <= [{'v': 2}]  # both real are absent
    with pytest.raises(TypeError):
        h <= 123  # unsupported type


def test_history_getting_by_index():
    v1 = ObjectVersion({'v': 1})
    v2 = ObjectVersion({'v': 2})
    h = ObjectHistory([v1, None, v2])
    assert h[0] == v1
    assert h[1] is None
    assert h[2] == v2
    assert h[-3] == v1
    assert h[-2] is None
    assert h[-1] == v2


def test_history_getting_by_slice():
    v1 = ObjectVersion({'v': 1})
    v2 = ObjectVersion({'v': 2})
    h = ObjectHistory([v1, None, v2])
    assert h[:] == [v1, None, v2]
    assert h[:2] == [v1, None]
    assert h[1:] == [None, v2]
    assert h[:-1] == [v1, None]
    assert h[-2:] == [None, v2]
    assert h[::-1] == [v2, None, v1]


def test_history_deleting_by_index():
    v1 = ObjectVersion({'v': 1})
    v2 = ObjectVersion({'v': 2})
    h = ObjectHistory([v1, None, v2])
    del h[0]
    assert list(h) == [None, v2]
    del h[-1]
    assert list(h) == [None]


def test_history_deleting_by_slice():
    v1 = ObjectVersion({'v': 1})
    v2 = ObjectVersion({'v': 2})
    h = ObjectHistory([v1, None, v2])
    del h[1:2]
    assert list(h) == [v1, v2]


def test_history_setting_by_index():
    v1 = ObjectVersion({'v': 1})
    v2 = ObjectVersion({'v': 2})
    v3 = ObjectVersion({'v': 3})
    h = ObjectHistory([v1, None, v2])
    h[1] = v3
    assert list(h) == [v1, v3, v2]
    h[0] = h[2] = None
    assert list(h) == [None, v3, None]


def test_history_setting_by_slice():
    v1 = ObjectVersion({'v': 1})
    v2 = ObjectVersion({'v': 2})
    v3 = ObjectVersion({'v': 3})
    h = ObjectHistory([v1, None, v2])
    h[:] = [v3, None, v3]
    assert list(h) == [v3, None, v3]
    h[-1:] = [v1]
    assert list(h) == [v3, None, v1]
    h[:2] = [v2]
    assert list(h) == [v2, v1]


def test_history_with_bad_keys_or_values():
    h = ObjectHistory([{}])
    with pytest.raises(TypeError):
        h[0] = object()
    with pytest.raises(TypeError):
        h[:] = object()
    with pytest.raises(TypeError):
        h['unsupported']
    with pytest.raises(TypeError):
        h['unsupported'] = ObjectVersion()
    with pytest.raises(TypeError):
        del h['unsupported']


def test_history_unwrappig_on_creation():
    v1 = ObjectVersion({'v': 1})
    h = ObjectHistory([v1])
    assert h[0] == v1
    assert h[0] is not v1


def test_history_unwrapping_on_setting():
    v1 = ObjectVersion({'v': 1})
    h = ObjectHistory()
    h[:] = [v1]
    assert h[0] == v1
    assert h[0] is not v1


def test_history_conversion_from_dict_by_index():
    v1 = ObjectVersion({'v': 1})
    v2 = ObjectVersion({'v': 2})
    h = ObjectHistory([v1, None, v2])
    h[1] = {'v': 3}
    assert isinstance(h[1], ObjectVersion)
    assert h[1] == {'v': 3}


def test_history_conversion_from_list_by_slice():
    v1 = ObjectVersion({'v': 1})
    v2 = ObjectVersion({'v': 2})
    h = ObjectHistory([v1, None, v2])
    h[-1:] = [{'v': 3}, None, {'v': 4}]
    assert isinstance(h[2], ObjectVersion)
    assert isinstance(h[4], ObjectVersion)
    assert h[-3] == {'v': 3}
    assert h[-2] is None
    assert h[-1] == {'v': 4}


def test_history_conversion_from_none_by_slice_fails():
    h = ObjectHistory()
    with pytest.raises(TypeError, match=r"Assigning None to history slices"):
        h[:] = None


def test_history_conversion_from_dict_by_slice_fails():
    h = ObjectHistory()
    with pytest.raises(TypeError, match=r"Assigning dicts to history slices"):
        h[:] = {}


def test_history_conversion_from_list_by_index_fails():
    h = ObjectHistory()
    with pytest.raises(TypeError, match=r"Unsupported types"):
        h[0] = [{}]


def test_history_conversion_from_unknown_by_slice_fails():
    h = ObjectHistory()
    with pytest.raises(TypeError, match=r"Unsupported item"):
        h[:] = [123]


def test_history_clearing():
    h = ObjectHistory([None])
    h.clear()
    assert not h
    assert len(h) == 0
    assert list(h) == []


def test_history_popping():
    h = ObjectHistory([{'v': 1}])
    assert h.pop() == {'v': 1}
    assert not h
    assert len(h) == 0
    assert list(h) == []


def test_history_insertion():
    h = ObjectHistory([None])
    h.insert(1, {'v': 1})
    assert len(h) == 2
    assert list(h) == [None, {'v': 1}]


def test_history_appending():
    h = ObjectHistory([None])
    h.append({'v': 1})
    assert len(h) == 2
    assert list(h) == [None, {'v': 1}]


def test_history_extending():
    h = ObjectHistory([None])
    h.extend([{'v': 1}])
    assert len(h) == 2
    assert list(h) == [None, {'v': 1}]


def test_history_removing_first_none():
    h = ObjectHistory([{'v': 1}, None, {'v': 2}, None, {'v': 2}])
    h.remove(None)
    assert len(h) == 4
    assert list(h) == [{'v': 1}, {'v': 2}, None, {'v': 2}]


def test_history_removing_first_dict():
    h = ObjectHistory([{'v': 1}, None, {'v': 2}, None, {'v': 2}])
    h.remove({'v': 2})
    assert len(h) == 4
    assert list(h) == [{'v': 1}, None, None, {'v': 2}]


def test_history_removing_nonexistent():
    h = ObjectHistory([{'v': 1}, None, {'v': 2}, None, {'v': 2}])
    h.remove({'v': 9})
    assert len(h) == 5
    assert list(h) == [{'v': 1}, None, {'v': 2}, None, {'v': 2}]


def test_history_last_real():
    h = ObjectHistory([None, {'v': 1}, None, {'v': 2}])
    assert h.last == {'v': 2}


def test_history_last_none():
    h = ObjectHistory([None, {'v': 1}, None, {'v': 2}, None])
    assert h.last == {'v': 2}


def test_history_last_empty():
    h = ObjectHistory()
    with pytest.raises(ValueError, match=r"has no last seen state"):
        h.last


def test_history_raw_full():
    h = ObjectHistory([{'v': 1}, None, {'v': 2}])
    assert h.raw == [{'v': 1}, None, {'v': 2}]
    assert isinstance(h.raw[0], ObjectVersion)
    assert isinstance(h.raw[2], ObjectVersion)


def test_history_is_slotted():
    h = ObjectHistory()
    with pytest.raises(AttributeError):
        h.xyz = 123
