import pytest

from kmock import KubernetesEmulator, Object, ObjectVersion, ObjectsArray, resource


def test_objects_properties_empty():
    objs = ObjectsArray()
    assert not objs
    assert len(objs) == 0
    assert list(objs) == []
    assert list(objs.keys()) == []
    assert list(objs.values()) == []
    assert list(objs.items()) == []


def test_objects_properties_filled():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = {'spec': 'value'}
    assert objs
    assert len(objs) == 1
    assert list(objs) == [(res, 'ns1', 'n1')]
    assert list(objs.keys()) == [(res, 'ns1', 'n1')]
    assert list(objs.values()) == [{'spec': 'value'}]
    assert list(objs.items()) == [((res, 'ns1', 'n1'), {'spec': 'value'})]


# All specified patterns must be present at least once (may overlap).
def test_objects_inclusion_of_patterns():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = {'spec': 'value', 'extra': 'irrelevant'}
    objs[res, 'ns1', 'n2'] = {'spec': 'other', 'extra': 'irrelevant'}
    assert objs >= [{'spec': 'value'}]  # list
    assert objs >= ({'spec': 'other'},)  # tuple
    assert not objs >= [{'spec': 'value'}, {'spec': 'value'}]  # excess patterns
    assert not objs >= [{'wrong': 'unexistent'}]
    with pytest.raises(TypeError):
        objs >= 123  # unsupported type


# All existing objects must match at least one pattern (may overlap).
def test_objects_inclusion_of_objects():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = {'spec': 'value', 'extra': 'common'}
    objs[res, 'ns1', 'n2'] = {'spec': 'other', 'extra': 'common'}
    assert objs <= [{'spec': 'value'}, {'spec': 'other'}]  # list
    assert objs <= ({'spec': 'value'}, {'spec': 'other'})  # tuple
    assert objs <= [{'extra': 'common'}, {'extra': 'common'}]  # same for each
    assert not objs <= [{'extra': 'common'}]  # reuse is prohibited
    assert not objs <= [{'wrong': 'unexistent'}]
    with pytest.raises(TypeError):
        objs <= 123  # unsupported type


def test_objects_equality():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = {'spec': 'value'}
    objs[res, 'ns1', 'n2'] = {'spec': 'other'}

    assert objs == [{'spec': 'value'}, {'spec': 'other'}]  # list
    assert objs == ({'spec': 'value'}, {'spec': 'other'})  # tuple

    assert objs == [{'spec': 'other'}, {'spec': 'value'}]  # list, shuffled
    assert objs == ({'spec': 'other'}, {'spec': 'value'})  # tuple, shuffled

    assert objs != [{'spec': 'value'}]  # shorter than actual
    assert objs != [{'spec': 'value'}, {'spec': 'other'}, {'spec': 'wrong'}]  # longer
    assert objs != [{'spec': 'value'}, {'spec': 'other'}, {'spec': 'other'}]  # duplicated

    assert not objs == 123  # unsupported type
    assert objs != 123  # unsupported type


def test_objects_contains():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = {'spec': 'value', 'extra': 'common'}
    objs[res, 'ns1', 'n2'] = {'spec': 'other', 'extra': 'common'}

    assert (res, 'ns1', 'n1') in objs
    assert (res, 'ns1', 'nX') not in objs
    assert (res, 'nsX', 'n1') not in objs


def test_objects_getting_of_existent_objects():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = {'spec': 'value', 'extra': 'common'}
    objs[res, 'ns1', 'n2'] = {'spec': 'other', 'extra': 'common'}
    obj = objs[res, 'ns1', 'n1']
    assert isinstance(obj, Object)


def test_objects_getting_of_existent_versions():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = [
        {'spec': 'value', 'extra': 'common'},
        {'spec': 'other', 'extra': 'common'},
    ]
    first_version = objs[res, 'ns1', 'n1', 0]  # positive (kind of)
    positive_version = objs[res, 'ns1', 'n1', 1]  # positive
    negative_version = objs[res, 'ns1', 'n1', -1]  # negative
    assert isinstance(first_version, ObjectVersion)
    assert isinstance(positive_version, ObjectVersion)
    assert isinstance(negative_version, ObjectVersion)
    assert first_version == {'spec': 'value', 'extra': 'common'}
    assert positive_version == {'spec': 'other', 'extra': 'common'}
    assert negative_version == {'spec': 'other', 'extra': 'common'}


def test_objects_getting_of_existent_history():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = [{'spec': 'value'}, {'spec': 'other'}]
    hist_positive = objs[res, 'ns1', 'n1', 0:1]
    hist_negative = objs[res, 'ns1', 'n1', -1:]
    hist_full = objs[res, 'ns1', 'n1', :]
    assert isinstance(hist_positive, list)
    assert isinstance(hist_negative, list)
    assert isinstance(hist_full, list)
    assert all(isinstance(v, ObjectVersion) for v in hist_positive)
    assert all(isinstance(v, ObjectVersion) for v in hist_negative)
    assert all(isinstance(v, ObjectVersion) for v in hist_full)
    assert hist_positive == [{'spec': 'value'}]
    assert hist_negative == [{'spec': 'other'}]
    assert hist_full == [{'spec': 'value'}, {'spec': 'other'}]


