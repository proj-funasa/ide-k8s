#!/usr/bin/env python3
"""Turn IDE off: delete ingress (ALB), scale down. Keeps PVC and Cognito."""
import subprocess, sys

def run(cmd):
    print(f"  $ {cmd}")
    subprocess.run(cmd, shell=True)

print("Stopping IDE...")
run("kubectl delete ingress funasa-ide-ingress -n default --ignore-not-found")
run("kubectl scale deployment ide-deployment ide-router -n default --replicas=0")

print("\nIDE is OFF — PVC and Cognito preserved")
