import asyncio
import collections
import datetime
import json
import re
import sys
import traceback
from typing import Any, AsyncIterator

import aiohttp.web
import attrs
from typing_extensions import override

from kmock._internal import aiobus, apps, dsl, enums, filtering, k8s_dicts, k8s_views, rendering, resources


@attrs.frozen
class KubernetesError(Exception):
    """An error with its own K8s-specific payload & status code."""
    status: int = 500
    reason: str | None = None
    message: str | None = None
    details: Any | None = None


@attrs.frozen
class KubernetesNotFoundError(KubernetesError):
    """An error for the HTTP 404 errors for lacking URLs in Kubernetes."""
    status: int = 404
    reason: str = 'Not Found'
    message: str = 'The URL or resource was not found'


@attrs.frozen
class KubernetesEndpointNotFoundError(KubernetesNotFoundError):
    """An error for the HTTP 404 errors for unknown endpoint in Kubernetes."""
    reason: str = 'Endpoint Not Found'
    message: str = (
        "The URL was not found and does not match any known pattern."
        " Declare it as: kmock['/endpoint'] << b'some payload'"
    )


@attrs.frozen
class KubernetesResourceNotFoundError(KubernetesNotFoundError):
    """An error for the HTTP 404 errors for unknown resources in Kubernetes."""
    reason: str = 'Resource Not Found'
    message: str = (
        "The resource is not declared in the Kubernetes server."
        " Declare it either way, e.g.: kmock.resources['group/v1/plural'] = {}"
    )


@attrs.frozen
class KubernetesObjectNotFoundError(KubernetesNotFoundError):
    """An error for the HTTP 404 errors for unknown objects in Kubernetes."""
    reason: str = 'Object Not Found'
    message: str = (
        "The object is not found in the Kubernetes server for a known resource."
        " Add it as: kmock.objects[res, 'ns', 'name'] = {'spec': ...}"
    )


@attrs.frozen
class KubernetesObjectConflictError(KubernetesError):
    """An error for the HTTP 404 errors for unknown objects in Kubernetes."""
    status: int = 409
    reason: str = 'Object Already Exists'
    message: str = (
        "The object already exists in the Kubernetes server and is not deleted."
    )


