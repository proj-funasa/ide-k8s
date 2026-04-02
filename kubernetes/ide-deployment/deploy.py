#!/usr/bin/env python3
"""Deploy Funasa IDE: k8s manifests + ALB + Cognito + Route53 + WAF."""

import json
import subprocess
import sys
import time
import boto3

REGION = "us-east-1"
CLUSTER = "dataiesb-cluster"
NAMESPACE = "default"
ZONE_DOMAIN = "dataiesb.com"
IDE_DOMAIN = "ide.dataiesb.com"
COGNITO_USER_POOL_ID = "us-east-1_KsQSqvc9B"
COGNITO_CLIENT_ID = "5lvif42ss8170fh2s24bs9fj5c"
COGNITO_DOMAIN = "funasa-ide"
WAF_NAME = "funasa-ide-waf"

MANIFESTS = [
    "../network/network-policy.yaml",
    "storage.yaml",
    "rbac.yaml",
    "deployment.yaml",
    "service.yaml",
    "user-spawner/router.yaml",
    "user-spawner/ingress.yaml",
]
DEPLOYMENTS = ["ide-deployment", "ide-router"]

r53 = boto3.client("route53", region_name=REGION)
waf = boto3.client("wafv2", region_name=REGION)
elbv2 = boto3.client("elbv2", region_name=REGION)
cognito = boto3.client("cognito-idp", region_name=REGION)


def run(cmd):
    print(f"  $ {cmd}")
    if subprocess.run(cmd, shell=True).returncode != 0:
        print(f"FAILED: {cmd}")
        sys.exit(1)


def wait_for_alb():
    """Wait for the IDE ingress ALB to be provisioned, return its DNS."""
    print("Waiting for ALB...")
    for attempt in range(24):
        result = subprocess.run(
            ["kubectl", "get", "ingress", "funasa-ide-ingress", "-n", NAMESPACE, "-o", "json"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            ing = json.loads(result.stdout)
            lbs = ing.get("status", {}).get("loadBalancer", {}).get("ingress", [])
            if lbs:
                dns = lbs[0]["hostname"]
                print(f"  ALB ready: {dns}")
                return dns
        print(f"  Waiting... ({attempt+1}/24)")
        time.sleep(10)
    print("ERROR: ALB not ready after 4 minutes")
    sys.exit(1)


def get_alb_info(dns_name):
    """Return (arn, hosted_zone_id) for an ALB by DNS name."""
    for lb in elbv2.describe_load_balancers()["LoadBalancers"]:
        if lb["DNSName"] == dns_name:
            return lb["LoadBalancerArn"], lb["CanonicalHostedZoneId"]
    raise RuntimeError(f"ALB not found for {dns_name}")


def configure_cognito(alb_dns):
    """Update Cognito app client callback URL to match the IDE domain."""
    callback = f"https://{IDE_DOMAIN}/oauth2/idpresponse"
    client = cognito.describe_user_pool_client(
        UserPoolId=COGNITO_USER_POOL_ID, ClientId=COGNITO_CLIENT_ID,
    )["UserPoolClient"]

    if client.get("CallbackURLs") == [callback]:
        print(f"  Cognito callback already set to {callback}")
        return

    cognito.update_user_pool_client(
        UserPoolId=COGNITO_USER_POOL_ID,
        ClientId=COGNITO_CLIENT_ID,
        CallbackURLs=[callback],
        AllowedOAuthFlows=client.get("AllowedOAuthFlows", ["code"]),
        AllowedOAuthScopes=client.get("AllowedOAuthScopes", ["openid", "email"]),
        AllowedOAuthFlowsUserPoolClient=True,
        SupportedIdentityProviders=client.get("SupportedIdentityProviders", ["COGNITO"]),
    )
    print(f"  Cognito callback -> {callback}")


def configure_route53(alb_dns, alb_zone_id):
    zones = r53.list_hosted_zones_by_name(DNSName=ZONE_DOMAIN, MaxItems="1")
    zone_id = None
    for z in zones["HostedZones"]:
        if z["Name"].rstrip(".") == ZONE_DOMAIN:
            zone_id = z["Id"].split("/")[-1]
    if not zone_id:
        raise RuntimeError(f"Hosted zone for {ZONE_DOMAIN} not found")

    r53.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={"Changes": [{
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": IDE_DOMAIN,
                "Type": "A",
                "AliasTarget": {
                    "HostedZoneId": alb_zone_id,
                    "DNSName": f"dualstack.{alb_dns}",
                    "EvaluateTargetHealth": True,
                },
            },
        }]},
    )
    print(f"  Route53: {IDE_DOMAIN} -> {alb_dns}")


