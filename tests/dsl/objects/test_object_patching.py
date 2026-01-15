import pytest

from kmock._internal.k8s_dicts import patch_dict

# NB: This is an internal (non-published) routine, but we still test it
# to make sure the patching logic works perfectly nice wherever it is used.


def test_patch_key_preservation_and_addition():
    d = patch_dict({'key': 'old'}, {'other': 'new'}, extra='more')
    assert d == {'key': 'old', 'other': 'new', 'extra': 'more'}


def test_patch_key_overwriting_via_patch():
    d = patch_dict({'key': 'old'}, {'key': 'new', 'extra': 'more'})
    assert d == {'key': 'new', 'extra': 'more'}


def test_patch_key_overwriting_via_kwargs():
    d = patch_dict({'key': 'old'}, {}, key='new', extra='more')
    assert d == {'key': 'new', 'extra': 'more'}


def test_patch_key_removal_via_patch():
    d = patch_dict({'key': 'old'}, {'key': None, 'extra': None})
    assert d == {}


def test_patch_key_removal_via_kwargs():
    d = patch_dict({'key': 'old'}, {}, key=None, extra=None)
    assert d == {}


def test_patch_nested_nulls_removal():
    d = patch_dict({}, {'spec': {'key': None, 'other': 'unaffected'}})
    assert d == {'spec': {'other': 'unaffected'}}


def test_patch_recursive_dicts():
    d = {'spec': {'key': 'old', 'other': 'unaffected'}}
    p = {'spec': {'key': 'new'}}
    r = patch_dict(d, p)
    assert r == {'spec': {'key': 'new', 'other': 'unaffected'}}


def test_patch_misaligned_types_dict_scalar():
    with pytest.raises(ValueError, match=r"a dict by a scalar"):
        patch_dict({'spec': {'key': 'old'}}, {'spec': 123})


def test_patch_misaligned_types_scalar_dict():
    with pytest.raises(ValueError, match=r"a scalar by a dict"):
        patch_dict({'spec': 123}, {'spec': {'key': 'new'}})


def test_patch_immutability():
    d = {'key': 'old'}
    p = {'key': 'new'}
    r = patch_dict(d, p)
    assert d['key'] == 'old'  # unaffected at source
    assert r['key'] == 'new'


def test_patch_ordering():
    d = {'old-key': 'old'}
    p = {'other': 'other', 'old-key': 'new', 'new-key': 'val'}
    r = patch_dict(d, p)
    assert list(r) == ['old-key', 'other', 'new-key']
