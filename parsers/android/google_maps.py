# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Android Google Maps & Navigation Cache Parser
"""
import sqlite3
import os
from typing import List
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import validate_coordinates

def parse_android_maps_db(db_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
    points: List[ForensicLocationPoint] = []
    if not os.path.exists(db_path):
        return points
        
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        
        for tbl in tables:
            try:
                cur.execute(f"PRAGMA table_info({tbl})")
                cols = [c[1].lower() for c in cur.fetchall()]
                
                lat_col = next((c for c in cols if c in ("dest_lat", "latitude", "lat", "latitude_e6", "latitude_e7")), None)
                lon_col = next((c for c in cols if c in ("dest_lng", "dest_lon", "longitude", "lon", "lng", "longitude_e6", "longitude_e7")), None)
                time_col = next((c for c in cols if "time" in c or "date" in c or "timestamp" in c), None)
                title_col = next((c for c in cols if "title" in c or "name" in c or "query" in c or "dest_title" in c), None)
                
                if lat_col and lon_col:
                    cur.execute(f"SELECT * FROM {tbl}")
                    for row in cur.fetchall():
                        r_dict = {k.lower(): row[k] for k in row.keys()}
                        raw_lat = r_dict.get(lat_col)
                        raw_lon = r_dict.get(lon_col)
                        
                        if raw_lat is None or raw_lon is None:
                            continue
                            
                        # Handle E6 / E7 integer scale
                        if "e7" in lat_col or (isinstance(raw_lat, (int, float)) and abs(raw_lat) > 10000000):
                            raw_lat = float(raw_lat) / 1e7
                            raw_lon = float(raw_lon) / 1e7
                        elif "e6" in lat_col or (isinstance(raw_lat, (int, float)) and 1000 < abs(raw_lat) <= 10000000):
                            raw_lat = float(raw_lat) / 1e6
                            raw_lon = float(raw_lon) / 1e6
                            
                        valid, s_lat, s_lon = validate_coordinates(raw_lat, raw_lon)
                        if valid:
                            raw_t = r_dict.get(time_col) if time_col else None
                            ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t, hint_os="Android")
                            dest_name = r_dict.get(title_col)
                            
                            points.append(ForensicLocationPoint(
                                latitude=s_lat,
                                longitude=s_lon,
                                accuracy=15.0,
                                timestamp_raw=raw_t,
                                timestamp_utc=ts_utc,
                                timestamp_local=ts_loc,
                                epoch_type=ep,
                                source_file=source_display_path,
                                source_type=f"Android Google Maps ({tbl})",
                                category="navigation",
                                table_or_field=f"{tbl} ({lat_col})",
                                device_os="Android",
                                confidence="high",
                                extra_data={
                                    "Destination": str(dest_name) if dest_name else "Recherche Maps",
                                    "Table": tbl
                                }
                            ))
            except Exception:
                pass
                
        conn.close()
    except Exception:
        pass
        
    return points
