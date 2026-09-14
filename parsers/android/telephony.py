# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Android Telephony Parser
Extracts cellular towers and network locations from telephony.db.
"""
import sqlite3
import os
from typing import List
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import validate_coordinates
from core.geocoder import resolve_cell_tower

def parse_android_telephony_db(db_path: str, source_display_path: str, mls_db_path: str = "MLS.db") -> List[ForensicLocationPoint]:
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
                
                # Check for direct coordinates
                lat_col = next((c for c in cols if "lat" in c), None)
                lon_col = next((c for c in cols if "lon" in c or "lng" in c), None)
                time_col = next((c for c in cols if "time" in c or "date" in c), None)
                
                mcc_col = next((c for c in cols if "mcc" in c), None)
                mnc_col = next((c for c in cols if "mnc" in c), None)
                lac_col = next((c for c in cols if "lac" in c or "area" in c or "tac" in c), None)
                cid_col = next((c for c in cols if "cid" in c or "cell" in c or "ci" in c), None)
                
                if lat_col and lon_col:
                    cur.execute(f"SELECT * FROM {tbl}")
                    for row in cur.fetchall():
                        r_dict = {k.lower(): row[k] for k in row.keys()}
                        lat, lon = r_dict.get(lat_col), r_dict.get(lon_col)
                        valid, s_lat, s_lon = validate_coordinates(lat, lon)
                        if valid:
                            raw_t = r_dict.get(time_col) if time_col else None
                            ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t, hint_os="Android")
                            
                            points.append(ForensicLocationPoint(
                                latitude=s_lat,
                                longitude=s_lon,
                                accuracy=1500.0,
                                timestamp_raw=raw_t,
                                timestamp_utc=ts_utc,
                                timestamp_local=ts_loc,
                                epoch_type=ep,
                                source_file=source_display_path,
                                source_type=f"Android Telephony ({tbl})",
                                category="cell_tower",
                                table_or_field=f"{tbl} ({lat_col})",
                                device_os="Android",
                                confidence="low",
                                extra_data={
                                    "MCC": r_dict.get(mcc_col),
                                    "MNC": r_dict.get(mnc_col),
                                    "LAC": r_dict.get(lac_col),
                                    "CID": r_dict.get(cid_col),
                                    "Table": tbl
                                }
                            ))
                # If no lat/lon but cell identifiers exist, resolve against MLS if available
                elif mcc_col and mnc_col and lac_col and cid_col and os.path.exists(mls_db_path):
                    cur.execute(f"SELECT * FROM {tbl}")
                    for row in cur.fetchall():
                        r_dict = {k.lower(): row[k] for k in row.keys()}
                        mcc, mnc, lac, cid = r_dict.get(mcc_col), r_dict.get(mnc_col), r_dict.get(lac_col), r_dict.get(cid_col)
                        if mcc and mnc and lac and cid:
                            lat, lon, rng = resolve_cell_tower(mcc, mnc, lac, cid, mls_db_path)
                            valid, s_lat, s_lon = validate_coordinates(lat, lon)
                            if valid:
                                raw_t = r_dict.get(time_col) if time_col else None
                                ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t, hint_os="Android")
                                points.append(ForensicLocationPoint(
                                    latitude=s_lat,
                                    longitude=s_lon,
                                    accuracy=rng or 1500.0,
                                    timestamp_raw=raw_t,
                                    timestamp_utc=ts_utc,
                                    timestamp_local=ts_loc,
                                    epoch_type=ep,
                                    source_file=source_display_path,
                                    source_type="Android Cell Tower (MLS Lookup)",
                                    category="cell_tower",
                                    table_or_field=f"{tbl} ({mcc}-{mnc}-{lac}-{cid})",
                                    device_os="Android",
                                    confidence="low",
                                    extra_data={
                                        "MCC": mcc,
                                        "MNC": mnc,
                                        "LAC": lac,
                                        "CID": cid,
                                        "MLS_Range_m": rng
                                    }
                                ))
            except Exception:
                pass
                
        conn.close()
    except Exception:
        pass
        
    return points
