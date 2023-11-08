import pytest

from kmock._internal.resources import resource


def test_kwargs() -> None:
    result = resource(group='group1', version='version1', plural='name1')
    assert result.group == 'group1'
    assert result.version == 'version1'
    assert result.plural == 'name1'


def test_no_args() -> None:
    result = resource()
    assert result.group is None
    assert result.version is None
    assert result.plural is None


def test_one_arg_name_alone() -> None:
    result = resource('name1')
    assert result.group is None
    assert result.version is None
    assert result.plural == 'name1'


@pytest.mark.parametrize('group', ['group1', 'group1.example.com', 'v1nonconventional'])
def test_one_arg_with_name_and_group(group: str) -> None:
    result = resource(f'name1.{group}')
    assert result.group == group
    assert result.version is None
    assert result.plural == 'name1'


@pytest.mark.parametrize('version', ['v1', 'v99', 'v99beta99', 'v99alpha99'])
@pytest.mark.parametrize('group', ['group1', 'group1.example.com', 'v1nonconventional'])
def test_one_arg_with_name_and_groupversion(version: str, group: str) -> None:
    result = resource(f'name1.{version}.{group}')
    assert result.group == group
    assert result.version == version
    assert result.plural == 'name1'


@pytest.mark.parametrize('group', ['group1', 'group1.example.com', 'v1nonconventional'])
def test_two_args_with_name_and_group(group: str) -> None:
    result = resource(f'{group}', 'name1')
    assert result.group == group
    assert result.version is None
    assert result.plural == 'name1'


@pytest.mark.parametrize('version', ['v1', 'v99', 'v99beta99', 'v99alpha99'])
@pytest.mark.parametrize('group', ['group1', 'group1.example.com', 'v1nonconventional'])
def test_two_args_with_name_and_groupversion(version: str, group: str) -> None:
    result = resource(f'{group}/{version}', 'name1')
    assert result.group == group
    assert result.version == version
    assert result.plural == 'name1'


def test_two_args_and_corev1() -> None:
    result = resource('v1', 'name1')
    assert result.group == ''
    assert result.version == 'v1'
    assert result.plural == 'name1'


@pytest.mark.parametrize('version', ['v1', 'v99', 'v99beta99', 'v99alpha99'])
@pytest.mark.parametrize('group', ['group1', 'group1.example.com', 'v1nonconventional'])
def test_three_args(group: str, version: str) -> None:
    result = resource(group, version, 'name1')
    assert result.group == group
    assert result.version == version
    assert result.plural == 'name1'


@pytest.mark.parametrize('arg1, arg2, arg3, kwarg', [
    ('', 'v1', 'pods', 'group'),
    ('', 'v1', None, 'group'),
    ('group', 'v1', 'items', 'group'),
    ('group', 'v1', None, 'group'),
    ('group', 'items', None, 'group'),
    ('v1', 'pods', None, 'group'),
    ('v1', None, None, 'group'),

    ('group/v1/items', None, None, 'group'),
    ('items.v1.group', None, None, 'group'),
    ('group/v1', 'items', None, 'group'),
    ('v1.group', 'items', None, 'group'),
    ('group/v1', None, None, 'group'),
    ('v1.group', None, None, 'group'),

    ('group/items', None, None, 'group'),
    ('items.group', None, None, 'group'),
    ('pods.v1', None, None, 'group'),
    ('v1/pods', None, None, 'group'),
])
def test_conflicting_group(arg1: str, arg2: str | None, arg3: str | None, kwarg: str) -> None:
    with pytest.raises(TypeError, match=r"Ambiguous resource"):
        resource(arg1, arg2, arg3, group=kwarg)


@pytest.mark.parametrize('arg1, arg2, arg3, kwarg', [
    ('group', 'v1', 'pods', 'v1'),
    ('v1', None, None, 'v1'),
    ('pods.v1', None, None, 'v1'),
    ('v1/pods', None, None, 'v1'),
    ('group/v1', None, None, 'v1'),
    ('group/v1/items', None, None, 'v1'),
    ('items.v1.group', None, None, 'v1'),
])
def test_conflicting_version(arg1: str, arg2: str | None, arg3: str | None, kwarg: str) -> None:
    with pytest.raises(TypeError, match=r"Ambiguous resource"):
        resource(arg1, arg2, arg3, version='conflicting')


@pytest.mark.parametrize('arg1, arg2, arg3, kwarg', [
    ('group', 'v1', 'pods', 'pods'),
    ('pods', None, None, 'pods'),
    ('pods.v1', None, None, 'pods'),
    ('v1/pods', None, None, 'pods'),
    ('group/v1/items', None, None, 'pods'),
    ('items.v1.group', None, None, 'pods'),
])
def test_conflicting_plural(arg1: str, arg2: str | None, arg3: str | None, kwarg: str) -> None:
    with pytest.raises(TypeError, match=r"Ambiguous resource"):
        r = resource(arg1, arg2, arg3, plural=kwarg)
        print(r)
