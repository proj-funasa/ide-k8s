#!/bin/bash
set -e

REGION="us-east-1"
ACCOUNT_ID="248189947068"
FUNCTION_NAME="funasa-ide-spawner"
ROLE_NAME="funasa-ide-spawner-role"
CLUSTER="dataiesb-cluster"
USER_POOL_ID="us-east-1_KsQSqvc9B"

echo "=== Building Lambda package ==="
TMPDIR=$(mktemp -d)
pip install -t "$TMPDIR" -r requirements.txt -q
cp spawner.py "$TMPDIR/lambda_function.py"
cd "$TMPDIR"
# rename handler for Lambda
sed -i 's/^def handler/def lambda_handler/' lambda_function.py
sed -i 's/handler = handler/handler = lambda_handler/' lambda_function.py
zip -r9 /tmp/spawner.zip . -q
cd -
rm -rf "$TMPDIR"

echo "=== Creating IAM Role ==="
TRUST_POLICY='{
  "Version":"2012-10-17",
  "Statement":[{
    "Effect":"Allow",
    "Principal":{"Service":"lambda.amazonaws.com"},
    "Action":"sts:AssumeRole"
  }]
}'

aws iam create-role \
  --role-name $ROLE_NAME \
  --assume-role-policy-document "$TRUST_POLICY" 2>/dev/null || echo "Role already exists"

# Attach policies: basic Lambda execution + EKS access
aws iam attach-role-policy --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

POLICY_DOC=$(cat <<EOF
{
  "Version":"2012-10-17",
  "Statement":[
    {
      "Effect":"Allow",
      "Action":["eks:DescribeCluster"],
      "Resource":"arn:aws:eks:${REGION}:${ACCOUNT_ID}:cluster/${CLUSTER}"
    },
    {
      "Effect":"Allow",
      "Action":["sts:GetCallerIdentity"],
      "Resource":"*"
    }
  ]
}
EOF
)

aws iam put-role-policy \
  --role-name $ROLE_NAME \
  --policy-name "${FUNCTION_NAME}-eks-access" \
  --policy-document "$POLICY_DOC"

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

echo "Waiting for role propagation..."
sleep 10

echo "=== Creating Lambda ==="
aws lambda create-function \
  --function-name $FUNCTION_NAME \
  --runtime python3.12 \
  --handler lambda_function.lambda_handler \
  --role "$ROLE_ARN" \
  --zip-file fileb:///tmp/spawner.zip \
  --timeout 30 \
  --memory-size 256 \
  --environment "Variables={EKS_CLUSTER=$CLUSTER,IDE_IMAGE=${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/ide-code-server:latest}" \
  --region $REGION 2>/dev/null || \
aws lambda update-function-code \
  --function-name $FUNCTION_NAME \
  --zip-file fileb:///tmp/spawner.zip \
  --region $REGION

echo "=== Granting Cognito permission to invoke Lambda ==="
aws lambda add-permission \
  --function-name $FUNCTION_NAME \
  --statement-id cognito-invoke \
  --action lambda:InvokeFunction \
  --principal cognito-idp.amazonaws.com \
  --source-arn "arn:aws:cognito-idp:${REGION}:${ACCOUNT_ID}:userpool/${USER_POOL_ID}" \
  --region $REGION 2>/dev/null || echo "Permission already exists"

LAMBDA_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}"

echo "=== Attaching Lambda to Cognito Post-Auth trigger ==="
aws cognito-idp update-user-pool \
  --user-pool-id $USER_POOL_ID \
  --lambda-config "PostAuthentication=$LAMBDA_ARN" \
  --region $REGION

echo ""
echo "Done!"
echo "  Lambda: $FUNCTION_NAME"
echo "  Trigger: PostAuthentication on $USER_POOL_ID"
echo ""
echo "IMPORTANT: Add the Lambda role to the EKS aws-auth ConfigMap:"
echo "  kubectl edit configmap aws-auth -n kube-system"
echo "  Add under mapRoles:"
echo "    - rolearn: $ROLE_ARN"
echo "      username: lambda-spawner"
echo "      groups: [system:masters]"
