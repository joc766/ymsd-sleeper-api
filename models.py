"""
Pydantic models for the YMSD Sleeper API

This module defines the data models used for API requests and responses.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class WeeklyStatsResponse(BaseModel):
    """Response model for weekly stats data"""
    weekly_stats_id: int
    roster_code: int
    league_id: str
    season: str
    week: int
    points: float
    points_against: float
    win: bool
    loss: bool
    tie: bool
    opponent_roster_code: Optional[int] = None
    is_playoff: bool = False
    created_date: datetime

    class Config:
        from_attributes = True


class WeeklyStatsQuery(BaseModel):
    """Query parameters for weekly stats endpoint"""
    league_id: Optional[str] = Field(None, description="Filter by league ID")
    season: Optional[str] = Field(None, description="Filter by season")
    week: Optional[int] = Field(None, description="Filter by week")
    roster_code: Optional[int] = Field(None, description="Filter by roster code")
    is_playoff: Optional[bool] = Field(None, description="Filter by playoff status")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Number of results to skip")


class WeeklyStatsSummary(BaseModel):
    """Summary statistics for weekly stats"""
    total_records: int
    total_points: float
    total_wins: int
    total_losses: int
    total_ties: int
    average_points: float
    win_percentage: float


class WeeklyStatsResponseWithSummary(BaseModel):
    """Response model with data and summary"""
    data: List[WeeklyStatsResponse]
    summary: WeeklyStatsSummary
    query_params: WeeklyStatsQuery
    version: str
    cached: bool
    cache_timestamp: Optional[datetime] = None


class VersionInfo(BaseModel):
    """Information about the current database version"""
    version: str
    s3_key: str
    manifest_key: str
    uploaded_at: datetime
    sha256: str
    size: int
    is_active: bool


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    database_connected: bool
    cache_status: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime
    request_id: Optional[str] = None


class CacheStatus(BaseModel):
    """Cache status information"""
    current_version: str
    cache_size_mb: float
    last_updated: datetime
    is_valid: bool
    available_versions: List[str]
