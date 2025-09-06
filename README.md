# YMSD Sleeper API

A FastAPI-based REST API for accessing fantasy football data from the YMSD Sleeper App database snapshots. The API is designed to run on AWS Lambda with EFS caching for efficient database access.

## Architecture

The API uses a versioned database snapshot system with the following components:

- **FastAPI Application**: REST API with endpoints for fantasy football data
- **AWS Lambda**: Serverless compute for the API
- **EFS (Elastic File System)**: Cached database storage for fast access
- **S3**: Storage for database snapshots and manifests (uses existing `ymsd-football` bucket)
- **Version Management**: Independent service for promoting database versions

## Features

- **Weekly Stats Endpoint**: Access to pre-calculated weekly performance data
- **Version Management**: Independent promotion of database versions
- **EFS Caching**: Automatic caching of database snapshots for performance
- **Filtering & Pagination**: Flexible querying with filtering and pagination
- **Health Monitoring**: Health check endpoints for monitoring
- **Auto-scaling**: Serverless architecture with automatic scaling

## API Endpoints

### Core Endpoints

- `GET /v1/health` - Health check
- `GET /v1/version` - Current database version information
- `GET /v1/versions` - List all available database versions
- `GET /v1/cache/status` - Cache status information

### Data Endpoints

- `GET /v1/weekly-stats` - Get weekly stats with filtering
- `GET /v1/weekly-stats/roster/{roster_code}` - Get stats for specific roster
- `GET /v1/weekly-stats/league/{league_id}` - Get stats for specific league

### Query Parameters

The weekly stats endpoint supports the following filters:

- `league_id` - Filter by league ID
- `season` - Filter by season (e.g., "2024")
- `week` - Filter by week number
- `roster_code` - Filter by roster code
- `is_playoff` - Filter by playoff status (true/false)
- `limit` - Maximum number of results (1-1000, default: 100)
- `offset` - Number of results to skip (default: 0)

## Quick Deployment

### Prerequisites

- AWS CLI configured with appropriate permissions
- Node.js 18+ and npm
- Python 3.11+
- Serverless Framework (`npm install -g serverless`)

### 1. Deploy Infrastructure

```bash
cd infrastructure
./deploy-infrastructure.sh
```

### 2. Set Environment Variables

The infrastructure deployment will output the required environment variables. Set them:

```bash
export EFS_SECURITY_GROUP_ID=<from-output>
export EFS_SUBNET_ID_1=<from-output>
export EFS_SUBNET_ID_2=<from-output>
export EFS_ACCESS_POINT_ARN=<from-output>
export S3_BUCKET_NAME=ymsd-football
```

### 3. Deploy API

```bash
cd ..
./deploy.sh
```

### 4. Test API

```bash
python test_api.py <api-url-from-deployment>
```

## Version Management

The API uses an independent version management system that allows you to promote different database snapshots without changing the API code.

### Promoting a Version

```bash
python version_manager.py promote --version <version>
```

### Listing Available Versions

```bash
python version_manager.py list
```

### Validating a Version

```bash
python version_manager.py validate --version <version>
```

### Cleaning Up Old Versions

```bash
python version_manager.py cleanup --keep 5
```

## Database Schema

The API accesses the `WeeklyStats` table with the following structure:

```sql
CREATE TABLE WeeklyStats (
  WeeklyStatsID INTEGER PRIMARY KEY AUTOINCREMENT,
  RosterCode INTEGER NOT NULL,
  LeagueID TEXT NOT NULL,
  Season TEXT NOT NULL,
  Week INTEGER NOT NULL,
  Points REAL NOT NULL,
  PointsAgainst REAL NOT NULL,
  Win INTEGER NOT NULL,
  Loss INTEGER NOT NULL,
  Tie INTEGER NOT NULL,
  OpponentRosterCode INTEGER,
  IsPlayoff INTEGER DEFAULT 0,
  CreatedDate DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Caching Strategy

The API implements a multi-level caching strategy:

1. **EFS Cache**: Database files are cached on EFS for fast access
2. **Version-based Invalidation**: Cache is invalidated when versions change
3. **TTL-based Expiration**: Cache expires after 1 hour by default
4. **Automatic Cleanup**: Old cached versions are automatically cleaned up

## Monitoring

### Health Checks

The API provides comprehensive health check endpoints:

- `/v1/health` - Overall API health
- `/v1/cache/status` - Cache status and metrics
- `/v1/version` - Current version information

### Logging

All API requests and errors are logged to CloudWatch Logs with structured logging for easy monitoring and debugging.

## Development

### Local Development

Run the API locally for development:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the development server
python main.py
```

The API will be available at `http://localhost:8000` with automatic documentation at `http://localhost:8000/v1/docs`.

### Testing

Test the API endpoints:

```bash
# Health check
curl http://localhost:8000/v1/health

# Get weekly stats
curl "http://localhost:8000/v1/weekly-stats?season=2024&limit=10"

# Get specific roster stats
curl http://localhost:8000/v1/weekly-stats/roster/1?season=2024
```

## Security

- **VPC Integration**: Lambda functions run in a VPC with restricted access
- **IAM Roles**: Least-privilege IAM roles for AWS service access
- **EFS Encryption**: Database files are encrypted at rest
- **S3 Encryption**: Snapshots are encrypted in S3
- **CORS Configuration**: Configurable CORS settings for web access

## Cost Optimization

- **Serverless Architecture**: Pay only for actual usage
- **EFS Caching**: Reduces S3 data transfer costs
- **Automatic Cleanup**: Prevents storage bloat
- **Provisioned Throughput**: Optimized EFS performance settings

## Troubleshooting

### Common Issues

1. **EFS Mount Issues**: Ensure security groups allow NFS traffic (port 2049)
2. **S3 Access Issues**: Verify IAM permissions for S3 bucket access
3. **Version Not Found**: Check that the version exists in S3
4. **Cache Issues**: Use the cache status endpoint to diagnose problems

### Debugging

Enable debug logging by setting the log level:

```bash
export LOG_LEVEL=DEBUG
```

Check CloudWatch Logs for detailed error information and request traces.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
