"""
Version Management Service for YMSD Sleeper API

This independent service manages database version promotion and cache invalidation.
It can be deployed separately from the main API to allow independent version management.
"""

import json
import logging
import boto3
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from botocore.exceptions import ClientError

from config import get_s3_config, get_efs_config, ensure_cache_directory

logger = logging.getLogger(__name__)


class VersionManager:
    """Manages database version promotion and cache operations"""
    
    def __init__(self):
        """Initialize the version manager"""
        self.s3_config = get_s3_config()
        self.efs_config = get_efs_config()
        self.s3_client = boto3.client('s3', region_name=self.s3_config['region'])
        
        # Ensure cache directory exists
        ensure_cache_directory()
    
    def get_available_versions(self) -> List[Dict[str, any]]:
        """Get all available database versions from S3 with metadata"""
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
                    
                    # Get manifest metadata
                    try:
                        manifest_response = self.s3_client.get_object(
                            Bucket=self.s3_config['bucket_name'],
                            Key=key
                        )
                        manifest = json.loads(manifest_response['Body'].read())
                        
                        # Get database file info
                        db_file_info = None
                        for file_info in manifest.get('files', []):
                            if file_info.get('type') == 'database_snapshot':
                                db_file_info = file_info
                                break
                        
                        version_info = {
                            'version': version,
                            'manifest_key': key,
                            'uploaded_at': manifest.get('timestamp'),
                            'total_files': manifest.get('total_files', 0),
                            'total_size': manifest.get('total_size', 0),
                            'database_info': db_file_info
                        }
                        versions.append(version_info)
                        
                    except Exception as e:
                        logger.warning(f"Could not read manifest for version {version}: {e}")
                        # Add basic version info even if manifest is unreadable
                        versions.append({
                            'version': version,
                            'manifest_key': key,
                            'uploaded_at': obj['LastModified'].isoformat(),
                            'total_files': 0,
                            'total_size': 0,
                            'database_info': None
                        })
            
            # Sort by upload time (newest first)
            versions.sort(key=lambda x: x['uploaded_at'], reverse=True)
            return versions
            
        except Exception as e:
            logger.error(f"Error getting available versions: {e}")
            return []
    
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
    
    def promote_version(self, version: str, force: bool = False) -> Tuple[bool, str]:
        """
        Promote a database version to be the active version
        
        Args:
            version: The version to promote
            force: Whether to force promotion even if version doesn't exist
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate version exists
            available_versions = self.get_available_versions()
            version_exists = any(v['version'] == version for v in available_versions)
            
            if not version_exists and not force:
                return False, f"Version {version} not found in available versions"
            
            # Get current version for comparison
            current_version = self.get_current_version()
            
            # Update version file
            version_file = Path(self.efs_config['current_version_file'])
            version_data = {
                'version': version,
                'previous_version': current_version,
                'promoted_at': datetime.now(timezone.utc).isoformat(),
                'promoted_by': 'version_manager',
                'force_promotion': force
            }
            
            with open(version_file, 'w') as f:
                json.dump(version_data, f, indent=2)
            
            # Invalidate cache for old version (optional cleanup)
            if current_version and current_version != version:
                self._invalidate_cache(current_version)
            
            logger.info(f"Successfully promoted version {version} (previous: {current_version})")
            return True, f"Version {version} promoted successfully"
            
        except Exception as e:
            logger.error(f"Error promoting version {version}: {e}")
            return False, f"Error promoting version: {str(e)}"
    
    def _invalidate_cache(self, version: str) -> None:
        """Invalidate cache for a specific version"""
        try:
            from config import get_database_cache_path, get_manifest_cache_path
            
            db_path = get_database_cache_path(version)
            manifest_path = get_manifest_cache_path(version)
            
            if db_path.exists():
                db_path.unlink()
                logger.info(f"Removed cached database for version {version}")
            
            if manifest_path.exists():
                manifest_path.unlink()
                logger.info(f"Removed cached manifest for version {version}")
                
        except Exception as e:
            logger.error(f"Error invalidating cache for version {version}: {e}")
    
    def get_version_status(self) -> Dict[str, any]:
        """Get comprehensive version status information"""
        try:
            current_version = self.get_current_version()
            available_versions = self.get_available_versions()
            
            # Get current version details
            current_version_info = None
            if current_version:
                current_version_info = next(
                    (v for v in available_versions if v['version'] == current_version),
                    None
                )
            
            return {
                'current_version': current_version,
                'current_version_info': current_version_info,
                'available_versions': available_versions,
                'total_versions': len(available_versions),
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting version status: {e}")
            return {
                'current_version': None,
                'current_version_info': None,
                'available_versions': [],
                'total_versions': 0,
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'error': str(e)
            }
    
    def validate_version(self, version: str) -> Tuple[bool, str]:
        """
        Validate that a version exists and is accessible
        
        Args:
            version: The version to validate
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            available_versions = self.get_available_versions()
            version_info = next((v for v in available_versions if v['version'] == version), None)
            
            if not version_info:
                return False, f"Version {version} not found"
            
            # Check if database file exists in S3
            if version_info['database_info']:
                db_key = version_info['database_info']['s3_key']
                try:
                    self.s3_client.head_object(
                        Bucket=self.s3_config['bucket_name'],
                        Key=db_key
                    )
                    return True, f"Version {version} is valid and accessible"
                except ClientError as e:
                    return False, f"Database file for version {version} not accessible: {e}"
            else:
                return False, f"No database file found for version {version}"
                
        except Exception as e:
            logger.error(f"Error validating version {version}: {e}")
            return False, f"Error validating version: {str(e)}"
    
    def cleanup_old_versions(self, keep_count: int = 5) -> Tuple[int, List[str]]:
        """
        Clean up old cached versions, keeping only the most recent ones
        
        Args:
            keep_count: Number of recent versions to keep
            
        Returns:
            Tuple of (cleaned_count, removed_versions)
        """
        try:
            from config import get_database_cache_path, get_manifest_cache_path
            
            available_versions = self.get_available_versions()
            current_version = self.get_current_version()
            
            # Sort versions by upload time (newest first)
            sorted_versions = sorted(
                available_versions,
                key=lambda x: x['uploaded_at'],
                reverse=True
            )
            
            # Determine which versions to remove
            versions_to_remove = []
            for i, version_info in enumerate(sorted_versions):
                version = version_info['version']
                # Keep current version and recent versions
                if version != current_version and i >= keep_count:
                    versions_to_remove.append(version)
            
            # Remove cached files for old versions
            removed_versions = []
            for version in versions_to_remove:
                try:
                    self._invalidate_cache(version)
                    removed_versions.append(version)
                except Exception as e:
                    logger.warning(f"Could not remove cache for version {version}: {e}")
            
            logger.info(f"Cleaned up {len(removed_versions)} old versions")
            return len(removed_versions), removed_versions
            
        except Exception as e:
            logger.error(f"Error cleaning up old versions: {e}")
            return 0, []


