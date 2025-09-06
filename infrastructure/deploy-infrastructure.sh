#!/bin/bash

# Infrastructure deployment script for YMSD Sleeper API
# Simplified single-environment setup

set -e

# Configuration
STACK_NAME=${1:-ymsd-sleeper-infrastructure}
REGION=${2:-us-east-1}

echo "🏗️  Deploying YMSD Sleeper API Infrastructure"
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"

# Check if AWS CLI is installed and configured
if ! command -v aws &> /dev/null; then
    echo "❌ Error: AWS CLI is not installed"
    echo "   Install with: pip install awscli"
    exit 1
fi

if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ Error: AWS credentials not configured"
    echo "   Run: aws configure"
    exit 1
fi

# Get VPC and subnet information
echo "🔍 Getting VPC and subnet information..."

# Get default VPC
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query "Vpcs[0].VpcId" --output text --region $REGION)

if [ "$VPC_ID" = "None" ] || [ -z "$VPC_ID" ]; then
    echo "❌ Error: No default VPC found"
    echo "   Please specify a VPC ID manually or create a default VPC"
    exit 1
fi

echo "   VPC ID: $VPC_ID"

# Get subnets in the VPC
SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query "Subnets[].SubnetId" --output text --region $REGION)

if [ -z "$SUBNET_IDS" ]; then
    echo "❌ Error: No subnets found in VPC $VPC_ID"
    exit 1
fi

# Convert to comma-separated list
SUBNET_LIST=$(echo $SUBNET_IDS | tr ' ' ',')

echo "   Subnet IDs: $SUBNET_LIST"

# Deploy CloudFormation stack
echo "🚀 Deploying CloudFormation stack..."

aws cloudformation deploy \
    --template-file cloudformation.yml \
    --stack-name $STACK_NAME \
    --parameter-overrides \
        VpcId=$VPC_ID \
        SubnetIds=$SUBNET_LIST \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $REGION

# Get stack outputs
echo "📋 Getting stack outputs..."

EFS_FILE_SYSTEM_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs[?OutputKey=='EfsFileSystemId'].OutputValue" \
    --output text \
    --region $REGION)

EFS_ACCESS_POINT_ARN=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs[?OutputKey=='EfsAccessPointArn'].OutputValue" \
    --output text \
    --region $REGION)

EFS_SECURITY_GROUP_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs[?OutputKey=='EfsSecurityGroupId'].OutputValue" \
    --output text \
    --region $REGION)

LAMBDA_SECURITY_GROUP_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs[?OutputKey=='LambdaSecurityGroupId'].OutputValue" \
    --output text \
    --region $REGION)

S3_BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs[?OutputKey=='S3BucketName'].OutputValue" \
    --output text \
    --region $REGION)

echo ""
echo "✅ Infrastructure deployment completed successfully!"
echo ""
echo "📋 Environment Variables for API Deployment:"
echo "   export EFS_SECURITY_GROUP_ID=$EFS_SECURITY_GROUP_ID"
echo "   export EFS_SUBNET_ID_1=$(echo $SUBNET_LIST | cut -d',' -f1)"
echo "   export EFS_SUBNET_ID_2=$(echo $SUBNET_LIST | cut -d',' -f2)"
echo "   export EFS_ACCESS_POINT_ARN=$EFS_ACCESS_POINT_ARN"
echo "   export S3_BUCKET_NAME=$S3_BUCKET_NAME"
echo ""
echo "🔧 To deploy the API with these settings:"
echo "   cd .."
echo "   export EFS_SECURITY_GROUP_ID=$EFS_SECURITY_GROUP_ID"
echo "   export EFS_SUBNET_ID_1=$(echo $SUBNET_LIST | cut -d',' -f1)"
echo "   export EFS_SUBNET_ID_2=$(echo $SUBNET_LIST | cut -d',' -f2)"
echo "   export EFS_ACCESS_POINT_ARN=$EFS_ACCESS_POINT_ARN"
echo "   export S3_BUCKET_NAME=$S3_BUCKET_NAME"
echo "   ./deploy.sh $REGION"
echo ""
echo "📊 Infrastructure Details:"
echo "   EFS File System ID: $EFS_FILE_SYSTEM_ID"
echo "   EFS Access Point ARN: $EFS_ACCESS_POINT_ARN"
echo "   S3 Bucket Name: $S3_BUCKET_NAME"
