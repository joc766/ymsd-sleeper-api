"""
Main FastAPI application for YMSD Sleeper API

This module contains the FastAPI application with endpoints for accessing
fantasy football data from cached database snapshots.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import API_VERSION, API_TITLE, API_DESCRIPTION, API_DOCS_URL
from models import (
    WeeklyStatsResponseWithSummary, WeeklyStatsQuery, WeeklyStatsResponse,
    HealthCheckResponse, ErrorResponse, VersionInfo, CacheStatus
)
from database_manager import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global database manager instance
db_manager: Optional[DatabaseManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global db_manager
    
    # Startup
    logger.info("Starting YMSD Sleeper API...")
    db_manager = DatabaseManager()
    
    # Clean up old cache on startup
    db_manager.cleanup_old_cache()
    
    yield
    
    # Shutdown
    logger.info("Shutting down YMSD Sleeper API...")
    if db_manager:
        db_manager.close()


# Create FastAPI application
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    docs_url=API_DOCS_URL,
    redoc_url=f"/{API_VERSION}/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db_manager() -> DatabaseManager:
    """Dependency to get database manager"""
    if db_manager is None:
        raise HTTPException(status_code=503, detail="Database manager not initialized")
    return db_manager


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc),
            timestamp=datetime.now(timezone.utc),
            request_id=getattr(request.state, 'request_id', None)
        ).dict()
    )


@app.get(f"/{API_VERSION}/health", response_model=HealthCheckResponse)
async def health_check(db: DatabaseManager = Depends(get_db_manager)):
    """Health check endpoint"""
    try:
        # Test database connection
        conn = db.get_database_connection()
        database_connected = conn is not None
        
        # Get cache status
        current_version = db.get_current_version()
        cache_status = "active" if current_version and db.is_cache_valid(current_version) else "inactive"
        
        return HealthCheckResponse(
            status="healthy" if database_connected else "unhealthy",
            version=API_VERSION,
            database_connected=database_connected,
            cache_status=cache_status,
            timestamp=datetime.now(timezone.utc)
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheckResponse(
            status="unhealthy",
            version=API_VERSION,
            database_connected=False,
            cache_status="error",
            timestamp=datetime.now(timezone.utc)
        )


@app.get(f"/{API_VERSION}/version", response_model=VersionInfo)
async def get_current_version(db: DatabaseManager = Depends(get_db_manager)):
    """Get current database version information"""
    try:
        current_version = db.get_current_version()
        if not current_version:
            raise HTTPException(status_code=404, detail="No active version found")
        
        # Get version details from S3
        available_versions = db.get_available_versions()
        if current_version not in available_versions:
            raise HTTPException(status_code=404, detail="Current version not found in S3")
        
        # For now, return basic version info
        # In a full implementation, you'd fetch detailed metadata from S3
        return VersionInfo(
            version=current_version,
            s3_key=f"snapshots/database_{current_version}.sqlite",
            manifest_key=f"manifests/manifest_{current_version}.json",
            uploaded_at=datetime.now(timezone.utc),  # Would get from S3 metadata
            sha256="",  # Would get from S3 metadata
            size=0,  # Would get from S3 metadata
            is_active=True
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting version info: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving version information")


@app.get(f"/{API_VERSION}/versions", response_model=List[str])
async def list_available_versions(db: DatabaseManager = Depends(get_db_manager)):
    """List all available database versions"""
    try:
        versions = db.get_available_versions()
        return versions
    except Exception as e:
        logger.error(f"Error listing versions: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving available versions")


@app.get(f"/{API_VERSION}/cache/status", response_model=CacheStatus)
async def get_cache_status(db: DatabaseManager = Depends(get_db_manager)):
    """Get cache status information"""
    try:
        current_version = db.get_current_version()
        available_versions = db.get_available_versions()
        
        # Calculate cache size
        from pathlib import Path
        from config import get_efs_config
        cache_dir = Path(get_efs_config()['cache_dir'])
        cache_size = sum(f.stat().st_size for f in cache_dir.glob("*.sqlite")) / 1024 / 1024
        
        return CacheStatus(
            current_version=current_version or "none",
            cache_size_mb=round(cache_size, 2),
            last_updated=datetime.now(timezone.utc),  # Would get from file metadata
            is_valid=db.is_cache_valid(current_version) if current_version else False,
            available_versions=available_versions
        )
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving cache status")


@app.get(f"/{API_VERSION}/weekly-stats", response_model=WeeklyStatsResponseWithSummary)
async def get_weekly_stats(
    league_id: Optional[str] = Query(None, description="Filter by league ID"),
    season: Optional[str] = Query(None, description="Filter by season"),
    week: Optional[int] = Query(None, description="Filter by week"),
    roster_code: Optional[int] = Query(None, description="Filter by roster code"),
    is_playoff: Optional[bool] = Query(None, description="Filter by playoff status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get weekly stats data with filtering and pagination"""
    try:
        # Create query object
        query = WeeklyStatsQuery(
            league_id=league_id,
            season=season,
            week=week,
            roster_code=roster_code,
            is_playoff=is_playoff,
            limit=limit,
            offset=offset
        )
        
        # Get data from database
        weekly_stats, summary = db.get_weekly_stats(query)
        
        # Get current version info
        current_version = db.get_current_version()
        cache_timestamp = db._cache_timestamp
        
        return WeeklyStatsResponseWithSummary(
            data=weekly_stats,
            summary=summary,
            query_params=query,
            version=current_version or "unknown",
            cached=True,
            cache_timestamp=cache_timestamp
        )
        
    except Exception as e:
        logger.error(f"Error getting weekly stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving weekly stats data")


@app.get(f"/{API_VERSION}/weekly-stats/roster/{{roster_code}}", response_model=List[WeeklyStatsResponse])
async def get_roster_weekly_stats(
    roster_code: int,
    season: Optional[str] = Query(None, description="Filter by season"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get weekly stats for a specific roster"""
    try:
        query = WeeklyStatsQuery(
            roster_code=roster_code,
            season=season,
            limit=limit,
            offset=0
        )
        
        weekly_stats, _ = db.get_weekly_stats(query)
        return weekly_stats
        
    except Exception as e:
        logger.error(f"Error getting roster weekly stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving roster weekly stats")


@app.get(f"/{API_VERSION}/weekly-stats/league/{{league_id}}", response_model=List[WeeklyStatsResponse])
async def get_league_weekly_stats(
    league_id: str,
    season: Optional[str] = Query(None, description="Filter by season"),
    week: Optional[int] = Query(None, description="Filter by week"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get weekly stats for a specific league"""
    try:
        query = WeeklyStatsQuery(
            league_id=league_id,
            season=season,
            week=week,
            limit=limit,
            offset=0
        )
        
        weekly_stats, _ = db.get_weekly_stats(query)
        return weekly_stats
        
    except Exception as e:
        logger.error(f"Error getting league weekly stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving league weekly stats")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": API_TITLE,
        "version": API_VERSION,
        "description": API_DESCRIPTION,
        "docs_url": API_DOCS_URL,
        "endpoints": {
            "health": f"/{API_VERSION}/health",
            "weekly_stats": f"/{API_VERSION}/weekly-stats",
            "version": f"/{API_VERSION}/version",
            "versions": f"/{API_VERSION}/versions",
            "cache_status": f"/{API_VERSION}/cache/status"
        }
    }


if __name__ == "__main__":
    # For local development
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