# CLI interface for version management
def main():
    """Command line interface for version management"""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="YMSD Sleeper API Version Manager")
    parser.add_argument("command", choices=["list", "promote", "status", "validate", "cleanup"],
                       help="Command to execute")
    parser.add_argument("--version", help="Version to promote or validate")
    parser.add_argument("--force", action="store_true", help="Force promotion even if version doesn't exist")
    parser.add_argument("--keep", type=int, default=5, help="Number of versions to keep during cleanup")
    
    args = parser.parse_args()
    
    manager = VersionManager()
    
    try:
        if args.command == "list":
            versions = manager.get_available_versions()
            current = manager.get_current_version()
            
            print(f"Available versions (current: {current}):")
            for version_info in versions:
                status = " [CURRENT]" if version_info['version'] == current else ""
                print(f"  {version_info['version']}{status}")
                print(f"    Uploaded: {version_info['uploaded_at']}")
                print(f"    Size: {version_info['total_size']} bytes")
                print()
        
        elif args.command == "promote":
            if not args.version:
                print("Error: --version required for promote command")
                sys.exit(1)
            
            success, message = manager.promote_version(args.version, args.force)
            if success:
                print(f"✓ {message}")
            else:
                print(f"✗ {message}")
                sys.exit(1)
        
        elif args.command == "status":
            status = manager.get_version_status()
            print(f"Current version: {status['current_version']}")
            print(f"Total available versions: {status['total_versions']}")
            print(f"Last updated: {status['last_updated']}")
            
            if status['current_version_info']:
                info = status['current_version_info']
                print(f"Current version details:")
                print(f"  Uploaded: {info['uploaded_at']}")
                print(f"  Size: {info['total_size']} bytes")
        
        elif args.command == "validate":
            if not args.version:
                print("Error: --version required for validate command")
                sys.exit(1)
            
            is_valid, message = manager.validate_version(args.version)
            if is_valid:
                print(f"✓ {message}")
            else:
                print(f"✗ {message}")
                sys.exit(1)
        
        elif args.command == "cleanup":
            cleaned_count, removed_versions = manager.cleanup_old_versions(args.keep)
            print(f"Cleaned up {cleaned_count} old versions:")
            for version in removed_versions:
                print(f"  - {version}")
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
