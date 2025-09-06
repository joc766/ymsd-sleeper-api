#!/bin/bash

# Deployment script for YMSD Sleeper API
# Simplified single-environment setup

set -e

# Configuration
REGION=${1:-us-east-1}
S3_BUCKET_NAME=${S3_BUCKET_NAME:-ymsd-football}
S3_PREFIX=${S3_PREFIX:-sleeper-snapshots/}

echo "🚀 Deploying YMSD Sleeper API to AWS Lambda"
echo "Region: $REGION"
echo "S3 Bucket: $S3_BUCKET_NAME"
echo "S3 Prefix: $S3_PREFIX"

# Check if required environment variables are set
if [ -z "$EFS_SECURITY_GROUP_ID" ]; then
    echo "❌ Error: EFS_SECURITY_GROUP_ID environment variable is required"
    echo "   Run the infrastructure deployment first:"
    echo "   cd infrastructure && ./deploy-infrastructure.sh"
    exit 1
fi

if [ -z "$EFS_SUBNET_ID_1" ] || [ -z "$EFS_SUBNET_ID_2" ]; then
    echo "❌ Error: EFS_SUBNET_ID_1 and EFS_SUBNET_ID_2 environment variables are required"
    echo "   Run the infrastructure deployment first:"
    echo "   cd infrastructure && ./deploy-infrastructure.sh"
    exit 1
fi

if [ -z "$EFS_ACCESS_POINT_ARN" ]; then
    echo "❌ Error: EFS_ACCESS_POINT_ARN environment variable is required"
    echo "   Run the infrastructure deployment first:"
    echo "   cd infrastructure && ./deploy-infrastructure.sh"
    exit 1
fi

# Check if serverless is installed
if ! command -v serverless &> /dev/null; then
    echo "❌ Error: Serverless Framework is not installed"
    echo "   Install with: npm install -g serverless"
    exit 1
fi

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ Error: AWS credentials not configured"
    echo "   Run: aws configure"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Install serverless plugins
echo "�� Installing serverless plugins..."
npm install serverless-python-requirements

# Deploy with serverless
echo "🚀 Deploying to AWS..."
serverless deploy \
    --region $REGION \
    --verbose

# Get the API URL
echo "📋 Getting deployment information..."
API_URL=$(serverless info --region $REGION | grep "endpoint:" | awk '{print $2}')

echo ""
echo "✅ Deployment completed successfully!"
echo "🌐 API URL: $API_URL"
echo "📚 API Documentation: $API_URL/v1/docs"
echo "❤️  Health Check: $API_URL/v1/health"
echo ""
echo "🔧 To test the API:"
echo "   curl $API_URL/v1/health"
echo ""
echo "📝 To promote a database version:"
echo "   python version_manager.py promote --version <version>"
echo ""
echo "🧹 To clean up old versions:"
echo "   python version_manager.py cleanup --keep 5"
