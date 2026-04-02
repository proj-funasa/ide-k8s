#!/usr/bin/env python3
"""Cognito Post-Auth Lambda: creates a per-user IDE deployment on EKS."""

import json
import os
import re
import boto3

CLUSTER = os.environ.get("EKS_CLUSTER", "dataiesb-cluster")
REGION = os.environ.get("AWS_REGION", "us-east-1")
NAMESPACE = "default"
IMAGE = os.environ.get("IDE_IMAGE", "248189947068.dkr.ecr.us-east-1.amazonaws.com/ide-code-server:latest")

eks = boto3.client("eks", region_name=REGION)


def sanitize(email):
    """Turn email into a safe k8s name."""
    return re.sub(r"[^a-z0-9]", "-", email.split("@")[0].lower()).strip("-")[:40]


def get_k8s_client():
    """Build a kubernetes client from EKS cluster info."""
    import kubernetes
    from kubernetes import client, config

    cluster_info = eks.describe_cluster(name=CLUSTER)["cluster"]
    endpoint = cluster_info["endpoint"]
    ca_data = cluster_info["certificateAuthority"]["data"]

    # Get token via STS
    sts = boto3.client("sts", region_name=REGION)
    token = sts.generate_presigned_url(
        "get_caller_identity",
        Params={},
        ExpiresIn=60,
        HttpMethod="GET",
    )
    # EKS token format
    import base64
    k8s_token = "k8s-aws-v1." + base64.urlsafe_b64encode(token.encode()).decode().rstrip("=")

    configuration = kubernetes.client.Configuration()
    configuration.host = endpoint
    configuration.api_key = {"BearerToken": k8s_token}
    import tempfile
    ca_file = tempfile.NamedTemporaryFile(delete=False, suffix=".crt")
    ca_file.write(base64.b64decode(ca_data))
    ca_file.close()
    configuration.ssl_ca_cert = ca_file.name

    return kubernetes.client.ApiClient(configuration)


def user_resources_exist(api_client, slug):
    apps = kubernetes.client.AppsV1Api(api_client)
    try:
        apps.read_namespaced_deployment(f"ide-{slug}", NAMESPACE)
        return True
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404:
            return False
        raise


def create_user_resources(api_client, slug):
    import kubernetes
    core = kubernetes.client.CoreV1Api(api_client)
    apps = kubernetes.client.AppsV1Api(api_client)

    # PVC
    pvc = kubernetes.client.V1PersistentVolumeClaim(
        metadata=kubernetes.client.V1ObjectMeta(name=f"ide-{slug}-pvc", namespace=NAMESPACE),
        spec=kubernetes.client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            storage_class_name="ebs-gp3",
            resources=kubernetes.client.V1VolumeResourceRequirements(
                requests={"storage": "10Gi"}
            ),
        ),
    )
    try:
        core.create_namespaced_persistent_volume_claim(NAMESPACE, pvc)
    except kubernetes.client.exceptions.ApiException as e:
        if e.status != 409:
            raise

    # Deployment
    container = kubernetes.client.V1Container(
        name="ide",
        image=IMAGE,
        ports=[kubernetes.client.V1ContainerPort(container_port=8080)],
        command=["/bin/sh"],
        args=["-c", "cd /home/coder/workspace && exec code-server --bind-addr 0.0.0.0:8080 --auth none ."],
        resources=kubernetes.client.V1ResourceRequirements(
            requests={"memory": "512Mi"},
            limits={"memory": "1843Mi"},
        ),
        volume_mounts=[kubernetes.client.V1VolumeMount(
            name="storage", mount_path="/home/coder/workspace"
        )],
    )
    deployment = kubernetes.client.V1Deployment(
        metadata=kubernetes.client.V1ObjectMeta(name=f"ide-{slug}", namespace=NAMESPACE),
        spec=kubernetes.client.V1DeploymentSpec(
            replicas=1,
            selector=kubernetes.client.V1LabelSelector(match_labels={"app": f"ide-{slug}"}),
            template=kubernetes.client.V1PodTemplateSpec(
                metadata=kubernetes.client.V1ObjectMeta(labels={"app": f"ide-{slug}"}),
                spec=kubernetes.client.V1PodSpec(
                    service_account_name="ide-admin",
                    containers=[container],
                    volumes=[kubernetes.client.V1Volume(
                        name="storage",
                        persistent_volume_claim=kubernetes.client.V1PersistentVolumeClaimVolumeSource(
                            claim_name=f"ide-{slug}-pvc"
                        ),
                    )],
                ),
            ),
        ),
    )
    try:
        apps.create_namespaced_deployment(NAMESPACE, deployment)
    except kubernetes.client.exceptions.ApiException as e:
        if e.status != 409:
            raise

    # Service
    svc = kubernetes.client.V1Service(
        metadata=kubernetes.client.V1ObjectMeta(name=f"ide-{slug}", namespace=NAMESPACE),
        spec=kubernetes.client.V1ServiceSpec(
            selector={"app": f"ide-{slug}"},
            ports=[kubernetes.client.V1ServicePort(port=80, target_port=8080)],
            type="ClusterIP",
        ),
    )
    try:
        core.create_namespaced_service(NAMESPACE, svc)
    except kubernetes.client.exceptions.ApiException as e:
        if e.status != 409:
            raise


def handler(event, context):
    """Cognito Post Authentication trigger."""
    import kubernetes

    email = event["request"]["userAttributes"].get("email", event["userName"])
    slug = sanitize(email)

    api_client = get_k8s_client()

    if not user_resources_exist(api_client, slug):
        print(f"Creating IDE resources for {slug}")
        create_user_resources(api_client, slug)
    else:
        print(f"IDE resources already exist for {slug}")

    return event
