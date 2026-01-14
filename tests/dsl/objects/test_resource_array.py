import pytest

from kmock import KubernetesScaffold, ResourceInfo, ResourcesArray, resource


def test_resource_info_empty() -> None:
    info = ResourceInfo()
    assert info.namespaced is None
    assert info.kind is None
    assert info.singular is None
    assert info.verbs == set()
    assert info.shortnames == set()
    assert info.categories == set()
    assert info.subresources == set()


def test_resource_info_kwargs() -> None:
    info = ResourceInfo(
        namespaced=True,
        kind='Kind',
        singular='Singlular',
        verbs=['verb1', 'verb2'],
        shortnames=('short1', 'short2'),
        categories={'cat1', 'cat2'},
        subresources=frozenset(['sub1', 'sub2']),
    )
    assert info.namespaced == True
    assert info.kind == 'Kind'
    assert info.singular == 'Singlular'
    assert info.verbs == {'verb1', 'verb2'}  # converted to mutable sets
    assert info.shortnames == {'short1', 'short2'}  # converted to mutable sets
    assert info.categories == {'cat1', 'cat2'}  # converted to mutable sets
    assert info.subresources == {'sub1', 'sub2'}  # converted to mutable sets


def test_resource_info_repr_empty() -> None:
    info = ResourceInfo()
    r = repr(info)
    assert r == "ResourceInfo()"


def test_resource_info_repr_filled() -> None:
    info = ResourceInfo(kind='Kind', categories={'cat1'})
    r = repr(info)
    assert r == "ResourceInfo(kind='Kind', categories={'cat1'})"


def test_resources_properties_empty() -> None:
    resources = ResourcesArray()
    assert not resources
    assert len(resources) == 0
    assert list(resources) == []
    assert list(resources.keys()) == []
    assert list(resources.values()) == []
    assert list(resources.items()) == []


def test_resources_properties_filled() -> None:
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    resources = ResourcesArray()
    resources[res] = ResourceInfo(singular='Sample')
    assert resources
    assert len(resources) == 1
    assert list(resources) == [res]
    assert list(resources.keys()) == [res]
    assert list(resources.values()) == [ResourceInfo(singular='Sample')]
    assert list(resources.items()) == [(res, ResourceInfo(singular='Sample'))]


def test_resources_creation_with_arguments() -> None:
    resources = ResourcesArray({
        'v1/pods': ResourceInfo(kind='Pod'),
        resource('kopf.dev', 'v1', 'kopfexamples'): ResourceInfo(kind='KopfExample'),
    })
    assert len(resources) == 2
    assert set(resources) == {resource('', 'v1', 'pods'), resource('kopf.dev', 'v1', 'kopfexamples')}
    assert resources['v1/pods'] == ResourceInfo(kind='Pod')
    assert resources['kopf.dev/v1/kopfexamples'] == ResourceInfo(kind='KopfExample')


def test_resources_creation_from_dicts() -> None:
    resources = ResourcesArray({
        'v1/pods': {'kind': 'Pod'},
        resource('kopf.dev', 'v1', 'kopfexamples'): {'kind': 'KopfExample'},
    })
    assert len(resources) == 2
    assert set(resources) == {resource('', 'v1', 'pods'), resource('kopf.dev', 'v1', 'kopfexamples')}
    assert resources['v1/pods'] == ResourceInfo(kind='Pod')
    assert resources['kopf.dev/v1/kopfexamples'] == ResourceInfo(kind='KopfExample')


def test_resources_creation_from_dict_with_wrong_type() -> None:
    with pytest.raises(TypeError, match="Unsupported resource value: 123"):
        ResourcesArray({'v1/pods': 123})


def test_resources_repr_empty() -> None:
    resources = ResourcesArray()
    r = repr(resources)
    assert r == 'ResourcesArray()'


def test_resources_repr_filled() -> None:
    resources = ResourcesArray()
    resources['v1/pods'] = ResourceInfo(singular='Pod')
    r = repr(resources)
    assert r == "ResourcesArray({resource(group='', version='v1', plural='pods'): ResourceInfo(singular='Pod')})"


def test_resources_containing_by_resource() -> None:
    resources = ResourcesArray({resource('v1/pods'): ResourceInfo(kind='Pod')})
    assert resource('v1/pods') in resources
    assert resource('v1/unexistent') not in resources


