# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Apple Maps & GeoHistory Parser
Extracts navigation destinations, pinned locations, searches from Maps databases.
"""
import sqlite3
import os
from typing import List
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import validate_coordinates

def parse_apple_maps_db(db_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
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
                cols = [c[1] for c in cur.fetchall()]
                
                lat_col = next((c for c in cols if "lat" in c.lower()), None)
                lon_col = next((c for c in cols if "lon" in c.lower() or "lng" in c.lower()), None)
                time_col = next((c for c in cols if "time" in c.lower() or "date" in c.lower()), None)
                name_col = next((c for c in cols if "name" in c.lower() or "title" in c.lower() or "query" in c.lower() or "address" in c.lower()), None)
                
                if lat_col and lon_col:
                    cur.execute(f"SELECT * FROM {tbl} WHERE {lat_col} IS NOT NULL AND {lat_col} != 0")
                    for row in cur.fetchall():
                        lat, lon = row[lat_col], row[lon_col]
                        valid, s_lat, s_lon = validate_coordinates(lat, lon)
                        if valid:
                            raw_t = row[time_col] if time_col else None
                            ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t, hint_os="iOS")
                            place_name = row[name_col] if name_col else None
                            
                            points.append(ForensicLocationPoint(
                                latitude=s_lat,
                                longitude=s_lon,
                                accuracy=15.0,
                                timestamp_raw=raw_t,
                                timestamp_utc=ts_utc,
                                timestamp_local=ts_loc,
                                epoch_type=ep,
                                source_file=source_display_path,
                                source_type="iOS Apple Maps (Navigation / Recherche)",
                                category="navigation",
                                table_or_field=f"{tbl} ({lat_col})",
                                device_os="iOS",
                                confidence="high",
                                extra_data={
                                    "Nom_Lieu": str(place_name) if place_name else "Destination Maps",
                                    "Table": tbl
                                }
                            ))
            except Exception:
                pass
                
        conn.close()
    except Exception:
        pass
        
    return points
