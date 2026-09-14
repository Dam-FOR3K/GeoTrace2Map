# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Coordinates Parser & Validator
Handles Decimal degrees, DMS, DDM, EXIF Rationals, and sanity validation.
"""
import re
from typing import Optional, Tuple, Any

def parse_coordinate(val: Any) -> Optional[float]:
    """
    Parses a single latitude or longitude coordinate from float, int, or string.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
        
    if isinstance(val, str):
        val_clean = val.strip().replace(',', '.')
        if not val_clean:
            return None
            
        # Try direct float
        try:
            return float(val_clean)
        except ValueError:
            pass

        # Try extracting number from phrases like "Horizontal: 15", "15 m", "Radius: 20"
        num_match = re.search(r'[-+]?\d*\.?\d+', val_clean)
        if num_match and any(k in val_clean.lower() for k in ('horizontal', 'radius', 'accuracy', 'precision', 'rayon', 'incertitude', 'm')):
            try:
                return float(num_match.group(0))
            except Exception:
                pass
            
        # Try DMS regex: e.g. 48° 51' 24.5" N or 48 51 24.5 N
        dms_match = re.match(r'^(-?\d+(?:\.\d+)?)[°\s]+(\d+(?:\.\d+)?)[′\'\s]+(\d+(?:\.\d+)?)[″\"\s]*([NSEWnsew])?$', val_clean)
        if dms_match:
            deg, minutes, seconds, direction = dms_match.groups()
            decimal = float(deg) + float(minutes)/60.0 + float(seconds)/3600.0
            if direction and direction.upper() in ('S', 'W'):
                decimal = -abs(decimal)
            return decimal
            
        # Try DDM regex: e.g. 48° 51.398' N
        ddm_match = re.match(r'^(-?\d+(?:\.\d+)?)[°\s]+(\d+(?:\.\d+)?)[′\'\s]*([NSEWnsew])?$', val_clean)
        if ddm_match:
            deg, minutes, direction = ddm_match.groups()
            decimal = float(deg) + float(minutes)/60.0
            if direction and direction.upper() in ('S', 'W'):
                decimal = -abs(decimal)
            return decimal

        # Try space-separated DMS: e.g. "30 4 59.98 N"
        parts = val_clean.split()
        if len(parts) >= 3:
            try:
                deg = float(parts[0])
                minutes = float(parts[1])
                sec_part = parts[2]
                direction = parts[3] if len(parts) > 3 else None
                
                # Check if direction is attached to seconds
                if sec_part[-1].upper() in ('N', 'S', 'E', 'W'):
                    direction = sec_part[-1]
                    sec_val = float(sec_part[:-1])
                else:
                    sec_val = float(sec_part)
                    
                decimal = deg + (minutes / 60.0) + (sec_val / 3600.0)
                if direction and direction.upper() in ('S', 'W'):
                    decimal = -abs(decimal)
                return decimal
            except Exception:
                pass

    return None

def validate_coordinates(lat: Optional[float], lon: Optional[float], allow_null_island: bool = False) -> Tuple[bool, Optional[float], Optional[float]]:
    """
    Validates lat and lon.
    Returns: (is_valid, sanitized_lat, sanitized_lon)
    """
    if lat is None or lon is None:
        return False, None, None
        
    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        return False, None, None
        
    # Check bounds
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        # Check if coordinates were swapped (e.g. lon in lat field)
        if -90.0 <= lon <= 90.0 and -180.0 <= lat <= 180.0:
            lat, lon = lon, lat
        else:
            return False, None, None
            
    # Filter Null Island (0.0, 0.0) default dummy coordinates
    if not allow_null_island and abs(lat) < 0.0001 and abs(lon) < 0.0001:
        return False, None, None
        
    return True, round(lat, 7), round(lon, 7)

def parse_exif_dms(dms_values, ref: str) -> Optional[float]:
    """
    Convert EXIF GPS DMS tuple ((deg_num, deg_den), (min_num, min_den), (sec_num, sec_den)) to decimal.
    """
    try:
        def _to_float(v):
            if isinstance(v, (int, float)):
                return float(v)
            if hasattr(v, 'num') and hasattr(v, 'den'):
                return float(v.num) / float(v.den) if v.den != 0 else 0.0
            if isinstance(v, tuple) and len(v) == 2:
                return float(v[0]) / float(v[1]) if v[1] != 0 else 0.0
            return float(v)

        deg = _to_float(dms_values[0])
        minutes = _to_float(dms_values[1])
        seconds = _to_float(dms_values[2])
        
        decimal = deg + (minutes / 60.0) + (seconds / 3600.0)
        if ref and ref.upper() in ('S', 'W'):
            decimal = -abs(decimal)
        return decimal
    except Exception:
        return None
