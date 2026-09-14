# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Android Google Location & Fused Location Parser
Extracts coordinates from gservices.db, location.db, fused_location, and android location providers.
"""
import sqlite3
import os
from typing import List
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import validate_coordinates

def parse_android_location_db(db_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
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
                
                lat_col = next((c for c in cols if c in ("latitude", "lat", "latitude_e7", "lat_e7")), None)
                lon_col = next((c for c in cols if c in ("longitude", "lon", "lng", "longitude_e7", "lon_e7", "lng_e7")), None)
                time_col = next((c for c in cols if "time" in c or "date" in c or "timestamp" in c), None)
                acc_col = next((c for c in cols if "accuracy" in c or "acc" in c or "precision" in c), None)
                alt_col = next((c for c in cols if "altitude" in c or "alt" in c), None)
                speed_col = next((c for c in cols if "speed" in c), None)
                bearing_col = next((c for c in cols if "bearing" in c or "heading" in c), None)
                provider_col = next((c for c in cols if "provider" in c or "source" in c), None)
                
                if lat_col and lon_col:
                    cur.execute(f"SELECT * FROM {tbl}")
                    for row in cur.fetchall():
                        r_dict = {k.lower(): row[k] for k in row.keys()}
                        raw_lat = r_dict.get(lat_col)
                        raw_lon = r_dict.get(lon_col)
                        
                        if raw_lat is None or raw_lon is None:
                            continue
                            
                        # Handle Google E7 format (integer scaled by 10^7)
                        if "e7" in lat_col or (isinstance(raw_lat, (int, float)) and abs(raw_lat) > 1000):
                            raw_lat = float(raw_lat) / 1e7
                            raw_lon = float(raw_lon) / 1e7
                            
                        valid, s_lat, s_lon = validate_coordinates(raw_lat, raw_lon)
                        if valid:
                            raw_t = r_dict.get(time_col) if time_col else None
                            ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t, hint_os="Android")
                            provider = str(r_dict.get(provider_col, "FusedLocation"))
                            acc = r_dict.get(acc_col)
                            
                            category = "gps_fix"
                            if "wifi" in provider.lower():
                                category = "wifi"
                            elif "cell" in provider.lower() or "network" in provider.lower():
                                category = "cell_tower"
                                
                            points.append(ForensicLocationPoint(
                                latitude=s_lat,
                                longitude=s_lon,
                                altitude=r_dict.get(alt_col),
                                accuracy=float(acc) if acc else None,
                                speed=r_dict.get(speed_col),
                                bearing=r_dict.get(bearing_col),
                                timestamp_raw=raw_t,
                                timestamp_utc=ts_utc,
                                timestamp_local=ts_loc,
                                epoch_type=ep,
                                source_file=source_display_path,
                                source_type=f"Android Location ({tbl})",
                                category=category,
                                table_or_field=f"{tbl} ({lat_col})",
                                device_os="Android",
                                confidence="high" if (acc and float(acc) < 30) else "medium",
                                extra_data={
                                    "Provider": provider,
                                    "Table": tbl
                                }
                            ))
            except Exception:
                pass
                
        conn.close()
    except Exception:
        pass
        
    return points
