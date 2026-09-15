# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Messaging Apps Geolocation Parser
Extracts shared & live locations from WhatsApp, Telegram, Signal, Snapchat, and Waze.
"""
import sqlite3
import os
import re
import urllib.parse
from typing import List
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import validate_coordinates

COORD_TEXT_PATTERNS = [
    re.compile(r'https?://(?:maps\.apple\.com|maps\.google\.com|goo\.gl/maps|google\.com/maps|waze\.com)[^\s"\'<>]+', re.IGNORECASE),
    re.compile(r'geo:([+-]?\d+\.\d{3,}),([+-]?\d+\.\d{3,})', re.IGNORECASE),
    re.compile(r'[?&](?:latitude|lat)=([+-]?\d+\.\d{3,})[^\s&]*&[^\s&]*(?:longitude|lon|lng)=([+-]?\d+\.\d{3,})', re.IGNORECASE),
    re.compile(r'[?&](?:q|loc|ll|center|near)=([+-]?\d+\.\d{3,})[,%2C]([+-]?\d+\.\d{3,})', re.IGNORECASE),
    re.compile(r'/@([+-]?\d+\.\d{3,}),([+-]?\d+\.\d{3,})', re.IGNORECASE),
]

def _extract_coords_from_message_text(text: str, date_val, source_file: str, source_label: str, os_hint: str) -> List[ForensicLocationPoint]:
    pts = []
    if not text or len(text) < 8:
        return pts
    decoded = urllib.parse.unquote(text)
    for pat in COORD_TEXT_PATTERNS:
        m = pat.search(decoded)
        if m:
            groups = m.groups()
            if len(groups) == 2:
                try:
                    lat, lon = float(groups[0]), float(groups[1])
                    valid, s_lat, s_lon = validate_coordinates(lat, lon)
                    if valid:
                        ts_utc, ts_loc, ep = parse_forensic_timestamp(date_val, hint_os=os_hint)
                        pts.append(ForensicLocationPoint(
                            latitude=s_lat,
                            longitude=s_lon,
                            accuracy=20.0,
                            timestamp_raw=date_val,
                            timestamp_utc=ts_utc,
                            timestamp_local=ts_loc,
                            epoch_type=ep,
                            source_file=source_file,
                            source_type=source_label,
                            category="messaging",
                            table_or_field="Message Content (Shared Location)",
                            device_os=os_hint,
                            confidence="high",
                            extra_data={
                                "Extrait_Message": text[:150],
                                "Type": "Partage de Position SMS/Chat"
                            }
                        ))
                        break
                except Exception:
                    pass
            elif m.group(0).startswith("http"):
                # Nested search inside the URL
                for sub_pat in COORD_TEXT_PATTERNS[2:]:
                    sub_m = sub_pat.search(decoded)
                    if sub_m:
                        try:
                            lat, lon = float(sub_m.group(1)), float(sub_m.group(2))
                            valid, s_lat, s_lon = validate_coordinates(lat, lon)
                            if valid:
                                ts_utc, ts_loc, ep = parse_forensic_timestamp(date_val, hint_os=os_hint)
                                pts.append(ForensicLocationPoint(
                                    latitude=s_lat,
                                    longitude=s_lon,
                                    accuracy=20.0,
                                    timestamp_raw=date_val,
                                    timestamp_utc=ts_utc,
                                    timestamp_local=ts_loc,
                                    epoch_type=ep,
                                    source_file=source_file,
                                    source_type=source_label,
                                    category="messaging",
                                    table_or_field="Message URL (Shared Location)",
                                    device_os=os_hint,
                                    confidence="high",
                                    extra_data={
                                        "Lien_Partage": m.group(0)[:150],
                                        "Type": "Lien Cartographique"
                                    }
                                ))
                                break
                        except Exception:
                            pass
                break
    return pts

def parse_messaging_db(db_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
    points: List[ForensicLocationPoint] = []
    if not os.path.exists(db_path):
        return points
        
    db_name = os.path.basename(db_path).lower()
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        try:
            cur.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception:
            pass
        
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

        # 4. SMS/iMessage iOS (sms.db -> message.text, date)
        if "message" in tables and "handle" in tables:
            try:
                cur.execute("SELECT text, date FROM message WHERE text IS NOT NULL AND length(text) > 8 LIMIT 20000")
                for row in cur.fetchall():
                    txt = row["text"]
                    d_val = row["date"]
                    pts = _extract_coords_from_message_text(txt, d_val, source_display_path, "SMS / iMessage iOS", "iOS")
                    if pts:
                        points.extend(pts)
            except Exception:
                pass

        # 5. SMS/MMS Android (mmssms.db -> sms.body, part.text)
        if "sms" in tables and any(c in tables for c in ("pdu", "threads", "words")):
            try:
                cur.execute("SELECT body, date FROM sms WHERE body IS NOT NULL AND length(body) > 8 LIMIT 20000")
                for row in cur.fetchall():
                    txt = row["body"]
                    d_val = row["date"]
                    pts = _extract_coords_from_message_text(txt, d_val, source_display_path, "SMS Android", "Android")
                    if pts:
                        points.extend(pts)
            except Exception:
                pass

        if "part" in tables:
            try:
                cur.execute("SELECT text, date FROM part WHERE text IS NOT NULL AND length(text) > 8 LIMIT 5000")
                for row in cur.fetchall():
                    txt = row["text"]
                    d_val = row["date"] if "date" in row.keys() else None
                    pts = _extract_coords_from_message_text(txt, d_val, source_display_path, "MMS Android", "Android")
                    if pts:
                        points.extend(pts)
            except Exception:
                pass

        conn.close()
    except Exception:
        pass
        
    return points
