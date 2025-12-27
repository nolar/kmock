# Configuration file for the Sphinx documentation builder.
# http://www.sphinx-doc.org/en/master/config
import os
import types

import docutils.nodes

###############################################################################
# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))

project = 'kmock'
copyright = '2023-2025 Sergey Vasilyev'
author = 'Sergey Vasilyev'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.todo',
    'sphinx.ext.extlinks',
    'sphinx.ext.linkcode',
    'sphinx.ext.intersphinx',
    'sphinx_llm.txt',
]

templates_path = []
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
html_static_path = []
html_theme = 'sphinx_rtd_theme'

default_role = 'py:obj'

autodoc_typehints = 'description'
autodoc_member_order = 'bysource'

todo_include_todos = False
todo_emit_warnings = True

extlinks = {
    'issue': ('https://github.com/nolar/kmock/issues/%s', 'issue '),
}

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'mypy': ('https://mypy.readthedocs.io/en/latest/', None),
    'kopf': ('https://kopf.readthedocs.io/en/latest/', None),
    'aiohttp': ('https://docs.aiohttp.org/en/stable/', None),
}


def linkcode_resolve(domain, info):
    if domain != 'py':
        return None
    if not info['module']:
        return None
    filename = info['module'].replace('.', '/')
    return "https://github.com/nolar/kmock/blob/main/%s.py" % filename


###############################################################################
# Ensure the apidoc is always built as part of the build process,
# especially in ReadTheDocs build environment.
# See: https://github.com/rtfd/readthedocs.org/issues/1139
###############################################################################

def run_apidoc(_):
    ignore_paths = [
    ]

    docs_path = os.path.relpath(os.path.dirname(__file__))
    root_path = os.path.relpath(os.path.dirname(os.path.dirname(__file__)))

    argv = [
        '--force',
        '--no-toc',
        '--separate',
        '--module-first',
        '--output-dir', os.path.join(docs_path, 'packages'),
        os.path.join(root_path, 'kmock'),
    ] + ignore_paths

    from sphinx.ext import apidoc
    apidoc.main(argv)


# KMock exposes most public classes/types on the `kmock` fixture itself (RawHandler & descendants),
# so that there is no need to use `from kmock import blah` syntax and the old `kmock.blah` remains.
# But we do not want these re-exposed members of the `kmock` fixtures to be documented as public
# members of the handlers, since they are already documented as the members of the `kmock` module.
# (Classes are more precise due to their source module; type aliases/generics are excluded blindly.)
def autodoc_skip_member(app, what, name, obj, skip, options):
    from types import GenericAlias
    from typing import Union

    # Rare cases like clusterwide(…), namespace(…), etc, which return Criteria() instances.
    # Alternative: remake them to classes with the overridden __new__(), which returns K8sCriteria.
    if what == 'class' and isinstance(obj, types.FunctionType):
        if not name.startswith('_') and '.' not in obj.__qualname__:
            return True
    if what == 'class' and isinstance(obj, type) and obj.__module__.startswith('kmock.'):
        return True
    if what == 'class' and isinstance(obj, GenericAlias | Union):
        return True


def setup(app):
    app.add_crossref_type('kwarg', 'kwarg', "pair: %s; kwarg", docutils.nodes.literal)
    app.connect('builder-inited', run_apidoc)
    app.connect('autodoc-skip-member', autodoc_skip_member)
