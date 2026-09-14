# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Messaging Apps Geolocation Parser
Extracts shared & live locations from WhatsApp, Telegram, Signal, Snapchat, and Waze.
"""
import sqlite3
import os
from typing import List
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import validate_coordinates

def parse_messaging_db(db_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
    points: List[ForensicLocationPoint] = []
    if not os.path.exists(db_path):
        return points
        
    db_name = os.path.basename(db_path).lower()
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        
        # 1. WhatsApp iOS (ChatStorage.sqlite -> ZWAMESSAGE, ZWAMEDIAITEM)
        if "ZWAMESSAGE" in tables or "ZWAMEDIAITEM" in tables:
            try:
                # Case A: ZWAMEDIAITEM
                if "ZWAMEDIAITEM" in tables:
                    cur.execute("PRAGMA table_info(ZWAMEDIAITEM)")
                    cols = [c[1] for c in cur.fetchall()]
                    if "ZLATITUDE" in cols and "ZLONGITUDE" in cols:
                        cur.execute("""
                            SELECT ZLATITUDE, ZLONGITUDE, ZTITLE, ZMEDIAURL 
                            FROM ZWAMEDIAITEM 
                            WHERE ZLATITUDE IS NOT NULL AND ZLATITUDE != 0
                        """)
                        for row in cur.fetchall():
                            lat, lon = row["ZLATITUDE"], row["ZLONGITUDE"]
                            valid, s_lat, s_lon = validate_coordinates(lat, lon)
                            if valid:
                                points.append(ForensicLocationPoint(
                                    latitude=s_lat,
                                    longitude=s_lon,
                                    accuracy=20.0,
                                    source_file=source_display_path,
                                    source_type="WhatsApp iOS (Position Partagée)",
                                    category="messaging",
                                    table_or_field="ZWAMEDIAITEM (ZLATITUDE)",
                                    device_os="iOS",
                                    confidence="high",
                                    extra_data={
                                        "Titre_Lieu": row["ZTITLE"] or "Position WhatsApp",
                                        "Media_URL": row["ZMEDIAURL"] or ""
                                    }
                                ))
            except Exception:
                pass
                
        # 2. WhatsApp Android (msgstore.db -> messages, message_location)
        if "messages" in tables or "message_location" in tables:
            try:
                # Look for message_location table
                if "message_location" in tables:
                    cur.execute("PRAGMA table_info(message_location)")
                    cols = [c[1].lower() for c in cur.fetchall()]
                    lat_col = next((c for c in cols if "lat" in c), None)
                    lon_col = next((c for c in cols if "lon" in c or "lng" in c), None)
                    name_col = next((c for c in cols if "name" in c or "label" in c), None)
                    if lat_col and lon_col:
                        cur.execute(f"SELECT * FROM message_location WHERE {lat_col} IS NOT NULL AND {lat_col} != 0")
                        for row in cur.fetchall():
                            r_dict = {k.lower(): row[k] for k in row.keys()}
                            lat, lon = r_dict.get(lat_col), r_dict.get(lon_col)
                            valid, s_lat, s_lon = validate_coordinates(lat, lon)
                            if valid:
                                points.append(ForensicLocationPoint(
                                    latitude=s_lat,
                                    longitude=s_lon,
                                    accuracy=20.0,
                                    source_file=source_display_path,
                                    source_type="WhatsApp Android (Position Partagée)",
                                    category="messaging",
                                    table_or_field=f"message_location ({lat_col})",
                                    device_os="Android",
                                    confidence="high",
                                    extra_data={
                                        "Nom_Lieu": r_dict.get(name_col) or "Position WhatsApp"
                                    }
                                ))
                # Fallback to messages table
                elif "messages" in tables:
                    cur.execute("PRAGMA table_info(messages)")
                    cols = [c[1].lower() for c in cur.fetchall()]
                    lat_col = next((c for c in cols if "lat" in c), None)
                    lon_col = next((c for c in cols if "lon" in c or "lng" in c), None)
                    time_col = next((c for c in cols if "timestamp" in c or "time" in c), None)
                    if lat_col and lon_col:
                        cur.execute(f"SELECT * FROM messages WHERE {lat_col} IS NOT NULL AND {lat_col} != 0")
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
                                    accuracy=20.0,
                                    timestamp_raw=raw_t,
                                    timestamp_utc=ts_utc,
                                    timestamp_local=ts_loc,
                                    epoch_type=ep,
                                    source_file=source_display_path,
                                    source_type="WhatsApp Android (Messages)",
                                    category="messaging",
                                    table_or_field=f"messages ({lat_col})",
                                    device_os="Android",
                                    confidence="high"
                                ))
            except Exception:
                pass
                
        # 3. Waze User Points & Favorite Locations
        if "user_places" in tables or "places" in tables or "favorites" in tables or "waze" in db_name:
            for tbl in tables:
                try:
                    cur.execute(f"PRAGMA table_info({tbl})")
                    cols = [c[1].lower() for c in cur.fetchall()]
                    lat_col = next((c for c in cols if "lat" in c), None)
                    lon_col = next((c for c in cols if "lon" in c or "lng" in c), None)
                    name_col = next((c for c in cols if "name" in c or "title" in c or "street" in c), None)
                    if lat_col and lon_col:
                        cur.execute(f"SELECT * FROM {tbl} WHERE {lat_col} IS NOT NULL AND {lat_col} != 0")
                        for row in cur.fetchall():
                            r_dict = {k.lower(): row[k] for k in row.keys()}
                            raw_lat = r_dict.get(lat_col)
                            raw_lon = r_dict.get(lon_col)
                            # Micro-degrees handling
                            if isinstance(raw_lat, (int, float)) and abs(raw_lat) > 1000:
                                raw_lat = float(raw_lat) / 1e6
                                raw_lon = float(raw_lon) / 1e6
                            valid, s_lat, s_lon = validate_coordinates(raw_lat, raw_lon)
                            if valid:
                                points.append(ForensicLocationPoint(
                                    latitude=s_lat,
                                    longitude=s_lon,
                                    accuracy=15.0,
                                    source_file=source_display_path,
                                    source_type=f"Waze ({tbl})",
                                    category="navigation",
                                    table_or_field=f"{tbl} ({lat_col})",
                                    device_os="Unknown",
                                    confidence="high",
                                    extra_data={
                                        "Lieu": r_dict.get(name_col) or "Destination Waze"
                                    }
                                ))
                except Exception:
                    pass

        conn.close()
    except Exception:
        pass
        
    return points
