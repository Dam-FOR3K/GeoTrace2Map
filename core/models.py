# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Forensic Geolocation Data Models
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import uuid

class ForensicLocationPoint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None          # Horizontal accuracy / uncertainty in meters
    vertical_accuracy: Optional[float] = None # Vertical accuracy in meters
    speed: Optional[float] = None             # Speed in m/s or km/h
    bearing: Optional[float] = None           # Heading / Course in degrees (0-360)
    
    timestamp_raw: Optional[Any] = None       # Original raw timestamp from database/file
    timestamp_utc: Optional[str] = None       # ISO 8601 UTC string (YYYY-MM-DDTHH:MM:SSZ)
    timestamp_local: Optional[str] = None     # Local formatted string
    epoch_type: Optional[str] = None          # "Cocoa (2001)", "Unix Sec", "Unix MS", "WebKit", "GPS", "String"
    
    source_file: str                          # Path inside archive or disk (e.g. "com.apple.routined/CoreRoutine.sqlite")
    source_type: str                          # e.g. "iOS CoreRoutine", "Android Google Services", "Photos EXIF", "UFED Report"
    category: str = "generic"                 # "gps_fix", "exif_photo", "wifi", "cell_tower", "system_routine", "messaging", "navigation", "generic"
    table_or_field: Optional[str] = None      # e.g. "ZRTCLLOCATIONMO (ZLATITUDE, ZLONGITUDE)"
    device_os: Optional[str] = "Unknown"      # "iOS", "Android", "UFED", "Unknown"
    
    confidence: Optional[str] = "medium"      # "high", "medium", "low"
    address: Optional[str] = None             # Reverse geocoded postal address if resolved
    extra_data: Dict[str, Any] = Field(default_factory=dict) # Key-value metadata (BSSID, SSID, CellID, Lac, MCC, MNC, photo thumbnail b64, etc.)

class ExtractionSummary(BaseModel):
    total_points: int = 0
    valid_points: int = 0
    duplicate_points_removed: int = 0
    date_min: Optional[str] = None
    date_max: Optional[str] = None
    sources_count: Dict[str, int] = Field(default_factory=dict)
    categories_count: Dict[str, int] = Field(default_factory=dict)
    detected_os: List[str] = Field(default_factory=list)
    scanned_files_count: int = 0
    execution_time_seconds: float = 0.0
    errors: List[str] = Field(default_factory=list)
