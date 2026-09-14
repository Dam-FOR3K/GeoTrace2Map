# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Generic Heuristic SQLite Scraper
Discovers and extracts geolocation data from any unknown SQLite database table.
"""
import sqlite3
import os
from typing import List
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import validate_coordinates

def scrape_generic_sqlite(db_path: str, source_display_path: str, hint_os: str = "Unknown") -> List[ForensicLocationPoint]:
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
            # Skip sqlite system tables
            if tbl.startswith("sqlite_"):
                continue
                
            try:
                cur.execute(f"PRAGMA table_info('{tbl}')")
                cols_info = cur.fetchall()
                cols = [c[1] for c in cols_info]
                cols_lower = [c.lower() for c in cols]
                
                # Match lat/lon columns
                lat_candidates = [cols[i] for i, c in enumerate(cols_lower) if any(k in c for k in ("latitude", "lat", "y_coord", "coord_y")) and not any(ign in c for k in ("delta", "span", "accuracy", "err") for ign in (k,))]
                lon_candidates = [cols[i] for i, c in enumerate(cols_lower) if any(k in c for k in ("longitude", "lon", "lng", "long", "x_coord", "coord_x")) and not any(ign in c for k in ("delta", "span", "accuracy", "err") for ign in (k,))]
                
                if not lat_candidates or not lon_candidates:
                    continue
                    
                lat_col = lat_candidates[0]
                lon_col = lon_candidates[0]
                
                # Look for time, accuracy, alt, name columns
                time_col = next((cols[i] for i, c in enumerate(cols_lower) if any(k in c for k in ("time", "date", "timestamp", "created", "added", "entry", "fix"))), None)
                acc_col = next((cols[i] for i, c in enumerate(cols_lower) if any(k in c for k in ("accuracy", "precision", "radius", "uncertainty", "acc", "horiz"))), None)
                alt_col = next((cols[i] for i, c in enumerate(cols_lower) if any(k in c for k in ("alt", "altitude", "elevation", "height"))), None)
                speed_col = next((cols[i] for i, c in enumerate(cols_lower) if any(k in c for k in ("speed", "velocity"))), None)
                bearing_col = next((cols[i] for i, c in enumerate(cols_lower) if any(k in c for k in ("bearing", "heading", "course", "direction"))), None)
                name_col = next((cols[i] for i, c in enumerate(cols_lower) if any(k in c for k in ("name", "title", "label", "text", "description", "address"))), None)
                
                cur.execute(f"SELECT * FROM '{tbl}' WHERE [{lat_col}] IS NOT NULL AND [{lat_col}] != 0 LIMIT 10000")
                for row in cur.fetchall():
                    raw_lat = row[lat_col]
                    raw_lon = row[lon_col]
                    
                    if raw_lat is None or raw_lon is None:
                        continue
                        
                    # Handle integer E6 / E7 scaling
                    if isinstance(raw_lat, (int, float)):
                        if abs(raw_lat) > 10000000:
                            raw_lat = float(raw_lat) / 1e7
                            raw_lon = float(raw_lon) / 1e7
                        elif 1000 < abs(raw_lat) <= 10000000:
                            raw_lat = float(raw_lat) / 1e6
                            raw_lon = float(raw_lon) / 1e6
                            
                    valid, s_lat, s_lon = validate_coordinates(raw_lat, raw_lon)
                    if valid:
                        raw_t = row[time_col] if time_col else None
                        ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t, hint_os=hint_os)
                        acc_val = row[acc_col] if acc_col else None
                        name_val = row[name_col] if name_col else None
                        
                        extra = {"Table": tbl}
                        if name_val:
                            extra["Nom/Detail"] = str(name_val)[:100]
                            
                        points.append(ForensicLocationPoint(
                            latitude=s_lat,
                            longitude=s_lon,
                            altitude=float(row[alt_col]) if alt_col and row[alt_col] is not None else None,
                            accuracy=float(acc_val) if acc_val is not None else None,
                            speed=float(row[speed_col]) if speed_col and row[speed_col] is not None else None,
                            bearing=float(row[bearing_col]) if bearing_col and row[bearing_col] is not None else None,
                            timestamp_raw=raw_t,
                            timestamp_utc=ts_utc,
                            timestamp_local=ts_loc,
                            epoch_type=ep,
                            source_file=source_display_path,
                            source_type=f"SQLite Générique ({tbl})",
                            category="generic",
                            table_or_field=f"{tbl} ({lat_col}, {lon_col})",
                            device_os=hint_os,
                            confidence="medium",
                            extra_data=extra
                        ))
            except Exception:
                pass
                
        conn.close()
    except Exception:
        pass
        
    return points
