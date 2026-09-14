# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - iOS Photos.sqlite Parser
Extracts geolocation metadata from Apple Photos database (ZGENERICASSET).
"""
import sqlite3
import os
from typing import List
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import validate_coordinates

def parse_photos_db(db_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
    points: List[ForensicLocationPoint] = []
    if not os.path.exists(db_path):
        return points
        
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        
        target_table = next((t for t in tables if t.upper() in ("ZGENERICASSET", "ZASSET")), None)
        if target_table:
            cur.execute(f"PRAGMA table_info({target_table})")
            cols = [c[1] for c in cur.fetchall()]
            
            lat_col = next((c for c in cols if c.upper() in ("ZLATITUDE", "LATITUDE")), None)
            lon_col = next((c for c in cols if c.upper() in ("ZLONGITUDE", "LONGITUDE")), None)
            date_col = next((c for c in cols if c.upper() in ("ZDATECREATED", "ZADDEDDATE", "DATECREATED")), None)
            file_col = next((c for c in cols if c.upper() in ("ZFILENAME", "ZORIGINALFILENAME", "FILENAME")), None)
            dir_col = next((c for c in cols if c.upper() in ("ZDIRECTORY", "DIRECTORY")), None)
            
            if lat_col and lon_col:
                cur.execute(f"SELECT * FROM {target_table} WHERE {lat_col} IS NOT NULL AND {lat_col} != 0")
                for row in cur.fetchall():
                    lat, lon = row[lat_col], row[lon_col]
                    valid, s_lat, s_lon = validate_coordinates(lat, lon)
                    if valid:
                        raw_t = row[date_col] if date_col else None
                        ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t, hint_os="iOS")
                        fname = row[file_col] if file_col else "Photo"
                        fdir = row[dir_col] if dir_col else ""
                        
                        points.append(ForensicLocationPoint(
                            latitude=s_lat,
                            longitude=s_lon,
                            accuracy=10.0, # High precision photo GPS
                            timestamp_raw=raw_t,
                            timestamp_utc=ts_utc,
                            timestamp_local=ts_loc,
                            epoch_type=ep,
                            source_file=source_display_path,
                            source_type="iOS Photos.sqlite (Photo/Vidéo)",
                            category="exif_photo",
                            table_or_field=f"{target_table} ({lat_col}, {lon_col})",
                            device_os="iOS",
                            confidence="high",
                            extra_data={
                                "Nom_Fichier": str(fname),
                                "Repertoire": str(fdir)
                            }
                        ))
        conn.close()
    except Exception:
        pass
        
    return points