def test_resources_containing_by_string() -> None:
    resources = ResourcesArray({resource('v1/pods'): ResourceInfo(kind='Pod')})
    assert 'v1/pods' in resources
    assert 'v1/unexistent' not in resources


def test_resources_getting_by_resource() -> None:
    resources = ResourcesArray({resource('v1/pods'): ResourceInfo(kind='Pod')})
    assert resources[resource('v1/pods')] == ResourceInfo(kind='Pod')
    assert resources[resource('v1/unexistent')] == ResourceInfo()  # auto-created


def test_resources_getting_by_string() -> None:
    resources = ResourcesArray({resource('v1/pods'): ResourceInfo(kind='Pod')})
    assert resources['v1/pods'] == ResourceInfo(kind='Pod')
    assert resources['v1/unexistent'] == ResourceInfo()  # auto-created


def test_resources_getting_by_wrong_key() -> None:
    resources = ResourcesArray()
    with pytest.raises(TypeError, match="Unsupported resource key: 123"):
        resources[123]


def test_resources_setting_by_resource() -> None:
    resources = ResourcesArray()
    resources[resource('v1/pods')] = ResourceInfo(kind='Pod')
    assert list(resources.items()) == [(resource('v1/pods'), ResourceInfo(kind='Pod'))]


def test_resources_setting_by_string() -> None:
    resources = ResourcesArray()
    resources['v1/pods'] = ResourceInfo(kind='Pod')
    assert list(resources.items()) == [(resource('v1/pods'), ResourceInfo(kind='Pod'))]


def test_resources_setting_by_wrong_key() -> None:
    resources = ResourcesArray()
    with pytest.raises(TypeError, match="Unsupported resource key: 123"):
        resources[123] = ResourceInfo()


def test_resources_setting_from_dict() -> None:
    resources = ResourcesArray()
    resources['v1/pods'] = {'kind': 'Pod'}
    assert list(resources.items()) == [(resource('v1/pods'), ResourceInfo(kind='Pod'))]


def test_resources_setting_from_dict_with_wrong_type() -> None:
    resources = ResourcesArray()
    with pytest.raises(TypeError, match="Unsupported resource value: 123"):
        resources['v1/pods'] = 123


def test_resources_deleting_by_resource() -> None:
    resources = ResourcesArray()
    resources['v1/pods'] = ResourceInfo()
    resources['kopf.dev/v1/kopfexamples'] = ResourceInfo()
    del resources[resource('v1/pods')]
    assert list(resources) == [resource('kopf.dev/v1/kopfexamples')]
    with pytest.raises(KeyError):
        del resources[resource('v1/unexistent')]


def test_resources_deleting_by_string() -> None:
    resources = ResourcesArray()
    resources['v1/pods'] = ResourceInfo()
    resources['kopf.dev/v1/kopfexamples'] = ResourceInfo()
    del resources['v1/pods']
    assert list(resources) == [resource('kopf.dev/v1/kopfexamples')]
    with pytest.raises(KeyError):
        del resources['v1/unexistent']


def test_resources_deleting_by_wrong_key() -> None:
    resources = ResourcesArray()
    with pytest.raises(TypeError, match="Unsupported resource key: 123"):
        del resources[123]


def test_resources_clearing() -> None:
    resources = ResourcesArray({'v1/pods': ResourceInfo(singular='Pod')})
    assert resources
    assert len(resources) == 1
    resources.clear()
    assert not resources
    assert len(resources) == 0


def test_resources_array_is_slotted():
    resources = ResourcesArray()
    with pytest.raises(AttributeError):
        resources.xyz = 123


# Not the functionality (tested above), but just the attribute itself.
@pytest.mark.kmock(cls=KubernetesScaffold)
def test_resources_property_is_accessible(kmock: KubernetesScaffold):
    res = resource('kopf.dev', 'v1', 'kopfexamples')
    kmock.resources[res].kind = 'KopfExample'
    assert isinstance(kmock.resources, ResourcesArray)
    assert kmock.resources[res].kind == 'KopfExample'


@pytest.mark.kmock(cls=KubernetesScaffold)
def test_resources_property_is_readonly(kmock: KubernetesScaffold):
    with pytest.raises(AttributeError):
        kmock.resources = ResourcesArray()
