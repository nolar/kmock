import re
from typing import Any

import pytest

from kmock import body, cookies, data, headers, params, text


@pytest.mark.parametrize('arg', ['item', b'item', 123])
def test_headers_unsupported(arg: Any) -> None:
    with pytest.raises(ValueError, match=r"Unsupported argument for headers:"):
        headers(arg)


@pytest.mark.parametrize('arg', [
    pytest.param(None, id='none'),
    pytest.param('', id='empty-str'),
    pytest.param(b'', id='empty-bytes'),
    pytest.param('\n \n\n ', id='spaced-str'),
    pytest.param(b'\n \n\n ', id='spaced-bytes'),
    pytest.param({}, id='dict'),
    pytest.param([], id='pairs'),
])
def test_headers_from_empty(arg: Any) -> None:
    result = headers(arg)
    assert result == {}


@pytest.mark.parametrize('arg1, arg2', [
    pytest.param('\n\nkey1: val1\nkey2: val2\n\n', b'', id='str'),
    pytest.param(b'\n\nkey1: val1\nkey2: val2\n\n', '', id='bytes'),
    pytest.param({'key1': 'val1', 'key2': 'val2'}, None, id='dict-none'),
    pytest.param([('key1', 'val1'), ('key2', 'val2')], None, id='pairs-none'),
    pytest.param(None, {'key1': 'val1', 'key2': 'val2'}, id='none-dict'),
    pytest.param(None, [('key1', 'val1'), ('key2', 'val2')], id='none-pairs'),
])
def test_headers_from_args(arg1: Any, arg2: Any) -> None:
    result = headers(arg1, arg2)
    assert result == {'key1': 'val1', 'key2': 'val2'}


def test_headers_from_kwargs() -> None:
    result = headers(key1='val1', key2='val2')
    assert result == {'key1': 'val1', 'key2': 'val2'}


def test_headers_overriden_kwargs() -> None:
    result = headers({'key1': 'val1'}, key1='kwarg')
    assert result == {'key1': 'kwarg'}


def test_headers_intermixed() -> None:
    result = headers({'key1': 'val1'}, 'key2: val2', key3='val3')
    assert result == {'key1': 'val1', 'key2': 'val2', 'key3': 'val3'}


@pytest.mark.parametrize('arg', ['item', b'item', 123, 'key=val', b'key=val'])
def test_cookies_unsupported(arg: Any) -> None:
    with pytest.raises(ValueError, match=r"Unsupported argument for cookies:"):
        cookies(arg)


@pytest.mark.parametrize('arg', [
    pytest.param(None, id='none'),
    pytest.param({}, id='dict'),
    pytest.param([], id='pairs'),
])
def test_cookies_from_empty(arg: Any) -> None:
    result = cookies(arg)
    assert result == {}


@pytest.mark.parametrize('arg1, arg2', [
    pytest.param({'key1': 'val1', 'key2': 'val2'}, None, id='dict-none'),
    pytest.param([('key1', 'val1'), ('key2', 'val2')], None, id='pairs-none'),
    pytest.param(None, {'key1': 'val1', 'key2': 'val2'}, id='none-dict'),
    pytest.param(None, [('key1', 'val1'), ('key2', 'val2')], id='none-pairs'),
])
def test_cookies_from_args(arg1: Any, arg2: Any) -> None:
    result = cookies(arg1, arg2)
    assert result == {'key1': 'val1', 'key2': 'val2'}


def test_cookies_from_kwargs() -> None:
    result = cookies(key1='val1', key2='val2')
    assert result == {'key1': 'val1', 'key2': 'val2'}


def test_cookies_overriden_kwargs() -> None:
    result = cookies({'key1': 'val1'}, key1='kwarg')
    assert result == {'key1': 'kwarg'}


def test_cookies_intermixed() -> None:
    result = cookies({'key1': 'val1'}, [('key2', 'val2')], key3='val3')
    assert result == {'key1': 'val1', 'key2': 'val2', 'key3': 'val3'}


@pytest.mark.parametrize('args', [
    pytest.param([123], id='int'),
    pytest.param([[()]], id='non-dict-like-list'),
])
def test_params_unsupported(args: Any) -> None:
    with pytest.raises(ValueError, match=r"Unsupported argument for params:"):
        params(*args)


@pytest.mark.parametrize('arg', [
    pytest.param(None, id='none'),
    pytest.param('', id='empty-str'),
    pytest.param(b'', id='empty-bytes'),
    pytest.param('?', id='q-str'),
    pytest.param(b'?', id='q-bytes'),
    pytest.param({}, id='dict'),
    pytest.param([], id='pairs'),
])
def test_params_from_empty(arg: str) -> None:
    result = params(arg)
    assert result == {}


