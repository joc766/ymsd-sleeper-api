"""
Configuration for YMSD Sleeper API

This module contains configuration settings for the API including
AWS services, database paths, and version management.
"""

import os
from pathlib import Path
from typing import Dict, Optional

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "ymsd-football")
S3_PREFIX = os.getenv("S3_PREFIX", "sleeper-snapshots/")

# EFS Configuration
EFS_MOUNT_PATH = os.getenv("EFS_MOUNT_PATH", "/mnt/efs")
# For local development, use a local cache directory if EFS is not available
if EFS_MOUNT_PATH == "/mnt/efs" and not Path(EFS_MOUNT_PATH).exists():
    # Running locally without EFS - use local cache directory
    CACHE_DIR = Path.cwd() / "local_cache"
else:
    CACHE_DIR = Path(EFS_MOUNT_PATH) / "database_cache"
CURRENT_VERSION_FILE = CACHE_DIR / "current_version.json"

# API Configuration
API_VERSION = "v1"
API_TITLE = "YMSD Sleeper API"
API_DESCRIPTION = "Fantasy Football API for YMSD Sleeper App"
API_DOCS_URL = f"/{API_VERSION}/docs"

# Database Configuration
DATABASE_CACHE_TTL = 3600  # 1 hour in seconds
MAX_CACHE_SIZE_GB = 5  # Maximum cache size in GB

# Version Management
VERSION_MANAGEMENT_SERVICE_URL = os.getenv(
    "VERSION_MANAGEMENT_SERVICE_URL", 
    "https://api.ymsd-sleeper.com/version-management"
)

def get_s3_config() -> Dict[str, str]:
    """Get S3 configuration settings"""
    return {
        "bucket_name": S3_BUCKET_NAME,
        "prefix": S3_PREFIX,
        "region": AWS_REGION
    }

def get_efs_config() -> Dict[str, str]:
    """Get EFS configuration settings"""
    return {
        "mount_path": EFS_MOUNT_PATH,
        "cache_dir": str(CACHE_DIR),
        "current_version_file": str(CURRENT_VERSION_FILE)
    }

def ensure_cache_directory() -> None:
    """Ensure the cache directory exists"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

def get_database_cache_path(version: str) -> Path:
    """Get the cache path for a specific database version"""
    return CACHE_DIR / f"database_{version}.sqlite"

def get_manifest_cache_path(version: str) -> Path:
    """Get the cache path for a specific manifest version"""
    return CACHE_DIR / f"manifest_{version}.json"
