import pytest

pytest_plugins = ['pytester']


@pytest.fixture(autouse=True)
def _auto_loop_scope(pytester: pytest.Pytester):
    pytester.makeini("""
        [pytest]
        asyncio_mode = auto
        asyncio_default_fixture_loop_scope = function
    """)


def test_fixture(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("""
        import pytest

        @pytest.mark.asyncio
        async def test_sample(kmock) -> None:
            root = kmock['/'] << 444 << b'yes, hello!'
            resp = await kmock.get('/?q=query', data=b'{"hello": "world"}')
            text = await resp.read()

            assert resp.status == 444
            assert text == b'yes, hello!'
            assert len(root) == 1
            assert len(kmock) == 1
            assert kmock[0].data == {'hello': 'world'}
            assert kmock[0].text == '{"hello": "world"}'
            assert kmock[0].body == b'{"hello": "world"}'
    """)
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_factory(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("""
        import pytest
        import kmock

        @pytest.mark.asyncio
        @pytest.mark.kmock(cls=kmock.RawHandler)
        async def test_sample(kmock) -> None:
            assert kmock.__class__.__name__ == 'RawHandler'
    """)
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_markers(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("""
        import pytest

        @pytest.mark.asyncio
        @pytest.mark.kmock(strict=False)
        async def test_sample_1(kmock) -> None:
            assert kmock.strict == False

        @pytest.mark.asyncio
        @pytest.mark.kmock(strict=True)
        async def test_sample_2(kmock) -> None:
            assert kmock.strict == True
    """)
    result = pytester.runpytest()
    result.assert_outcomes(passed=2)


def test_markers_merge(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("""
        import pytest

        pytestmark = pytest.mark.kmock(limit=1)

        @pytest.mark.asyncio
        async def test_with_external_marks(kmock) -> None:
            assert kmock.limit == 1
            assert kmock.strict == False  # default

        @pytest.mark.asyncio
        @pytest.mark.kmock(limit=100, strict=True)
        @pytest.mark.kmock(limit=200)
        async def test_with_own_marks(kmock) -> None:
            assert kmock.limit == 200
            assert kmock.strict == True
    """)
    result = pytester.runpytest()
    result.assert_outcomes(passed=2)


def test_config(pytester: pytest.Pytester) -> None:
    pytester.makeini("""
        [pytest]
        asyncio_mode = auto
        asyncio_default_fixture_loop_scope = function
        kmock_cls = kmock.RawHandler
        kmock_limit = 1
        kmock_strict = True
    """)
    pytester.makepyfile("""
        import pytest

        @pytest.mark.asyncio
        async def test_options(kmock) -> None:
            assert kmock.__class__.__name__ == 'RawHandler'
            assert kmock.limit == 1
            assert kmock.strict == True
    """)
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_hostname_interception(pytester: pytest.Pytester) -> None:
    # Mind that kmock's client has the base URL pointing to its own server,
    # so we need our own client with no base URL to access an external host.
    # See more captive endpoints: https://en.wikipedia.org/wiki/Captive_portal
    pytester.makepyfile("""
        import aiohttp
        import pytest

        @pytest.mark.asyncio
        @pytest.mark.kmock(hostnames=['google.com'])
        async def test_intercepted_host(kmock) -> None:
            kmock['/'] << b'hello' << 444

            async with aiohttp.ClientSession() as client:
                resp = await client.get('http://google.com/', data=b'hey!')
                text = await resp.read()

            assert resp.status == 444
            assert text == b'hello'
            assert len(kmock) == 1
            assert kmock[0].body == b'hey!'
            assert kmock[0].url.scheme == 'http'
            assert kmock[0].url.host == 'google.com'

        @pytest.mark.asyncio
        @pytest.mark.kmock(hostnames=['google.com'])
        async def test_outside_of_interception(kmock) -> None:
            kmock['/'] << b'hello' << 444

            async with aiohttp.ClientSession() as client:
                resp = await client.get('http://clients3.google.com/generate_204')
                text = await resp.read()

            assert resp.status == 204
            assert text == b''
            assert len(kmock) == 0
    """)
    result = pytester.runpytest()
    result.assert_outcomes(passed=2)


def test_wrong_cls_name(pytester: pytest.Pytester) -> None:
    pytester.makeini("""
        [pytest]
        kmock_cls = WrongClsName
        asyncio_default_fixture_loop_scope = function
    """)
    pytester.makepyfile("""
        async def test_nothing(kmock) -> None:
            pass
    """)
    result = pytester.runpytest()
    result.assert_outcomes(passed=0, errors=1)
    result.stdout.re_match_lines([
        ".*ERROR at setup of test_nothing.*",
        ".*UsageError: kmock_cls must look like 'package.class'..*",
    ])


def test_wrong_cls_reference(pytester: pytest.Pytester) -> None:
    pytester.makeini("""
        [pytest]
        kmock_cls = kmock.WrongClsName
        asyncio_default_fixture_loop_scope = function
    """)
    pytester.makepyfile("""
        async def test_nothing(kmock) -> None:
            pass
    """)
    result = pytester.runpytest()
    result.assert_outcomes(passed=0, errors=1)
    result.stdout.re_match_lines([
        ".*ERROR at setup of test_nothing.*",
        ".*UsageError: kmock_cls refers to non-existent class.*",
    ])


def test_aresponses_first(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("""
        async def test_nothing(kmock, aresponses) -> None:
            assert aresponses is not None
    """)
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
