# YMSD Sleeper API - Simplified Deployment Guide

This guide walks you through deploying the YMSD Sleeper API to AWS with EFS caching and version management. This is a simplified single-environment setup.

## Quick Start

### 1. Prerequisites

- AWS CLI configured with appropriate permissions
- Node.js 18+ and npm
- Python 3.11+
- Serverless Framework (`npm install -g serverless`)

### 2. Deploy Infrastructure

```bash
cd infrastructure
./deploy-infrastructure.sh [stack-name] [region]
```

This creates:
- EFS file system for database caching
- Security groups for Lambda and EFS
- IAM roles with appropriate permissions
- Uses your existing S3 bucket `ymsd-football`

### 3. Set Environment Variables

The infrastructure deployment will output the required environment variables. Set them:

```bash
export EFS_SECURITY_GROUP_ID=<from-output>
export EFS_SUBNET_ID_1=<from-output>
export EFS_SUBNET_ID_2=<from-output>
export EFS_ACCESS_POINT_ARN=<from-output>
export S3_BUCKET_NAME=ymsd-football
```

### 4. Deploy API

```bash
cd ..
./deploy.sh [region]
```

### 5. Test API

```bash
python test_api.py <api-url-from-deployment>
```

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   API Gateway   │────│   AWS Lambda     │────│   EFS Cache     │
│                 │    │   (FastAPI)      │    │   (Database)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                │
                       ┌──────────────────┐
                       │   S3 Bucket      │
                       │   (ymsd-football)│
                       └──────────────────┘
```

## Key Features

### Version Management
- Independent version promotion system
- Cache invalidation on version changes
- Automatic cleanup of old versions

### EFS Caching
- Database snapshots cached on EFS for fast access
- TTL-based cache expiration (1 hour default)
- Automatic cache validation and refresh

### API Endpoints
- `/v1/weekly-stats` - Main data endpoint with filtering
- `/v1/health` - Health monitoring
- `/v1/version` - Version information
- `/v1/cache/status` - Cache metrics

## Deployment Commands

### Infrastructure Deployment
```bash
# Deploy infrastructure (creates EFS, security groups, IAM roles)
cd infrastructure
./deploy-infrastructure.sh ymsd-sleeper-infrastructure us-east-1
```

### API Deployment
```bash
# Deploy API to Lambda
cd ..
./deploy.sh us-east-1
```

### Version Promotion
```bash
# List available versions
python version_manager.py list

# Promote a specific version
python version_manager.py promote --version 20241201_143022

# Validate the promotion
python version_manager.py status
```

## Environment Variables

The following environment variables are required for deployment:

### Required (set by infrastructure deployment):
- `EFS_SECURITY_GROUP_ID` - Security group for EFS access
- `EFS_SUBNET_ID_1` - First subnet for EFS mount target
- `EFS_SUBNET_ID_2` - Second subnet for EFS mount target
- `EFS_ACCESS_POINT_ARN` - EFS access point ARN

### Optional (with defaults):
- `AWS_REGION` - AWS region (default: us-east-1)
- `S3_BUCKET_NAME` - S3 bucket for database snapshots (default: ymsd-football)
- `S3_PREFIX` - S3 prefix for snapshots (default: sleeper-snapshots/)
- `EFS_MOUNT_PATH` - EFS mount path (default: /mnt/efs)

## Version Management Workflow

1. **Upload Database Snapshot**: Use the data-collection project to upload a new snapshot to S3
2. **Promote Version**: Use the version manager to promote the new version
3. **Cache Refresh**: The API automatically downloads and caches the new version
4. **Traffic Routing**: All API requests now use the new database version

### Example Version Promotion

```bash
# List available versions
python version_manager.py list

# Promote a specific version
python version_manager.py promote --version 20241201_143022

# Validate the promotion
python version_manager.py status
```

## Monitoring

### Health Checks
- `/v1/health` - Overall API health
- `/v1/cache/status` - Cache status and metrics
- CloudWatch Logs for detailed monitoring

### Key Metrics
- API response times
- Cache hit/miss rates
- Database download times
- Error rates

## Troubleshooting

### Common Issues

1. **EFS Mount Failures**
   - Check security group allows NFS (port 2049)
   - Verify subnet routing
   - Ensure Lambda has EFS permissions

2. **S3 Access Issues**
   - Verify IAM role has S3 permissions
   - Check bucket policy
   - Ensure bucket exists and is accessible

3. **Version Not Found**
   - Check version exists in S3
   - Verify manifest file is valid
   - Use version manager to list available versions

4. **Cache Issues**
   - Check EFS mount status
   - Verify cache directory permissions
   - Use cache status endpoint for diagnostics

### Debug Commands

```bash
# Check version status
python version_manager.py status

# Validate specific version
python version_manager.py validate --version <version>

# List all versions
python version_manager.py list

# Clean up old cache
python version_manager.py cleanup --keep 5
```

## Security Considerations

- Lambda functions run in VPC with restricted access
- EFS is encrypted at rest
- S3 snapshots are encrypted
- IAM roles follow least-privilege principle
- Security groups restrict network access

## Cost Optimization

- Serverless architecture (pay per request)
- EFS caching reduces S3 data transfer
- Automatic cleanup prevents storage bloat
- Provisioned EFS throughput for predictable costs

## Scaling

The API automatically scales with demand:
- Lambda concurrency limits can be adjusted
- EFS performance scales with provisioned throughput
- API Gateway handles high request volumes
- Consider CloudFront for global distribution

## Maintenance

### Regular Tasks
- Monitor cache usage and cleanup old versions
- Review CloudWatch metrics and logs
- Update dependencies periodically
- Test version promotion process

### Backup Strategy
- Database snapshots are versioned in S3
- EFS has built-in redundancy
- Consider cross-region replication for critical data

## Support

For issues or questions:
1. Check CloudWatch Logs for error details
2. Use the health check endpoints for diagnostics
3. Review the troubleshooting section above
4. Check AWS service status pages
