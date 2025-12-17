import pytest

from kmock import Criteria, HTTPCriteria, K8sCriteria, action, method, resource


def test_http_criteria_creation() -> None:
    criteria = HTTPCriteria(
        method=method.POST,
        path='/path',
        params={'q': 'query'},
        cookies={'session': 'sid'},
        headers={'X-Custom': 'blah'},
        text='text',
        body=b'body',
        data={'key': 'val'},
    )
    assert criteria.method == method.POST
    assert criteria.path == '/path'
    assert criteria.params == {'q': 'query'}
    assert criteria.cookies == {'session': 'sid'}
    assert criteria.headers == {'X-Custom': 'blah'}
    assert criteria.text == 'text'
    assert criteria.body == b'body'
    assert criteria.data == {'key': 'val'}


def test_k8s_criteria_creation() -> None:
    criteria = K8sCriteria(
        action=action.CREATE,
        resource=resource('', 'v1', 'pods'),
        clusterwide=False,
        namespace='ns1',
        name='n1',
        subresource='status',
    )
    assert criteria.action == action.CREATE
    assert criteria.resource == resource('', 'v1', 'pods')
    assert criteria.clusterwide == False
    assert criteria.namespace == 'ns1'
    assert criteria.name == 'n1'
    assert criteria.subresource == 'status'


@pytest.mark.parametrize('cls, kwargs, expected_repr', [
    (HTTPCriteria, dict(), 'HTTPCriteria()'),
    (K8sCriteria, dict(), 'K8sCriteria()'),
    (HTTPCriteria, dict(path='/'), "HTTPCriteria(path='/')"),
    (K8sCriteria, dict(name='n1'), "K8sCriteria(name='n1')"),
])
def test_repr_without_defaults(cls: type[Criteria], kwargs: dict[str, str], expected_repr: str) -> None:
    criteria = cls(**kwargs)
    repr_text = repr(criteria)
    assert repr_text == expected_repr