@attrs.define(kw_only=True)
class KubernetesScaffold(apps.RawHandler):
    """
    A bare structure of the Kubernetes API: errors, API & resource discovery.

    It is stateless! It keeps nothing in memory except for what was fed into it.
    For the stateful API, see :class:`KubernetesEmulator`.
    """

    _resources: k8s_views.ResourcesArray = attrs.field(factory=k8s_views.ResourcesArray, init=False)

    def __attrs_post_init__(self) -> None:
        # NB: Partially duplicates the URL parsing logic, but here we check for
        # the presence or absence of the version, not for its specific value.
        # This cannot be expressed as a catch-all [resource()] selector.
        self.fallback.fallback << KubernetesEndpointNotFoundError
        self.fallback['get', re.compile(r'/apis/[^/]+/[^/]+')] << self._serve_version
        self.fallback['get', re.compile(r'/apis/[^/]+')] << self._serve_group
        self.fallback['get', re.compile(r'/api/[^/]+')] << self._serve_version
        self.fallback['get /version'] << self._serve_server_version
        self.fallback['get /apis'] << self._serve_apis
        self.fallback['get /api'] << self._serve_api
        self.fallback['get /'] << self._serve_root

    @override
    async def _render_error(self, exc: Exception) -> aiohttp.web.StreamResponse:
        # For Kubernetes server, we simulate Kubernetes error in the hope that
        # clients will understand it properly and re-raise internally.
        # https://kubernetes.io/docs/reference/kubernetes-api/common-definitions/status/
        if isinstance(exc, KubernetesError):
            return aiohttp.web.json_response({
                'apiVersion': 'v1',
                'kind': 'Status',
                'metadata': {},
                'code': exc.status,
                'status': 'Failure',
                'reason': exc.reason or type(exc).__name__,
                'message': exc.message or repr(exc),
                'details': exc.details or {'traceback': traceback.format_exc()},
            }, status=exc.status)
        else:
            return aiohttp.web.json_response({
                'apiVersion': 'v1',
                'kind': 'Status',
                'metadata': {},
                'code': 500,
                'status': 'Failure',
                'reason': type(exc).__name__,
                'message': repr(exc),
                'details': {'traceback': traceback.format_exc()},
            }, status=500)

    @override
    async def _stream_error(self, exc: Exception, raw_response: aiohttp.web.StreamResponse) -> None:
        error = json.dumps({
            'type': 'ERROR',
            'object': {
                'apiVersion': 'v1',
                'kind': 'Status',
                'metadata': {},
                'code': 500,
                'status': 'Failure',
                'reason': type(exc).__name__,
                'message': repr(exc),
                'details': {'traceback': traceback.format_exc()},
            }
        })
        await raw_response.write(error.encode() + b'\n')

    def _get_paths(self) -> set[str]:
        paths: set[str] = set()
        for payload in self._payloads:
            for filter in payload._walk(dsl.Filter):
                if isinstance(filter.criteria, filtering.HTTPCriteria):
                    if isinstance(filter.criteria.path, str):
                        paths.add(filter.criteria.path)
        return paths

    def _get_resources(self) -> list[resources.resource]:
        """
        Reconstruct the supposed K8s resources served by this handler.

        The resources are retrieved from:

        1) explicitly declared ``kmock.resources`` with extended info;
        2) implicitly declared via payload filters: ``kmock[resource(…)]``.

        Only the registered payloads are considered. And only the very specific
        resources — with group, version, and a plural name or 'any name'.
        Anything else is considered non-specific and thus non-discoverable.

        The reconstruction might be imprecise, it is the best effort basis.
        In case of need, declare the intended resources explicitly.
        """
        result: set[resources.resource] = set()
        for resource in self._resources:  # explicitly declared
            result.add(resource)
        for payload in self._payloads:  # implicitly declared
            for filter in payload._walk(dsl.Filter):
                if isinstance(filter.criteria, filtering.K8sCriteria):
                    if filter.criteria.resource is not None:
                        resource = filter.criteria.resource
                        if resource.group is not None and resource.version is not None:
                            name = resource.plural
                            if name is not None and name.lower() == name:
                                result.add(resource)
        return list(result)

    # e.g. /
    async def _serve_root(self, request: rendering.Request) -> rendering.Payload:
        paths: set[str] = {'/api', '/apis', '/version'}
        for resource in self._get_resources():
            if resource.group == '' and resource.version == 'v1':
                paths.add(f"/api/v1")
            else:
                paths.add(f"/apis/{resource.group}")
                paths.add(f"/apis/{resource.group}/{resource.version}")
        return {
            'paths': sorted(paths | self._get_paths()),
        }

    # e.g. /version
    async def _serve_server_version(self, request: rendering.Request) -> rendering.Payload:
        return {
            # TODO: make it configurable
            'major': '1',
            'minor': '26',
            'gitVersion': 'v1.26.4+k3s1',
            'gitCommit': '8d0255af07e95b841952563253d27b0d10bd72f0',
            'gitTreeState': 'clean',
            'buildDate': '2023-04-20T00:33:18Z',
            'goVersion': 'go1.19.8',
            'compiler': 'gc',
            'platform': 'linux/amd64'
        }

    # e.g. /api
    async def _serve_api(self, request: rendering.Request) -> rendering.Payload:
        return {'versions': ['v1']}

    # e.g. /apis
    async def _serve_apis(self, request: rendering.Request) -> rendering.Payload:
        resources = self._get_resources()
        groups = {
            group: {
                resource.version
                for resource in resources
                if resource.version is not None and resource.group == group
            }
            for group in {
                resource.group for resource in resources
                if resource.group is not None and resource.group != ''  # excluding the core v1
            }
        }
        return {
            'groups': [
                {
                    'name': group,
                    'preferredVersion': {
                        'groupVersion': f'{group}/{list(versions)[0]}',
                        'version': list(versions)[0],
                    },
                    'versions': [
                        {
                            'groupVersion': f'{group}/{version}',
                            'version': version,
                        }
                        for version in versions
                    ],
                }
                for group, versions in groups.items()
            ],
        }

    # e.g.: /apis/kopf.dev
    async def _serve_group(self, request: rendering.Request) -> rendering.Payload:
        assert request.resource is not None  # logically impossible, but for type-checkers

        resources = self._get_resources()
        groups = {
            group: {
                resource.version for resource in resources
                if resource.group is not None and resource.version is not None
                if resource.group == group
            }
            for group in {resource.group for resource in resources}
            if group != ''  # excluding the core v1
        }

        group = request.resource.group
        if group not in groups:
            raise KubernetesResourceNotFoundError()

        versions = groups[group]
        return {
            'apiVersion': 'v1',  # of APIGroup, not of the served group
            'kind': 'APIGroup',
            'name': group,
            'preferredVersion':{
                'groupVersion': f'{group}/{list(versions)[0]}',
                'version': list(versions)[0],
            },
            'versions': [
                {
                    'groupVersion': f'{group}/{version}',
                    'version': version,
                }
                for version in versions
            ],
        }

    # e.g.: /apis/kopf.dev/v1beta1
    async def _serve_version(self, request: rendering.Request) -> rendering.Payload:
        assert request.resource is not None  # logically impossible, but for type-checkers

        # Only sufficiently specific resources and only for the requested group/version.
        resources = [res for res in self._get_resources() if request.resource.check(res)]
        if not resources:
            raise KubernetesResourceNotFoundError()
        return {
            'apiVersion': 'v1',  # of APIResourceList, not of the served group
            'kind': 'APIResourceList',
            'groupVersion': f'{request.resource.group}/{request.resource.version}',
            'resources': [
                {
                    'name': f'{resource.plural}/{subresource}' if subresource else resource.plural,
                    'kind': info.kind if info.kind is not None else resource.plural.capitalize(),
                    'singularName': info.singular if info.singular is not None else resource.plural,
                    'shortNames': list(info.shortnames),
                    'categories': list(info.categories),
                    'verbs': list(info.verbs),
                    'namespaced': info.namespaced if info.namespaced is not None else None,
                }
                for resource in resources
                for info in [self._resources[resource]]
                for subresource in {''} | set(info.subresources)
                if resource.plural is not None  # impossible, but for type-checkers
            ],
        }

    @property
    def resources(self) -> k8s_views.ResourcesArray:
        return self._resources

    # Expose commonly used classes via the fixture without explicit imports (K8s-specific only).
    # The library itself DOES NOT use these fields, it uses the classes directly.
    # For when the fixture name overlaps the library name, so that it requires writing `import…as…`.
    ResourceKey = k8s_views.ResourceKey
    ResourceInfo = k8s_views.ResourceInfo
    ResourceDict = k8s_views.ResourceDict
    ResourcesArray = k8s_views.ResourcesArray


