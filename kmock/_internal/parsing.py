import urllib.parse
from collections.abc import Mapping
from typing import Any

import attrs
from typing_extensions import Self

from kmock._internal import enums, resources


@attrs.frozen
class ParsedHTTP:
    """
    Try to parse a string that looks ike a typical HTTP request.

    E.g.: `get /path?q=query`.
    """
    # Reminder: None means it was not parsed.
    # TODO: = Ellipsis??? or keep it as None for "not parsed"?
    method: enums.method | None
    path: str | None
    params: dict[str, str] | None

    @classmethod
    def parse(cls, s: str) -> Self | None:
        maybe_method, *parts = s.split(maxsplit=1)
        method: enums.method | None = enums.method(maybe_method)
        method = method if method in set(enums.method) else None  # ignore unknown methods!
        s = s if method is None else parts[0] if parts else ''

        # Skip the k8s-like case: "delete pods", but catch as http in "delete /pods".
        parsed = urllib.parse.urlparse(s.strip())
        if parsed.path and not parsed.path.startswith('/'):
            return None

        # No extra checks: it is impossible to make these three to be None in tests or in reality.
        # For this, the first word must be a non-verb, but if so, the whole string goes back to "s",
        # and so it returns None because the path (or "s") does not start with "/".
        # And if the verb starts with "/", it becomes a path, so it is not None either.
        # TODO: None=>ANY
        path = parsed.path or None
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True) or None
        params = dict(query) if query else None
        return cls(method, path, params)


@attrs.frozen
class ParsedK8s:
    # Reminder: None means it was not parsed.
    method: enums.method | None
    action: enums.action | None
    resource: resources.resource | None

    @classmethod
    def parse(cls, s: str) -> Self | None:
        maybe_verb, *parts = s.split(maxsplit=1)
        method: enums.method | None = enums.method(maybe_verb)
        try:
            action = enums.action(maybe_verb)
        except ValueError:
            action = None
        method = method if method in set(enums.method) else None  # ignore unknown methods!
        action = action if action in set(enums.action) else None  # ignore unknown actions!
        s = s if method is None and action is None else parts[0] if parts else ''

        # No extra checks: it is impossible to make these two to be None in tests or in reality.
        # If the first word is not a known action and the action becomes None, then that word
        # goes to the resource parser and becomes the plural name of the resource (never None).
        resource: resources.resource | None = resources.resource(s)
        resource = None if resource is None or (resource.group is None and resource.version is None and resource.plural is None) else resource
        return cls(method, action, resource)


@attrs.frozen
class ParsedPath:
    group: str | None = None
    version: str | None = None
    plural: str | None = None
    namespace: str | None = None
    name: str | None = None
    subresource: str | None = None


def parse_path(path: str) -> ParsedPath:
    parts: list[str | None] = []
    parts += list(path.strip('/').split('/'))

    if len(parts) >= 2 and parts[0] == 'apis':
        _, group, version, *parts = parts + [None]
    elif len(parts) >= 2 and parts[0] == 'api':
        group = ''
        _, version, *parts = parts + [None]
    else:
        group = version = None
        parts += [None]
    parts = parts[:-1]  # if the filler was added but not used for versions

    if group is not None:  # is it k8s-related at all?
        if parts and parts[0] == 'namespaces':
            namespace, *parts = parts[1:]
        else:
            namespace = None
        plural, *parts = parts if parts else [None]
        name, *parts = parts if parts else [None]
        subresource = '/'.join([s for s in parts if s]) or None
    else:
        plural = namespace = name = subresource = None
    return ParsedPath(group, version, plural, namespace, name, subresource)


def guess_k8s(k8s: ParsedPath, method: enums.method, query: dict[str, str]) -> enums.action | None:
    if k8s.group is None:  # non-k8s requests have no k8s action by definition
        return None

    action: enums.action | None
    if method == enums.method.GET and query.get('watch') == 'true':
        action = enums.action.WATCH  # both for lists & named resources
    elif k8s.name is None:
        action = (
            enums.action.LIST if method == enums.method.GET else
            enums.action.CREATE if method == enums.method.POST else
            None  # not guessed, but continuing (not an error)
        )
    else:
        action = (
            enums.action.FETCH if method == enums.method.GET else
            enums.action.UPDATE if method == enums.method.PATCH else
            enums.action.DELETE if method == enums.method.DELETE else
            None  # not guessed, but continuing (not an error)
        )
    return action


def are_all_known_headers(arg: Mapping[str, Any]) -> bool:
    known_headers = {key.lower() for key in KNOWN_HEADERS}
    return bool(arg) and all(key.lower().startswith('x-') or key.lower() in known_headers for key in arg)


# Only those that are distinguished headers and rarely (if ever) can be regular JSON dict keys.
# As a rule of thumb, multi-word headers are fine; if single-word, then only verbs, not nouns.
# Many more can be found at https://en.wikipedia.org/wiki/List_of_HTTP_header_fields
KNOWN_HEADERS = {
    'Accept',
    'Accept-CH',
    'Accept-Charset',
    'Accept-Datetime',
    'Accept-Encoding',
    'Accept-Language',
    'Accept-Patch',
    'Accept-Ranges',
    'Authorization',  # as an exception, the very common one
    'Cache-Control',
    'Content-Disposition',
    'Content-Encoding',
    'Content-Language',
    'Content-Length',
    'Content-Location',
    'Content-MD5',
    'Content-Range',
    'Content-Security-Policy',
    'Content-Transfer-Encoding',
    'Content-Type',
    'ETag',
    'Expires',
    'If-Match',
    'If-Modified-Since',
    'If-None-Match',
    'If-Range',
    'If-Unmodified-Since',
    'Last-Modified',
    'Location',  # as an exception, the very common one
    'Proxy-Authenticate',
    'Proxy-Authorization',
    'Proxy-Connection',
    'Refresh',
    'Retry-After',
    'Set-Cookie',
    'Transfer-Encoding',
    'User-Agent',
    'WWW-Authenticate',
}
