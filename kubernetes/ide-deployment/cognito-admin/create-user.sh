#!/bin/bash
set -e

USER_NAME="cognito_admin_iesb"
POLICY_NAME="CognitoAdminIesbPolicy"
ACCOUNT_ID="248189947068"
REGION="us-east-1"
SECRET_NAME="cognito-admin-iesb-credentials"
PROFILE_NAME="cognito_admin_iesb"

# Create IAM user
aws iam create-user --user-name $USER_NAME 2>/dev/null || echo "User $USER_NAME already exists"

# Create and attach policy
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"
aws iam create-policy --policy-name $POLICY_NAME --policy-document file://policy.json 2>/dev/null || echo "Policy already exists"
aws iam attach-user-policy --user-name $USER_NAME --policy-arn $POLICY_ARN

# Create access key
echo "Creating access key..."
KEY_OUTPUT=$(aws iam create-access-key --user-name $USER_NAME)
ACCESS_KEY=$(echo $KEY_OUTPUT | jq -r '.AccessKey.AccessKeyId')
SECRET_KEY=$(echo $KEY_OUTPUT | jq -r '.AccessKey.SecretAccessKey')

# Store in Secrets Manager
echo "Storing credentials in Secrets Manager..."
aws secretsmanager create-secret \
  --name $SECRET_NAME \
  --region $REGION \
  --secret-string "{\"AccessKeyId\":\"$ACCESS_KEY\",\"SecretAccessKey\":\"$SECRET_KEY\"}" \
  2>/dev/null || \
aws secretsmanager update-secret \
  --secret-id $SECRET_NAME \
  --region $REGION \
  --secret-string "{\"AccessKeyId\":\"$ACCESS_KEY\",\"SecretAccessKey\":\"$SECRET_KEY\"}"

# Configure local AWS profile
echo "Configuring AWS profile '$PROFILE_NAME'..."
aws configure set aws_access_key_id "$ACCESS_KEY" --profile $PROFILE_NAME
aws configure set aws_secret_access_key "$SECRET_KEY" --profile $PROFILE_NAME
aws configure set region "$REGION" --profile $PROFILE_NAME

echo ""
echo "Done!"
echo "  Secrets Manager: $SECRET_NAME"
echo "  AWS Profile: $PROFILE_NAME"
echo "  Run: streamlit run cognito_admin.py"
