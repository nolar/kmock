import pytest
from kubernetes import client
from kubernetes.dynamic import DynamicClient
from kmock import KubernetesEmulator
from typing import Optional
import threading
import asyncio
import time

from aiohttp import web


# === HTTP.CLIENT MONKEY PATCH ===
# # Monkey-patch HTTPResponse to log response body
# # Useful for debugging HTTP traffic in tests
# import http.client as http_client
# _original_read = http_client.HTTPResponse.read
#
# def _logged_read(self, amt=None):
#     data = _original_read(self, amt)
#     if data:
#         print(f"RESPONSE: {data.decode('utf-8').replace("\n", " ")}")
#     return data
#
# http_client.HTTPResponse.read = _logged_read

class KMockServer:
    def __init__(self, handler, host: str = '127.0.0.1', port: int = 8080):
        self.host = host
        self.port = port
        self.server_thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.runner: Optional[web.AppRunner] = None
        self.handler = handler

    def start(self):
        """Start kmock server in background thread"""

        def run_server():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            app = web.Application()
            app.router.add_route('*', '/{path:.*}', self.handler)

            self.runner = web.AppRunner(app)
            self.loop.run_until_complete(self.runner.setup())
            site = web.TCPSite(self.runner, self.host, self.port)
            self.loop.run_until_complete(site.start())
            self.loop.run_forever()

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        time.sleep(1)  # Wait for server to be ready

    def stop(self):
        """Stop kmock server"""
        if self.loop and self.runner:
            # Schedule cleanup and stop in the event loop
            future = asyncio.run_coroutine_threadsafe(self.runner.cleanup(), self.loop)
            # Wait for cleanup to complete
            try:
                future.result(timeout=5)
            except Exception:
                pass
            # Stop the event loop
            self.loop.call_soon_threadsafe(self.loop.stop)
            # Wait for thread to finish
            if self.server_thread:
                self.server_thread.join(timeout=5)


@pytest.fixture(scope="function")
def kmock_handler():
    handler = KubernetesEmulator()
    handler.resources['apps/v1/deployments'] = {
        'kind': 'Deployment',
        'namespaced': True,
    }
    return handler

@pytest.fixture(scope="function")
def kmock_server(kmock_handler):
    server = KMockServer(kmock_handler)
    server.start()
    yield f"http://{server.host}:{server.port}"
    server.stop()


@pytest.fixture(scope="function")
def k8s_client(kmock_server):
    print(f"\n{'='*80}")
    print(f"Creating k8s_client for kmock_server: {kmock_server}")
    print(f"{'='*80}\n")

    configuration = client.Configuration()
    configuration.host = kmock_server
    configuration.verify_ssl = False
    configuration.debug = False  # Enable debug mode

    api_client = client.ApiClient(configuration)

    # Create DynamicClient with cache disabled to force fresh discovery
    print("Creating DynamicClient (cache disabled)...")
    dyn_client = DynamicClient(api_client, cache_file=None)

    return dyn_client
