# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - iOS Apple Maps GeoBookmarks & Saved Places Parser
Extracts pinned places, bookmarks, and favorite locations from GeoBookmarks.plist.
"""
import plistlib
import os
from typing import List, Any, Dict, Optional
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import validate_coordinates

def _find_coords_in_dict(d: Dict[str, Any], results: list, parent_title: Optional[str] = None):
    """Recursively traverses nested dictionaries and lists looking for coordinate pairs."""
    keys_lower = {k.lower(): k for k in d.keys()}
    
    title = d.get("title") or d.get("name") or d.get("label") or d.get("syncData") or parent_title
    date_val = d.get("date") or d.get("dateAdded") or d.get("timestamp") or d.get("modified")
    
    # Check for direct latitude / longitude keys
    lat_key = next((orig for low, orig in keys_lower.items() if low in ("latitude", "lat", "_latitude")), None)
    lon_key = next((orig for low, orig in keys_lower.items() if low in ("longitude", "lon", "lng", "_longitude")), None)
    
    if lat_key and lon_key:
        try:
            raw_lat = float(d[lat_key])
            raw_lon = float(d[lon_key])
            valid, s_lat, s_lon = validate_coordinates(raw_lat, raw_lon)
            if valid:
                results.append({
                    "lat": s_lat,
                    "lon": s_lon,
                    "title": str(title) if title else "Signet Apple Maps",
                    "date": date_val,
                    "raw": d
                })
        except Exception:
            pass

    # Recurse into children
    for k, v in d.items():
        sub_title = title if title else (k if isinstance(k, str) else None)
        if isinstance(v, dict):
            _find_coords_in_dict(v, results, sub_title)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    _find_coords_in_dict(item, results, sub_title)

def parse_geobookmarks_plist(plist_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
    """
    Parses iOS GeoBookmarks.plist (binary plist or XML).
    """
    points: List[ForensicLocationPoint] = []
    if not os.path.exists(plist_path):
        return points

    try:
        with open(plist_path, "rb") as f:
            data = plistlib.load(f)

        raw_items = []
        if isinstance(data, dict):
            _find_coords_in_dict(data, raw_items)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    _find_coords_in_dict(item, raw_items)

        for it in raw_items:
            ts_utc, ts_loc, ep = parse_forensic_timestamp(it.get("date"), hint_os="iOS")
            points.append(ForensicLocationPoint(
                latitude=it["lat"],
                longitude=it["lon"],
                accuracy=10.0,
                timestamp_raw=it.get("date"),
                timestamp_utc=ts_utc,
                timestamp_local=ts_loc,
                epoch_type=ep,
                source_file=source_display_path,
                source_type="Apple Maps (GeoBookmarks)",
                category="navigation",
                table_or_field="GeoBookmarks.plist",
                device_os="iOS",
                confidence="high",
                extra_data={
                    "Nom_Lieu": it["title"][:100],
                    "Source": "Favoris & Signets Apple Maps"
                }
            ))
    except Exception:
        pass

    return points