def test_objects_getting_of_unexistent_object():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    with pytest.raises(KeyError):
        objs[res, 'ns1', 'nX']


def test_objects_getting_of_unexistent_version():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = {'spec': 'value', 'extra': 'common'}
    with pytest.raises(KeyError):
        objs[res, 'ns1', 'nX', 1]
    with pytest.raises(IndexError):
        objs[res, 'ns1', 'n1', 1]


def test_objects_getting_of_unexistent_history():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    with pytest.raises(KeyError):
        objs[res, 'ns1', 'nX', :]


# NB: setting of an object per se is indirectly tested by all tests around.
def test_objects_setting_of_version():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = [{'spec': 1}, {'spec': 2}, {'spec': 3}]
    objs[res, 'ns1', 'n1', -2] = {'spec': 9}
    assert objs[res, 'ns1', 'n1', :] == [{'spec': 1}, {'spec': 9}, {'spec': 3}]


def test_objects_setting_of_history_slice():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = [{'spec': 1}, {'spec': 2}, {'spec': 3}]
    objs[res, 'ns1', 'n1', -2:-1] = [{'spec': 8}, {'spec': 9}]
    assert objs[res, 'ns1', 'n1', :] == [{'spec': 1}, {'spec': 8}, {'spec': 9}, {'spec': 3}]


def test_objects_setting_of_unexistent_version():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = [{'spec': 1}, {'spec': 2}, {'spec': 3}]
    with pytest.raises(KeyError):
        objs[res, 'ns1', 'nX', 9] = {}
    with pytest.raises(IndexError):
        objs[res, 'ns1', 'n1', 9] = {}


def test_objects_setting_of_unexistent_history():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = [{'spec': 1}, {'spec': 2}, {'spec': 3}]
    with pytest.raises(KeyError):
        del objs[res, 'ns1', 'nX', :]


def test_objects_deletion_of_object():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = [{'spec': 1}, {'spec': 2}, {'spec': 3}]
    objs[res, 'ns1', 'n2'] = [{'spec': 1}, {'spec': 2}, {'spec': 3}]
    del objs[res, 'ns1', 'n1']
    assert list(objs) == [(res, 'ns1', 'n2')]


def test_objects_deletion_of_version():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = [{'spec': 1}, {'spec': 2}, {'spec': 3}]
    del objs[res, 'ns1', 'n1', -2]
    assert objs[res, 'ns1', 'n1', :] == [{'spec': 1}, {'spec': 3}]


def test_objects_deletion_of_history():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = [{'spec': 1}, {'spec': 2}, {'spec': 3}]
    del objs[res, 'ns1', 'n1', -2:-1]
    assert objs[res, 'ns1', 'n1', :] == [{'spec': 1}, {'spec': 3}]


def test_objects_deletion_of_unexistent_version():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = [{'spec': 1}, {'spec': 2}, {'spec': 3}]
    with pytest.raises(KeyError):
        del objs[res, 'ns1', 'nX', 9]
    with pytest.raises(IndexError):
        del objs[res, 'ns1', 'n1', 9]


def test_objects_deletion_of_unexistent_history():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = [{'spec': 1}, {'spec': 2}, {'spec': 3}]
    with pytest.raises(KeyError):
        del objs[res, 'ns1', 'nX', :]


def test_objects_unsupported_keys_or_values():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    with pytest.raises(TypeError):
        objs[res, 'ns1', 'n1', 0] = []
    with pytest.raises(TypeError):
        objs[res, 'ns1', 'n1', :] = {}
    with pytest.raises(TypeError):
        objs[res, 'ns1', 'n1', :] = None
    with pytest.raises(TypeError):
        objs['unsupported']
    with pytest.raises(TypeError):
        objs['unsupported'] = {}
    with pytest.raises(TypeError):
        objs['unsupported'] = []
    with pytest.raises(TypeError):
        del objs['unsupported']


def test_objects_clearing():
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    objs = ObjectsArray()
    objs[res, 'ns1', 'n1'] = [{'spec': 1}, {'spec': 2}, {'spec': 3}]
    objs[res, 'ns1', 'n2'] = [{'spec': 1}, {'spec': 2}, {'spec': 3}]
    objs.clear()
    assert list(objs) == []


def test_objects_array_is_slotted():
    objs = ObjectsArray()
    with pytest.raises(AttributeError):
        objs.xyz = 123


# Not the functionality (tested above), but just the attribute itself.
@pytest.mark.kmock(cls=KubernetesEmulator)
def test_objects_is_accessible(kmock: KubernetesEmulator):
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    kmock.objects[res, 'ns1', 'n1'] = [{'spec': 1}, {'spec': 2}, {'spec': 3}]
    assert isinstance(kmock.objects, ObjectsArray)
    assert kmock.objects[res, 'ns1', 'n1'] == {'spec': 3}


@pytest.mark.kmock(cls=KubernetesEmulator)
def test_objects_is_readonly(kmock: KubernetesEmulator):
    with pytest.raises(AttributeError):
        kmock.objects = ObjectsArray()
