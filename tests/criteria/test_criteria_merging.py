import attrs
import pytest

from kmock import HTTPCriteria, K8sCriteria, action, method, resource

RESOURCE1 = resource('', 'v1', 'pods')
RESOURCE2 = resource('', 'v1', 'deployments')
K8S_1 = dict(action=action.FETCH, resource=RESOURCE1, clusterwide=True, namespace='ns1', name='n1', subresource='sub1')
K8S_2 = dict(action=action.WATCH, resource=RESOURCE2, clusterwide=False, namespace='ns2', name='n2', subresource='sub2')
HTTP_1 = dict(method=method.GET, path='/path1', text='hello', body=b'hello', data={'key': 'val'}, headers={'X': 'h1'})
HTTP_2 = dict(method=method.POST, path='/path2', text='world', body=b'world', data={'key': 'alt'}, headers={'X': 'h2'})
# Cookies, params, headers, and even data dicts are all the same, so we can skip them but one — for brevity.


def test_crosstype_conflict() -> None:
    criteria1 = HTTPCriteria()
    criteria2 = K8sCriteria()
    with pytest.raises(TypeError):
        criteria1 + criteria2
    with pytest.raises(TypeError):
        criteria2 + criteria1


@pytest.mark.parametrize('field1, field2', [(f1, f2) for f1 in HTTP_1 for f2 in HTTP_1 if f1 != f2])
def test_nonoverlapping_fields_in_http(field1: str, field2: str) -> None:
    criteria1 = HTTPCriteria(**{field1: HTTP_1[field1]})
    criteria2 = HTTPCriteria(**{field2: HTTP_1[field2]})
    criteria = criteria1 + criteria2
    assert getattr(criteria, field1) == HTTP_1[field1]
    assert getattr(criteria, field2) == HTTP_1[field2]
    assert all(v is ... for f, v in attrs.asdict(criteria).items() if f not in {field1, field2})


@pytest.mark.parametrize('field1, field2', [(f1, f2) for f1 in K8S_1 for f2 in K8S_1 if f1 != f2])
def test_nonoverlapping_fields_in_k8s(field1: str, field2: str) -> None:
    criteria1 = K8sCriteria(**{field1: K8S_1[field1]})
    criteria2 = K8sCriteria(**{field2: K8S_1[field2]})
    criteria = criteria1 + criteria2
    assert getattr(criteria, field1) == K8S_1[field1]
    assert getattr(criteria, field2) == K8S_1[field2]
    assert all(v is ... for f, v in attrs.asdict(criteria).items() if f not in {field1, field2})


@pytest.mark.parametrize('field', [f for f, v in HTTP_1.items() if not isinstance(v, dict)])
def test_compatible_scalars_in_http(field: str) -> None:
    criteria1 = HTTPCriteria(**{field: HTTP_1[field]})
    criteria2 = HTTPCriteria(**{field: HTTP_1[field]})
    criteria = criteria1 + criteria2
    assert getattr(criteria, field) == HTTP_1[field]
    assert all(value is ... for f, value in attrs.asdict(criteria).items() if f != field)


@pytest.mark.parametrize('field', [f for f, v in K8S_1.items() if not isinstance(v, dict)])
def test_compatible_scalars_in_k8s(field: str) -> None:
    criteria1 = K8sCriteria(**{field: K8S_1[field]})
    criteria2 = K8sCriteria(**{field: K8S_1[field]})
    criteria = criteria1 + criteria2
    assert getattr(criteria, field) == K8S_1[field]
    assert all(value is ... for f, value in attrs.asdict(criteria).items() if f != field)


@pytest.mark.parametrize('field', [f for f, v in HTTP_1.items() if not isinstance(v, dict)])
def test_conflicting_scalars_in_http(field: str) -> None:
    criteria1 = HTTPCriteria(**{field: HTTP_1[field]})
    criteria2 = HTTPCriteria(**{field: HTTP_2[field]})
    with pytest.raises(ValueError, match=r"Ambiguous.*"):
        criteria1 + criteria2


@pytest.mark.parametrize('field', [f for f, v in K8S_1.items() if not isinstance(v, dict)])
def test_conflicting_scalars_in_k8s(field: str) -> None:
    criteria1 = K8sCriteria(**{field: K8S_1[field]})
    criteria2 = K8sCriteria(**{field: K8S_2[field]})
    with pytest.raises(ValueError, match=r"Ambiguous.*"):
        criteria1 + criteria2


# NB: there are no fields of type `dict` in K8sCriteria, only in HTTP.
@pytest.mark.parametrize('field', {'headers', 'cookies', 'params', 'data'})
def test_compatible_dicts_in_http(field: str) -> None:
    criteria1 = HTTPCriteria(**{field: {'key1': 'val1', 'common': 'value'}})
    criteria2 = HTTPCriteria(**{field: {'key2': 'val2', 'common': 'value'}})
    criteria = criteria1 + criteria2
    assert getattr(criteria, field) == {'key1': 'val1', 'key2': 'val2', 'common': 'value'}
    assert all(value is ... for f, value in attrs.asdict(criteria).items() if f != field)


# NB: there are no fields of type `dict` in K8sCriteria, only in HTTP.
@pytest.mark.parametrize('field', {'headers', 'cookies', 'params', 'data'})
def test_conflicting_dicts_in_http(field: str) -> None:
    criteria1 = HTTPCriteria(**{field: {'key1': 'val1'}})
    criteria2 = HTTPCriteria(**{field: {'key1': 'val2'}})
    with pytest.raises(ValueError, match=r"Ambiguous.*"):
        criteria1 + criteria2
