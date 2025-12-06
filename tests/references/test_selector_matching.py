import attrs
import pytest

from kmock._internal.resources import Selectable, resource


@attrs.frozen
class SampleResource(Selectable):
    group: str
    version: str
    plural: str


@pytest.mark.parametrize('group, version', [
    (None, None),
    ('group1', None),
    (None, 'version1'),
    ('group1', 'version1'),
])
def test_when_matches_names(group: str | None, version: str | None) -> None:
    selectable = SampleResource(group='group1', version='version1', plural='plural1')
    pattern = resource(group=group, version=version, plural='plural1')
    matches = pattern.check(selectable)
    assert matches


@pytest.mark.parametrize('group, version', [
    ('group9', None),
    (None, 'version9'),
    ('group1', 'version9'),
    ('group9', 'version1'),
    ('group9', 'version9'),
])
def test_when_groupversion_mismatch_but_names_do_match(group: str | None, version: str | None) -> None:
    selectable = SampleResource(group='group1', version='version1', plural='plural1')
    pattern = resource(group=group, version=version, plural='plural1')
    matches = pattern.check(selectable)
    assert not matches


@pytest.mark.parametrize('group, version', [
    (None, None),
    ('group1', None),
    (None, 'version1'),
    ('group1', 'version1'),
])
def test_when_groupversion_do_match_but_names_mismatch(group: str | None, version: str | None) -> None:
    selectable = SampleResource(group='group1', version='version1', plural='plural1')
    pattern = resource(group=group, version=version, plural='different')
    matches = pattern.check(selectable)
    assert not matches


def test_catchall_resource() -> None:
    selectable = SampleResource(group='group1', version='version1', plural='plural1')
    pattern = resource()
    matches = pattern.check(selectable)
    assert matches
