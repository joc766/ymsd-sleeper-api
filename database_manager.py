"""
Database Manager for YMSD Sleeper API

This module handles database operations including caching, version management,
and query execution with EFS integration.
"""

import json
import sqlite3
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import boto3
from botocore.exceptions import ClientError

from config import (
    get_s3_config, get_efs_config, ensure_cache_directory,
    get_database_cache_path, get_manifest_cache_path,
    DATABASE_CACHE_TTL, MAX_CACHE_SIZE_GB
)
from models import WeeklyStatsResponse, WeeklyStatsQuery, WeeklyStatsSummary

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database operations with EFS caching and version management"""
    
    def __init__(self):
        """Initialize the database manager"""
        self.s3_config = get_s3_config()
        self.efs_config = get_efs_config()
        self.s3_client = boto3.client('s3', region_name=self.s3_config['region'])
        
        # Ensure cache directory exists
        ensure_cache_directory()
        
        # Current database connection
        self._db_connection: Optional[sqlite3.Connection] = None
        self._current_version: Optional[str] = None
        self._cache_timestamp: Optional[datetime] = None
    
    def get_current_version(self) -> Optional[str]:
        """Get the current active database version"""
        try:
            version_file = Path(self.efs_config['current_version_file'])
            if version_file.exists():
                with open(version_file, 'r') as f:
                    version_data = json.load(f)
                    return version_data.get('version')
        except Exception as e:
            logger.error(f"Error reading current version: {e}")
        return None
    
    def set_current_version(self, version: str) -> bool:
        """Set the current active database version"""
        try:
            version_file = Path(self.efs_config['current_version_file'])
            version_data = {
                'version': version,
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'updated_by': 'api'
            }
            
            with open(version_file, 'w') as f:
                json.dump(version_data, f, indent=2)
            
            logger.info(f"Set current version to: {version}")
            return True
        except Exception as e:
            logger.error(f"Error setting current version: {e}")
            return False
    
    def is_cache_valid(self, version: str) -> bool:
        """Check if the cached database is valid and not expired"""
        try:
            db_path = get_database_cache_path(version)
            if not db_path.exists():
                return False
            
            # Check if cache is expired
            cache_age = datetime.now(timezone.utc).timestamp() - db_path.stat().st_mtime
            if cache_age > DATABASE_CACHE_TTL:
                logger.info(f"Cache expired for version {version}")
                return False
            
            # Verify file integrity
            return self._verify_database_integrity(db_path, version)
        except Exception as e:
            logger.error(f"Error checking cache validity: {e}")
            return False
    
    def _verify_database_integrity(self, db_path: Path, version: str) -> bool:
        """Verify database file integrity"""
        try:
            # Try to open and query the database
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Check if WeeklyStats table exists and has data
            cursor.execute("SELECT COUNT(*) FROM WeeklyStats LIMIT 1")
            result = cursor.fetchone()
            
            conn.close()
            return result is not None
        except Exception as e:
            logger.error(f"Database integrity check failed: {e}")
            return False
    
    def download_database_from_s3(self, version: str) -> bool:
        """Download database from S3 to EFS cache"""
        try:
            # Get manifest to find the database file
            manifest_key = f"{self.s3_config['prefix']}manifests/manifest_{version}.json"
            manifest_path = get_manifest_cache_path(version)
            
            # Download manifest
            logger.info(f"Downloading manifest: {manifest_key}")
            self.s3_client.download_file(
                self.s3_config['bucket_name'],
                manifest_key,
                str(manifest_path)
            )
            
            # Read manifest to get database file info
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            # Find database file in manifest
            db_file_info = None
            for file_info in manifest.get('files', []):
                if file_info.get('type') == 'database_snapshot':
                    db_file_info = file_info
                    break
            
            if not db_file_info:
                logger.error("No database file found in manifest")
                return False
            
            # Download database file
            db_path = get_database_cache_path(version)
            logger.info(f"Downloading database: {db_file_info['s3_key']}")
            
            self.s3_client.download_file(
                self.s3_config['bucket_name'],
                db_file_info['s3_key'],
                str(db_path)
            )
            
            # Verify download
            if self._verify_database_integrity(db_path, version):
                logger.info(f"Successfully cached database version {version}")
                return True
            else:
                logger.error(f"Downloaded database failed integrity check")
                db_path.unlink(missing_ok=True)
                return False
                
        except Exception as e:
            logger.error(f"Error downloading database from S3: {e}")
            return False
    
    def get_database_connection(self, version: Optional[str] = None) -> Optional[sqlite3.Connection]:
        """Get database connection, ensuring the correct version is cached"""
        try:
            # Use current version if not specified
            if version is None:
                version = self.get_current_version()
            
            if not version:
                logger.error("No version specified and no current version set")
                return None
            
            # Check if we need to update cache
            if (self._current_version != version or 
                not self.is_cache_valid(version) or 
                self._db_connection is None):
                
                logger.info(f"Updating database cache to version: {version}")
                
                # Download database if not cached or invalid
                if not self.is_cache_valid(version):
                    if not self.download_database_from_s3(version):
                        logger.error(f"Failed to download database version {version}")
                        return None
                
                # Close existing connection
                if self._db_connection:
                    self._db_connection.close()
                
                # Open new connection
                db_path = get_database_cache_path(version)
                self._db_connection = sqlite3.connect(str(db_path))
                self._db_connection.row_factory = sqlite3.Row  # Enable column access by name
                self._current_version = version
                self._cache_timestamp = datetime.now(timezone.utc)
                
                logger.info(f"Connected to database version {version}")
            
            return self._db_connection
            
        except Exception as e:
            logger.error(f"Error getting database connection: {e}")
            return None
    
    def get_weekly_stats(self, query: WeeklyStatsQuery) -> Tuple[List[WeeklyStatsResponse], WeeklyStatsSummary]:
        """Get weekly stats data with filtering and pagination"""
        try:
            conn = self.get_database_connection()
            if not conn:
                raise Exception("No database connection available")
            
            # Build query
            where_conditions = []
            params = []
            
            if query.league_id:
                where_conditions.append("LeagueID = ?")
                params.append(query.league_id)
            
            if query.season:
                where_conditions.append("Season = ?")
                params.append(query.season)
            
            if query.week is not None:
                where_conditions.append("Week = ?")
                params.append(query.week)
            
            if query.roster_code is not None:
                where_conditions.append("RosterCode = ?")
                params.append(query.roster_code)
            
            if query.is_playoff is not None:
                where_conditions.append("IsPlayoff = ?")
                params.append(1 if query.is_playoff else 0)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # Get total count for summary
            count_query = f"SELECT COUNT(*) as total FROM WeeklyStats {where_clause}"
            cursor = conn.execute(count_query, params)
            total_count = cursor.fetchone()['total']
            
            # Get summary statistics
            summary_query = f"""
                SELECT 
                    COUNT(*) as total_records,
                    SUM(Points) as total_points,
                    SUM(Win) as total_wins,
                    SUM(Loss) as total_losses,
                    SUM(Tie) as total_ties,
                    AVG(Points) as average_points
                FROM WeeklyStats {where_clause}
            """
            cursor = conn.execute(summary_query, params)
            summary_row = cursor.fetchone()
            
            # Get paginated data
            data_query = f"""
                SELECT * FROM WeeklyStats {where_clause}
                ORDER BY Season DESC, Week DESC, Points DESC
                LIMIT ? OFFSET ?
            """
            data_params = params + [query.limit, query.offset]
            cursor = conn.execute(data_query, data_params)
            
            # Convert to response models
            weekly_stats = []
            for row in cursor.fetchall():
                weekly_stats.append(WeeklyStatsResponse(
                    weekly_stats_id=row['WeeklyStatsID'],
                    roster_code=row['RosterCode'],
                    league_id=row['LeagueID'],
                    season=row['Season'],
                    week=row['Week'],
                    points=row['Points'],
                    points_against=row['PointsAgainst'],
                    win=bool(row['Win']),
                    loss=bool(row['Loss']),
                    tie=bool(row['Tie']),
                    opponent_roster_code=row['OpponentRosterCode'],
                    is_playoff=bool(row['IsPlayoff']),
                    created_date=datetime.fromisoformat(row['CreatedDate'])
                ))
            
            # Create summary
            total_wins = summary_row['total_wins'] or 0
            total_losses = summary_row['total_losses'] or 0
            total_ties = summary_row['total_ties'] or 0
            total_games = total_wins + total_losses + total_ties
            win_percentage = (total_wins / total_games * 100) if total_games > 0 else 0
            
            summary = WeeklyStatsSummary(
                total_records=total_count,
                total_points=summary_row['total_points'] or 0,
                total_wins=total_wins,
                total_losses=total_losses,
                total_ties=total_ties,
                average_points=summary_row['average_points'] or 0,
                win_percentage=round(win_percentage, 2)
            )
            
            return weekly_stats, summary
            
        except Exception as e:
            logger.error(f"Error getting weekly stats: {e}")
            raise
    
    def get_available_versions(self) -> List[str]:
        """Get list of available database versions from S3"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.s3_config['bucket_name'],
                Prefix=f"{self.s3_config['prefix']}manifests/",
                MaxKeys=100
            )
            
            versions = []
            for obj in response.get('Contents', []):
                key = obj['Key']
                if key.endswith('.json'):
                    # Extract version from manifest filename
                    version = key.split('/')[-1].replace('manifest_', '').replace('.json', '')
                    versions.append(version)
            
            return sorted(versions, reverse=True)  # Newest first
            
        except Exception as e:
            logger.error(f"Error getting available versions: {e}")
            return []
    
    def cleanup_old_cache(self) -> None:
        """Clean up old cached database files to manage EFS storage"""
        try:
            cache_dir = Path(self.efs_config['cache_dir'])
            current_version = self.get_current_version()
            
            # Get all cached database files
            db_files = list(cache_dir.glob("database_*.sqlite"))
            
            # Calculate total cache size
            total_size = sum(f.stat().st_size for f in db_files)
            max_size_bytes = MAX_CACHE_SIZE_GB * 1024 * 1024 * 1024
            
            if total_size > max_size_bytes:
                logger.info(f"Cache size ({total_size / 1024 / 1024 / 1024:.2f} GB) exceeds limit")
                
                # Sort by modification time (oldest first)
                db_files.sort(key=lambda f: f.stat().st_mtime)
                
                # Remove oldest files until under limit
                for db_file in db_files:
                    if db_file.name != f"database_{current_version}.sqlite":
                        logger.info(f"Removing old cache file: {db_file.name}")
                        db_file.unlink()
                        
                        # Recalculate size
                        total_size = sum(f.stat().st_size for f in cache_dir.glob("database_*.sqlite"))
                        if total_size <= max_size_bytes:
                            break
                            
        except Exception as e:
            logger.error(f"Error cleaning up cache: {e}")
    
    def close(self) -> None:
        """Close database connection"""
        if self._db_connection:
            self._db_connection.close()
            self._db_connection = None