def configure_waf(alb_arn):
    # Find or create WAF ACL
    acls = waf.list_web_acls(Scope="REGIONAL")["WebACLs"]
    waf_arn = next((a["ARN"] for a in acls if a["Name"] == WAF_NAME), None)

    if not waf_arn:
        resp = waf.create_web_acl(
            Name=WAF_NAME, Scope="REGIONAL",
            DefaultAction={"Allow": {}},
            VisibilityConfig={"SampledRequestsEnabled": True, "CloudWatchMetricsEnabled": True, "MetricName": WAF_NAME},
            Rules=[
                {"Name": "RateLimit", "Priority": 1, "Action": {"Block": {}},
                 "Statement": {"RateBasedStatement": {"Limit": 1000, "AggregateKeyType": "IP"}},
                 "VisibilityConfig": {"SampledRequestsEnabled": True, "CloudWatchMetricsEnabled": True, "MetricName": "RateLimit"}},
                {"Name": "AWSManagedCommonRules", "Priority": 2, "OverrideAction": {"None": {}},
                 "Statement": {"ManagedRuleGroupStatement": {"VendorName": "AWS", "Name": "AWSManagedRulesCommonRuleSet"}},
                 "VisibilityConfig": {"SampledRequestsEnabled": True, "CloudWatchMetricsEnabled": True, "MetricName": "AWSManagedCommonRules"}},
                {"Name": "AWSManagedSQLiRules", "Priority": 3, "OverrideAction": {"None": {}},
                 "Statement": {"ManagedRuleGroupStatement": {"VendorName": "AWS", "Name": "AWSManagedRulesSQLiRuleSet"}},
                 "VisibilityConfig": {"SampledRequestsEnabled": True, "CloudWatchMetricsEnabled": True, "MetricName": "AWSManagedSQLiRules"}},
            ],
        )
        waf_arn = resp["Summary"]["ARN"]
        print(f"  WAF ACL created")
    else:
        print(f"  WAF ACL already exists")

    # Associate
    for attempt in range(5):
        try:
            waf.associate_web_acl(WebACLArn=waf_arn, ResourceArn=alb_arn)
            print(f"  WAF associated with ALB")
            return
        except waf.exceptions.WAFInvalidParameterException:
            print(f"  WAF already associated")
            return
        except waf.exceptions.WAFUnavailableEntityException:
            time.sleep(5)


def main():
    aws_only = "--aws-only" in sys.argv

    if not aws_only:
        print("1. Updating kubeconfig...")
        run(f"aws eks update-kubeconfig --region {REGION} --name {CLUSTER}")

        print("2. Applying manifests...")
        for m in MANIFESTS:
            run(f"kubectl apply -f {m}")

        print("3. Waiting for rollouts...")
        for d in DEPLOYMENTS:
            run(f"kubectl rollout status deployment/{d} -n {NAMESPACE} --timeout=120s")

    print("4. Waiting for ALB...")
    alb_dns = wait_for_alb()
    alb_arn, alb_zone_id = get_alb_info(alb_dns)

    print("5. Configuring Cognito...")
    configure_cognito(alb_dns)

    print("6. Configuring Route53...")
    configure_route53(alb_dns, alb_zone_id)

    print("7. Configuring WAF...")
    configure_waf(alb_arn)

    print(f"\nDone! IDE: https://{IDE_DOMAIN}")


if __name__ == "__main__":
    main()
