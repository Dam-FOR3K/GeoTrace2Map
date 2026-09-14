# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - iOS locationd Cache Parser
Parses cache_encryptedA.db, lockCache_encryptedA.db, cache_encryptedB.db (Cell towers, Wi-Fi spots, GPS fixes).
"""
import sqlite3
import os
from typing import List
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import validate_coordinates

def parse_locationd_db(db_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
    points: List[ForensicLocationPoint] = []
    if not os.path.exists(db_path):
        return points
        
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        
        # 1. WifiLocation / WifiHarvest
        wifi_tables = [t for t in tables if "wifi" in t.lower()]
        for wtable in wifi_tables:
            try:
                cur.execute(f"PRAGMA table_info({wtable})")
                cols = [c[1].lower() for c in cur.fetchall()]
                
                lat_col = next((c for c in cols if "latitude" in c), None)
                lon_col = next((c for c in cols if "longitude" in c), None)
                mac_col = next((c for c in cols if "mac" in c or "bssid" in c), None)
                time_col = next((c for c in cols if "time" in c or "date" in c), None)
                acc_col = next((c for c in cols if "accuracy" in c or "confidence" in c or "reach" in c), None)
                
                if lat_col and lon_col:
                    cur.execute(f"SELECT * FROM {wtable}")
                    for row in cur.fetchall():
                        r_dict = {k.lower(): row[k] for k in row.keys()}
                        lat, lon = r_dict.get(lat_col), r_dict.get(lon_col)
                        valid, s_lat, s_lon = validate_coordinates(lat, lon)
                        if valid:
                            raw_t = r_dict.get(time_col) if time_col else None
                            ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t, hint_os="iOS")
                            mac_addr = r_dict.get(mac_col) if mac_col else None
                            acc = r_dict.get(acc_col) if acc_col else 50.0
                            
                            points.append(ForensicLocationPoint(
                                latitude=s_lat,
                                longitude=s_lon,
                                accuracy=float(acc) if acc else 50.0,
                                timestamp_raw=raw_t,
                                timestamp_utc=ts_utc,
                                timestamp_local=ts_loc,
                                epoch_type=ep,
                                source_file=source_display_path,
                                source_type=f"iOS locationd ({wtable})",
                                category="wifi",
                                table_or_field=wtable,
                                device_os="iOS",
                                confidence="medium",
                                extra_data={
                                    "BSSID_MAC": str(mac_addr) if mac_addr else "Inconnu",
                                    "Table": wtable
                                }
                            ))
            except Exception:
                pass

        # 2. Cellular Tables (CdmaCellLocation, LteCellLocation, GsmCellLocation, CellLocation)
        cell_tables = [t for t in tables if "cell" in t.lower() or "lte" in t.lower() or "gsm" in t.lower() or "cdma" in t.lower()]
        for ctable in cell_tables:
            try:
                cur.execute(f"PRAGMA table_info({ctable})")
                cols = [c[1].lower() for c in cur.fetchall()]
                lat_col = next((c for c in cols if "latitude" in c), None)
                lon_col = next((c for c in cols if "longitude" in c), None)
                time_col = next((c for c in cols if "time" in c or "date" in c), None)
                cid_col = next((c for c in cols if "cell" in c or "ci" in c), None)
                lac_col = next((c for c in cols if "area" in c or "lac" in c or "tac" in c), None)
                mcc_col = next((c for c in cols if "mcc" in c), None)
                mnc_col = next((c for c in cols if "mnc" in c), None)
                
                if lat_col and lon_col:
                    cur.execute(f"SELECT * FROM {ctable}")
                    for row in cur.fetchall():
                        r_dict = {k.lower(): row[k] for k in row.keys()}
                        lat, lon = r_dict.get(lat_col), r_dict.get(lon_col)
                        valid, s_lat, s_lon = validate_coordinates(lat, lon)
                        if valid:
                            raw_t = r_dict.get(time_col) if time_col else None
                            ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t, hint_os="iOS")
                            
                            points.append(ForensicLocationPoint(
                                latitude=s_lat,
                                longitude=s_lon,
                                accuracy=1000.0, # Typical cell radius
                                timestamp_raw=raw_t,
                                timestamp_utc=ts_utc,
                                timestamp_local=ts_loc,
                                epoch_type=ep,
                                source_file=source_display_path,
                                source_type=f"iOS locationd ({ctable})",
                                category="cell_tower",
                                table_or_field=ctable,
                                device_os="iOS",
                                confidence="low",
                                extra_data={
                                    "MCC": r_dict.get(mcc_col),
                                    "MNC": r_dict.get(mnc_col),
                                    "LAC_TAC": r_dict.get(lac_col),
                                    "CellID": r_dict.get(cid_col),
                                    "Table": ctable
                                }
                            ))
            except Exception:
                pass
                
        # 3. Location / IndoorLocation / Harvest tables
        other_loc_tables = [t for t in tables if t not in wifi_tables and t not in cell_tables and ("loc" in t.lower() or "pos" in t.lower())]
        for ltable in other_loc_tables:
            try:
                cur.execute(f"PRAGMA table_info({ltable})")
                cols = [c[1].lower() for c in cur.fetchall()]
                lat_col = next((c for c in cols if "latitude" in c), None)
                lon_col = next((c for c in cols if "longitude" in c), None)
                time_col = next((c for c in cols if "time" in c or "date" in c), None)
                acc_col = next((c for c in cols if "accuracy" in c or "horiz" in c), None)
                alt_col = next((c for c in cols if "alt" in c), None)
                speed_col = next((c for c in cols if "speed" in c), None)
                course_col = next((c for c in cols if "course" in c or "heading" in c), None)
                
                if lat_col and lon_col:
                    cur.execute(f"SELECT * FROM {ltable}")
                    for row in cur.fetchall():
                        r_dict = {k.lower(): row[k] for k in row.keys()}
                        lat, lon = r_dict.get(lat_col), r_dict.get(lon_col)
                        valid, s_lat, s_lon = validate_coordinates(lat, lon)
                        if valid:
                            raw_t = r_dict.get(time_col) if time_col else None
                            ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t, hint_os="iOS")
                            acc = r_dict.get(acc_col)
                            
                            points.append(ForensicLocationPoint(
                                latitude=s_lat,
                                longitude=s_lon,
                                altitude=r_dict.get(alt_col),
                                accuracy=float(acc) if acc else None,
                                speed=r_dict.get(speed_col),
                                bearing=r_dict.get(course_col),
                                timestamp_raw=raw_t,
                                timestamp_utc=ts_utc,
                                timestamp_local=ts_loc,
                                epoch_type=ep,
                                source_file=source_display_path,
                                source_type=f"iOS locationd ({ltable})",
                                category="gps_fix",
                                table_or_field=ltable,
                                device_os="iOS",
                                confidence="high" if (acc and float(acc) < 30) else "medium"
                            ))
            except Exception:
                pass

        conn.close()
    except Exception:
        pass
        
    return points
