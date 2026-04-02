# IDE Deployment

Cloud-based IDE for Development Analysis System.

## Components

- **Deployment**: Main IDE container with development tools
- **Service**: ClusterIP service for internal access  
- **Ingress**: ALB ingress for external access via ide.dataiesb.com
- **Storage**: 50GB GP3 EBS persistent volume
- **RBAC**: Service account with cluster admin permissions

## Tools Included

- Docker
- kubectl (configured for default namespace)
- AWS CLI
- eksctl
- Code Server IDE

## Access

- URL: https://ide.dataiesb.com
- Authentication: Password from AWS Secrets Manager

## Management

To update secrets: `./update-secret.sh`
