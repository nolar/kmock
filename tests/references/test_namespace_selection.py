# TODO: restore namespace globs?
# import re
#
# from kmock._internal.resources import select_specific_namespaces
#
#
# def test_empty_pattern_list() -> None:
#     names = select_specific_namespaces([])
#     assert not names
#
#
# def test_included_empty_string() -> None:
#     names = select_specific_namespaces([''])
#     assert names == {''}
#
#
# def test_included_exact_strings() -> None:
#     names = select_specific_namespaces(['ns2', 'ns1'])
#     assert names == {'ns1', 'ns2'}
#
#
# def test_excluded_multipatterns() -> None:
#     names = select_specific_namespaces(['ns1,ns2'])
#     assert not names
#
#
# def test_excluded_globs() -> None:
#     names = select_specific_namespaces(['n*s', 'n?s'])
#     assert not names
#
#
# def test_excluded_regexps() -> None:
#     names = select_specific_namespaces([re.compile(r'ns1')])
#     assert not names
