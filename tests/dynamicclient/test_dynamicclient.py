import pytest
import logging
from kubernetes.dynamic.exceptions import ResourceNotFoundError, NotFoundError, ConflictError

logger = logging.getLogger(__name__)


def test_resource_not_found_error(k8s_client):
    with pytest.raises(ResourceNotFoundError):
        result = k8s_client.resources.get(api_version='v1', kind='PodWithATypo200')
        raise AssertionError(f"Expected ResourceNotFoundError but got result: {result}")
    with pytest.raises(ResourceNotFoundError):
        result = k8s_client.resources.get(api_version='randomApiVersion/v100', kind='randomKind3')
        raise AssertionError(f"Expected ResourceNotFoundError but got result: {result}")


def test_crud(k8s_client):
    v1_deployment = k8s_client.resources.get(api_version='apps/v1', kind='Deployment')

    # Step 1: Verify resource doesn't exist
    with pytest.raises(NotFoundError):
        v1_deployment.get(name='crud-test-deployment', namespace='test-namespace')

    # Step 2: Create deployment
    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "crud-test-deployment",
            "namespace": "test-namespace",
            "labels": {
                "original-label": "original-value"
            }
        },
        "spec": {
            "replicas": 1,
            "selector": {
                "matchLabels": {
                    "app": "crud-test"
                }
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": "crud-test"
                    }
                },
                "spec": {
                    "containers": [{
                        "name": "nginx",
                        "image": "nginx:1.14.2"
                    }]
                }
            }
        }
    }

    v1_deployment.create(body=deployment, namespace='test-namespace')

    # Step 3: Try to create the same deployment again
    with pytest.raises(ConflictError):
        v1_deployment.create(body=deployment, namespace='test-namespace')

    # Step 4: Get and verify creation worked
    retrieved = v1_deployment.get(name='crud-test-deployment', namespace='test-namespace')
    assert retrieved.metadata.name == 'crud-test-deployment'
    assert retrieved.metadata.labels['original-label'] == 'original-value'
    assert retrieved.spec.replicas == 1
    assert retrieved.spec.template.spec.containers[0].image == 'nginx:1.14.2'

    # Step 5: Patch (update) deployment
    patch = {
        "metadata": {
            "labels": {
                "new-label": "new-value",
                "original-label": "updated-value"
            }
        },
        "spec": {
            "replicas": 3,
            "template": {
                "spec": {
                    "containers": [{
                        "name": "nginx",
                        "image": "nginx:1.21.0"
                    }]
                }
            }
        }
    }

    patched = v1_deployment.patch(body=patch, name='crud-test-deployment', namespace='test-namespace')

    # Step 6: Get and verify update worked
    updated = v1_deployment.get(name='crud-test-deployment', namespace='test-namespace')

    # Verify existing fields not in patch are preserved
    assert updated.spec.selector.matchLabels['app'] == 'crud-test'

    # Verify new field was added
    assert updated.metadata.labels['new-label'] == 'new-value'

    # Verify existing fields in patch were updated
    assert updated.metadata.labels['original-label'] == 'updated-value'
    assert updated.spec.replicas == 3
    assert updated.spec.template.spec.containers[0].image == 'nginx:1.21.0'

    # Step 7: Delete deployment
    v1_deployment.delete(name='crud-test-deployment', namespace='test-namespace')

    # Step 8: Verify deletion
    with pytest.raises(NotFoundError):
        v1_deployment.get(name='crud-test-deployment', namespace='test-namespace')