@attrs.define(kw_only=True)
class KubernetesEmulator(KubernetesScaffold):
    """
    A server that mimics Kubernetes and tracks the state of objects in memory.

    Object creation, patching, and deletion are tracked. The operations emulate
    the behaviour of a realistic Kubernetes server, but very simplistically.
    The server then serves these objects on listings, watch-streams, fetching.
    It is essentially an in-memory-database-over-http.

    However, unlike the real Kubernetes server, this emulator only modifies
    the objects as simple JSON structures: merge the dicts, overwrite the keys.
    There is no special treatment of "special" fields, e.g. lists where
    the new values are added/merged instead of overwriting the whole dict key.
    If you need "special" field treament, inherit and implement for your cases.

    All objects are available for assertions via the ``kmock.objects`` field
    (in addition to the inherited ``kmock.requests`` and others).

    Note: the object tracking happens even if there are reactions that catch
    the creation/update/deletion operations. However, the objects are shown
    only in the default handlers, i.e. when the fetching/listing/watching
    requests are not intercepted (because those responses will return
    their content instead of the stored states of the objects).

    .. seealso::
        Simulator vs. emulator: https://stackoverflow.com/a/1584701/857383
    """

    # The accessible/modifiable container of all objects stored in memory (unordered).
    _objects: k8s_views.ObjectsArray = attrs.field(factory=k8s_views.ObjectsArray, init=False)

    _lock = attrs.field(factory=asyncio.Lock, init=False)
    _buses: dict[resources.resource, aiobus.Bus[Any]] = attrs.field(factory=lambda: collections.defaultdict(aiobus.Bus))

    def __attrs_post_init__(self) -> None:
        # If there is no specific user instruction found, serve the implicit logic as a K8s server.
        # Generally, these are empty/dummy responses with conventional structure, but overrideable.
        super().__attrs_post_init__()
        self.fallback[enums.action.LIST] << self._serve_list
        self.fallback[enums.action.WATCH] << self._serve_watch
        self.fallback[enums.action.FETCH] << self._serve_fetch
        self.fallback[enums.action.CREATE] << self._serve_create
        self.fallback[enums.action.UPDATE] << self._serve_update
        self.fallback[enums.action.DELETE] << self._serve_delete

    @override
    async def _handle(self, request: rendering.Request) -> aiohttp.web.StreamResponse:
        delete_key: k8s_views.ArrayKey | None = None

        # Silently serve object-modifying requests even if intercepted by user-defined reactions.
        # These objects must be available for assertions and implicit (fallback) reading requests.
        if request.resource is not None:  # only k8s requests
            object_key: k8s_views.ArrayKey | None = None
            async with self._lock:
                if request.action == enums.action.CREATE:
                    obj = request.data
                    object_name = obj.get('metadata', {}).get('name')
                    object_namespace = obj.get('metadata', {}).get('namespace')
                    object_key = (request.resource, request.namespace or object_namespace, object_name)
                    if object_key not in self._objects:
                        self._objects[object_key] = request.data
                    elif not self._objects[object_key].deleted:
                        raise KubernetesObjectConflictError()
                    else:
                        self._objects[object_key].create(request.data)
                    raw = self._objects[object_key].last.raw
                    await self._buses[request.resource].put({'type': 'ADDED', 'object': raw})
                elif request.action == enums.action.DELETE and request.name is not None:
                    object_key = (request.resource, request.namespace, request.name)
                    if object_key not in self._objects or self._objects[object_key].deleted:
                        raise KubernetesObjectNotFoundError()
                    elif self._objects[object_key].get('metadata', {}).get('deletionTimestamp'):
                        pass  # already marked for deletion, nothing to do here
                    elif self._objects[object_key].get('metadata', {}).get('finalizers', []):
                        # TODO: remove the condition on Python 3.10 dropping.
                        now = datetime.datetime.now(tz=datetime.UTC) if sys.version_info >= (3, 11) else datetime.datetime.utcnow()
                        nows = now.isoformat()
                        self._objects[object_key].patch({'metadata': {'deletionTimestamp': nows}})
                        raw = self._objects[object_key].raw
                        await self._buses[request.resource].put({'type': 'MODIFIED', 'object': raw})
                    else:
                        self._objects[object_key].delete()
                        raw = self._objects[object_key].last.raw
                        await self._buses[request.resource].put({'type': 'DELETED', 'object': raw})
                elif request.action == enums.action.UPDATE and request.name is not None:
                    object_key = (request.resource, request.namespace, request.name)
                    if object_key not in self._objects or self._objects[object_key].deleted:
                        raise KubernetesObjectNotFoundError()
                    self._objects[object_key].patch(request.data)
                    raw = self._objects[object_key].raw
                    await self._buses[request.resource].put({'type': 'MODIFIED', 'object': raw})

                if object_key is not None and object_key in self._objects and not self._objects[object_key].deleted:
                    obj = self._objects[object_key]
                    meta = obj.get('metadata', {})
                    if meta.get('deletionTimestamp') and not meta.get('finalizers', []):
                        delete_key = object_key

        try:
            return await super()._handle(request)
        finally:
            # Garbage-collect the soft-deleted and released objects (i.e. finalizers removed).
            # But only after all handlers & fallbacks are processed & the response is generated.
            # Mainly needed for the serve_delete() handler to return the last object before the gc.
            if delete_key is not None:  # only if previously updated/deleted accordingly
                assert request.resource is not None  # logically impossible, but for type-checkers
                async with self._lock:
                    raw = self._objects[delete_key].raw
                    self._objects[delete_key].delete()
                    await self._buses[request.resource].put({'type': 'DELETED', 'object': raw})

    async def _serve_list(self, request: rendering.Request) -> rendering.Payload:
        # Check if we know this resource at all, regardless of the objects.
        for resource in self._get_resources():
            if resource == request.resource:
                break
        else:
            raise KubernetesResourceNotFoundError()

        # TODO: see test_empty_stream_yields_nothing():
        #   when a watch reaction is added, the list request is still made.
        #   but without the explicit list reaction, we get 404.
        #   we should somehow handle this for k8s-specific watches, but not for generic streams.
        async with self._lock:
            objs: list[k8s_dicts.Object] = self.__get_objs(request, strict=False)
        return {
            # TODO: kind=? version=?
            'metadata': {'resourceVersion': '...'},
            'items': [obj.raw for obj in objs if not obj.deleted],
        }

    # TODO: support ?timeout=123 for the server-side timeouts, stop after N seconds.
    async def _serve_watch(self, request: rendering.Request) -> AsyncIterator[rendering.Payload]:
        # Finish the headers and signal that we are indeed streaming (even if nothing happens).
        # Otherwise, it gets stuck at the request initialization unable to send the headers.
        yield b''

        # Instantly stream all existing objects while holding the stream mark.
        async with self._lock:
            objs: list[k8s_dicts.Object] = self.__get_objs(request, strict=False)
            objs = [obj for obj in objs if not obj.deleted]
            events = [{'type': 'ADDED', 'object': obj.raw} for obj in objs]
        for event in events:
            yield event

        # Then stream the bookmarked bus as soon as the events arrive or until cancelled.
        # This for-loop never exits normally, but on the request/stream cancellation only.
        assert request.resource is not None  # logically impossible, but for type-checkers
        async for event in self._buses[request.resource]:  # pragma: no branch
            resource = request.resource
            namespace = event.get('object', {}).get('metadata', {}).get('namespace')
            name = event.get('object', {}).get('metadata', {}).get('name')
            if self.__check(request, resource, namespace, name, strict=False):
                yield event

    async def _serve_fetch(self, request: rendering.Request) -> rendering.Payload:
        async with self._lock:
            obj: k8s_dicts.Object | None = self.__get_obj(request, strict=True)
        if obj is None or obj.deleted:
            raise KubernetesObjectNotFoundError()
        return obj.raw

    async def _serve_create(self, request: rendering.Request) -> rendering.Payload:
        # The state changes in the _handle() interceptor code. Here, we only return the state.

        # Creation is special: unlike patching/deleting, it does not use the identifying URLs,
        # but uses cluster-wide no-name ones. As such, the name/namespace is absent in request,
        # and ALL objects of that resource get picked. The name/namespace is only available
        # in the request data. To work around this, instead of rewriting the object-picking logic,
        # we fake the request and feed it into the existing logic. "If it works, it is not dumb."
        alter_request = rendering.Request(
            resource=request.resource,
            namespace=request.namespace or request.data.get('metadata', {}).get('namespace'),
            name=request.name or request.data.get('metadata', {}).get('name'),
        )
        async with self._lock:
            obj: k8s_dicts.Object | None = self.__get_obj(alter_request, strict=True)
        assert obj is not None  # logically impossible, created in _handle(); for type-checkers
        return obj.raw

    async def _serve_update(self, request: rendering.Request) -> rendering.Payload:
        # The state changes in the _handle() interceptor code. Here, we only return the state.
        # If it has been just soft-deleted in _handle(), show the last seen state as the result.
        # This could happen when we patch with finalizers=[] and thus unblock the object.
        async with self._lock:
            obj: k8s_dicts.Object | None = self.__get_obj(request, strict=True)
        assert obj is not None  # logically impossible, updated in _handle(); for type-checkers
        return obj.last.raw

    async def _serve_delete(self, request: rendering.Request) -> rendering.Payload:
        # The state changes in the _handle() interceptor code. Here, we only return the state.
        # If it has been just soft-deleted in _handle(), show the last seen state as the result.
        async with self._lock:
            obj: k8s_dicts.Object | None = self.__get_obj(request, strict=True)
        assert obj is not None  # logically impossible, deleted in _handle(); for type-checkers
        return obj.last.raw

    def _get_resources(self) -> list[resources.resource]:
        # Also include the specific objects if the resources are not declared.
        result: set[resources.resource] = set(super()._get_resources())
        for resource, _, _ in self._objects:
            result.add(resource)
        return list(result)

    def __get_obj(self, request: rendering.Request, strict: bool) -> k8s_dicts.Object | None:
        objs: list[k8s_dicts.Object] = self.__get_objs(request, strict=strict)
        if len(objs) > 1:  # pragma: no cover  # impossible to simulate in tests
            raise RuntimeError('More than one object matches the request. This should not happen.')
        return objs[0] if objs else None

    def __get_objs(self, request: rendering.Request, strict: bool) -> list[k8s_dicts.Object]:
        objs: list[k8s_dicts.Object] = []
        obj: k8s_dicts.Object
        for (resource, namespace, name), obj in self._objects.items():
            if self.__check(request, resource, namespace, name, strict=strict):
                objs.append(obj)
        return objs

    def __check(
            self,
            request: rendering.Request,
            resource: resources.resource,
            namespace: str | None,
            name: str,
            strict: bool,
    ) -> bool:
        # NB: if the request is cluster-wide, we return ALL objects of ALL namespaces,
        # not just the cluster-wide objects (as for the `kubectl get --all` CLI option).
        # TODO? redesign clusterwide as namespace=='', not None! None means ANY.
        #       this should simplify typing in many places.
        namespace_ok = (
            namespace == request.namespace if strict else
            (request.namespace is None or namespace == request.namespace)
        )
        name_ok = request.name is None or name == request.name
        return bool(resource == request.resource and namespace_ok and name_ok)

    @property
    def objects(self) -> k8s_views.ObjectsArray:
        return self._objects

    # Expose commonly used classes via the fixture without explicit imports (K8s-specific only).
    # The library itself DOES NOT use these fields, it uses the classes directly.
    # For when the fixture name overlaps the library name, so that it requires writing `import…as…`.
    ObjectKey = k8s_views.ObjectKey
    VersionKey = k8s_views.VersionKey
    HistoryKey = k8s_views.HistoryKey
    ObjectsArray = k8s_views.ObjectsArray
    ObjectVersion = k8s_dicts.ObjectVersion
    ObjectHistory = k8s_dicts.ObjectHistory
    Object = k8s_dicts.Object