@pytest.mark.parametrize('arg1, arg2', [
    pytest.param('key1=val1&key2=val2', b'', id='str-bytes'),
    pytest.param(b'key1=val1&key2=val2', '', id='bytes-str'),
    pytest.param('?key1=val1&key2=val2', b'?', id='qstr-qbytes'),
    pytest.param(b'?key1=val1&key2=val2', '?', id='qbytes-qstr'),
    pytest.param({'key1': 'val1', 'key2': 'val2'}, None, id='dict-none'),
    pytest.param([('key1', 'val1'), ('key2', 'val2')], None, id='pairs-none'),
    pytest.param(None, {'key1': 'val1', 'key2': 'val2'}, id='none-dict'),
    pytest.param(None, [('key1', 'val1'), ('key2', 'val2')], id='none-pairs'),
])
def test_params_from_args(arg1: Any, arg2: Any) -> None:
    result = params(arg1, arg2)
    assert result == {'key1': 'val1', 'key2': 'val2'}


def test_params_from_kwargs() -> None:
    result = params(key1='val1', key2='val2')
    assert result == {'key1': 'val1', 'key2': 'val2'}


def test_params_overriden_kwargs() -> None:
    result = params({'key1': 'val1'}, key1='kwarg')
    assert result == {'key1': 'kwarg'}


def test_params_intermixed() -> None:
    result = params({'key1': 'val1'}, '?key2=val2', key3='val3')
    assert result == {'key1': 'val1', 'key2': 'val2', 'key3': 'val3'}


def test_params_with_simple_presence() -> None:
    result = params('?key1=&key2')
    assert result == {'key1': '', 'key2': None}


def test_params_repr() -> None:
    result = params(key1='val1', key2='val2')
    assert repr(result) == "params({'key1': 'val1', 'key2': 'val2'})"


@pytest.mark.parametrize('val', ['key=val', 'key: val', {'key': 'val'}, [('key', 'val')]])
def test_data_remains_unparsed(val: Any) -> None:
    result = data(val)
    assert result.data == val


def test_data_from_kwargs() -> None:
    result = data(key1='val1', key2='val2')
    assert result.data == {'key1': 'val1', 'key2': 'val2'}


def test_data_dicts_merged() -> None:
    result = data({'a': 'b', 'x': 'y'}, {'c': 'd', 'x': 'z'}, None)
    assert result.data == {'a': 'b', 'c': 'd', 'x': 'z'}


def test_data_overriden_kwargs() -> None:
    result = data({'key1': 'val1'}, key1='kwarg')
    assert result.data == {'key1': 'kwarg'}


def test_data_unmergeable_args() -> None:
    with pytest.raises(ValueError, match=r"Unmergeable combination of multiple arguments"):
        data({'key1': 'val1'}, 'hello')


@pytest.mark.parametrize('val', ['key1=val1', [('key1', 'val1')]], ids=['str', 'pairs'])
def test_data_unsupported_kwargs(val: Any) -> None:
    with pytest.raises(ValueError, match=r"only alone or for a mapping"):
        data(val, key1='kwarg')


@pytest.mark.parametrize('expected, args', [
    pytest.param(b'', (), id='no-args'),
    pytest.param(b'', (None,), id='none-arg'),
    pytest.param(b'', (None, None), id='none-args'),
    pytest.param(b'helloworld', ('helloworld', None), id='str-none'),
    pytest.param(b'helloworld', (b'helloworld', None), id='bytes-none'),
    pytest.param(b'helloworld', (None, 'helloworld'), id='none-str'),
    pytest.param(b'helloworld', (None, b'helloworld'), id='none-bytes'),
    pytest.param(b'helloworld', ('hello', b'world'), id='str-bytes'),
    pytest.param(b'helloworld', (b'hello', 'world'), id='bytes-str'),
    pytest.param(re.compile(b'helloworld'), (re.compile(b'helloworld'),), id='regexp'),
])
def test_body_creation(args: Any, expected: bytes) -> None:
    result = body(*args)
    assert result.body == expected


@pytest.mark.parametrize('arg', [123, 123.456, True, False, object()])
def test_body_unsupported_arg(arg: Any) -> None:
    with pytest.raises(ValueError, match=r"Body can be either"):
        body(arg)


@pytest.mark.parametrize('expected, args', [
    pytest.param('', (), id='no-args'),
    pytest.param('', (None,), id='none-arg'),
    pytest.param('', (None, None), id='none-args'),
    pytest.param('helloworld', ('helloworld', None), id='str-none'),
    pytest.param('helloworld', (b'helloworld', None), id='bytes-none'),
    pytest.param('helloworld', (None, 'helloworld'), id='none-str'),
    pytest.param('helloworld', (None, b'helloworld'), id='none-bytes'),
    pytest.param('helloworld', ('hello', b'world'), id='str-bytes'),
    pytest.param('helloworld', (b'hello', 'world'), id='bytes-str'),
    pytest.param(re.compile('helloworld'), (re.compile('helloworld'),), id='regexp'),
])
def test_text_creation(args: Any, expected: str) -> None:
    result = text(*args)
    assert result.text == expected


@pytest.mark.parametrize('arg', [123, 123.456, True, False, object()])
def test_text_unsupported_arg(arg: Any) -> None:
    with pytest.raises(ValueError, match=r"Text can be either"):
        text(arg)
