import pytest

from kmock._internal.dicts import patch_dict

# NB: This is an internal (non-published) routine, but we still test it
# to make sure the patching logic works perfectly nice wherever it is used.

# NB: the detailed json-patching is tested in a 3rd-party library anyway.
# But we test it in full nevertheless, since we can replace the library.

#
# Dispatch and general behavior.
#

def test_dispatch_list_to_json_patch():
    d = patch_dict({'key': 'old'}, [{'op': 'replace', 'path': '/key', 'value': 'new'}])
    assert d == {'key': 'new'}


def test_empty_patch_list():
    d = patch_dict({'key': 'val'}, [])
    assert d == {'key': 'val'}


def test_kwargs_rejected():
    with pytest.raises(TypeError, match=r"not supported with JSON-patches"):
        patch_dict({'key': 'old'}, [{'op': 'add', 'path': '/x', 'value': 1}], extra='more')


def test_immutability():
    d = {'key': 'old'}
    r = patch_dict(d, [{'op': 'replace', 'path': '/key', 'value': 'new'}])
    assert d['key'] == 'old'
    assert r['key'] == 'new'


#
# add op.
#

def test_add_new_top_level_key():
    d = patch_dict({'a': 1}, [{'op': 'add', 'path': '/b', 'value': 2}])
    assert d == {'a': 1, 'b': 2}


def test_add_new_nested_key():
    d = patch_dict({'a': {'x': 1}}, [{'op': 'add', 'path': '/a/y', 'value': 2}])
    assert d == {'a': {'x': 1, 'y': 2}}


def test_add_nested_object():
    d = patch_dict({'a': 1}, [{'op': 'add', 'path': '/b', 'value': {'x': 10}}])
    assert d == {'a': 1, 'b': {'x': 10}}


def test_add_overwrites_existing_key():
    d = patch_dict({'a': 1}, [{'op': 'add', 'path': '/a', 'value': 2}])
    assert d == {'a': 2}


def test_add_into_array_by_index():
    d = patch_dict({'a': [1, 2, 3]}, [{'op': 'add', 'path': '/a/1', 'value': 99}])
    assert d == {'a': [1, 99, 2, 3]}


def test_add_to_end_of_array():
    d = patch_dict({'a': [1, 2]}, [{'op': 'add', 'path': '/a/-', 'value': 3}])
    assert d == {'a': [1, 2, 3]}


def test_add_nonexistent_intermediate_path():
    with pytest.raises(Exception, match=r"not found"):
        patch_dict({}, [{'op': 'add', 'path': '/a/b', 'value': 1}])


#
# remove op.
#

def test_remove_top_level_key():
    d = patch_dict({'a': 1, 'b': 2}, [{'op': 'remove', 'path': '/a'}])
    assert d == {'b': 2}


def test_remove_nested_key():
    d = patch_dict({'a': {'x': 1, 'y': 2}}, [{'op': 'remove', 'path': '/a/y'}])
    assert d == {'a': {'x': 1}}


def test_remove_array_element():
    d = patch_dict({'a': [1, 2, 3]}, [{'op': 'remove', 'path': '/a/1'}])
    assert d == {'a': [1, 3]}


def test_remove_nonexistent_path():
    with pytest.raises(Exception, match=r"non-existent object"):
        patch_dict({'a': 1}, [{'op': 'remove', 'path': '/nonexistent'}])


#
# replace op.
#

def test_replace_top_level_value():
    d = patch_dict({'a': 1}, [{'op': 'replace', 'path': '/a', 'value': 2}])
    assert d == {'a': 2}


def test_replace_nested_value():
    d = patch_dict({'a': {'x': 1}}, [{'op': 'replace', 'path': '/a/x', 'value': 2}])
    assert d == {'a': {'x': 2}}


def test_replace_scalar_with_dict():
    d = patch_dict({'a': 1}, [{'op': 'replace', 'path': '/a', 'value': {'x': 10}}])
    assert d == {'a': {'x': 10}}


def test_replace_dict_with_scalar():
    d = patch_dict({'a': {'x': 10}}, [{'op': 'replace', 'path': '/a', 'value': 1}])
    assert d == {'a': 1}


def test_replace_nonexistent_path():
    with pytest.raises(Exception, match=r"non-existent object"):
        patch_dict({'a': 1}, [{'op': 'replace', 'path': '/nonexistent', 'value': 2}])


#
# test op.
#

def test_test_matching_value():
    d = patch_dict({'a': 1}, [{'op': 'test', 'path': '/a', 'value': 1}])
    assert d == {'a': 1}


def test_test_nonmatching_value():
    with pytest.raises(Exception, match=r"not equal to tested value"):
        patch_dict({'a': 1}, [{'op': 'test', 'path': '/a', 'value': 999}])


def test_test_nonexistent_path():
    with pytest.raises(Exception, match=r"not found"):
        patch_dict({'a': 1}, [{'op': 'test', 'path': '/nonexistent', 'value': 1}])


#
# move op.
#

def test_move_top_level_key():
    d = patch_dict({'a': 1, 'b': 2}, [{'op': 'move', 'from': '/a', 'path': '/c'}])
    assert d == {'b': 2, 'c': 1}


def test_move_nested_key():
    d = patch_dict({'a': {'x': 1, 'y': 2}}, [{'op': 'move', 'from': '/a/x', 'path': '/a/z'}])
    assert d == {'a': {'y': 2, 'z': 1}}


def test_move_nonexistent_source():
    with pytest.raises(Exception, match=r"nonexistent"):
        patch_dict({'a': 1}, [{'op': 'move', 'from': '/nonexistent', 'path': '/b'}])


#
# copy op.
#

def test_copy_top_level_key():
    d = patch_dict({'a': 1}, [{'op': 'copy', 'from': '/a', 'path': '/b'}])
    assert d == {'a': 1, 'b': 1}


def test_copy_nested_key():
    d = patch_dict({'a': {'x': 1}}, [{'op': 'copy', 'from': '/a/x', 'path': '/b'}])
    assert d == {'a': {'x': 1}, 'b': 1}


def test_copy_nonexistent_source():
    with pytest.raises(Exception, match=r"nonexistent"):
        patch_dict({'a': 1}, [{'op': 'copy', 'from': '/nonexistent', 'path': '/b'}])


#
# Multi-op patches.
#

def test_multiple_ops_in_sequence():
    d = patch_dict({'a': 1}, [
        {'op': 'add', 'path': '/b', 'value': 2},
        {'op': 'replace', 'path': '/a', 'value': 10},
    ])
    assert d == {'a': 10, 'b': 2}


def test_ops_see_results_of_prior_ops():
    d = patch_dict({}, [
        {'op': 'add', 'path': '/a', 'value': 1},
        {'op': 'remove', 'path': '/a'},
    ])
    assert d == {}
