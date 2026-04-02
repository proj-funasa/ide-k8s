#!/usr/bin/env python3
"""Turn IDE on: scale up, apply ingress, configure AWS."""
import subprocess, sys, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

def run(cmd):
    print(f"  $ {cmd}")
    if subprocess.run(cmd, shell=True).returncode != 0:
        sys.exit(1)

print("Scaling up...")
run("kubectl scale deployment ide-deployment ide-router -n default --replicas=1")
run("kubectl rollout status deployment/ide-deployment deployment/ide-router -n default --timeout=120s")
run("kubectl apply -f user-spawner/ingress.yaml")

print("Configuring AWS...")
run("python3 deploy.py --aws-only")

print("\nIDE is ON — https://ide.dataiesb.com")
