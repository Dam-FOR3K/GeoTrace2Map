# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Web Browser History Geolocation Parser
Extracts navigation searches, Google Maps / Apple Maps URLs, and coordinates
from Safari (History.db) and Google Chrome (History).
"""
import sqlite3
import os
import re
import urllib.parse
from typing import List
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import validate_coordinates

COORD_URL_PATTERNS = [
    # lat=...&lon=...
    re.compile(r'[?&](?:latitude|lat)=([+-]?\d+\.\d{3,})[^\s&]*&[^\s&]*(?:longitude|lon|lng)=([+-]?\d+\.\d{3,})', re.IGNORECASE),
    # lon=...&lat=...
    re.compile(r'[?&](?:longitude|lon|lng)=([+-]?\d+\.\d{3,})[^\s&]*&[^\s&]*(?:latitude|lat)=([+-]?\d+\.\d{3,})', re.IGNORECASE),
    # q=lat,lon or loc=lat,lon or ll=lat,lon or center=lat,lon
    re.compile(r'[?&](?:q|loc|ll|latlng|point|near|saddr|daddr|center)=([+-]?\d+\.\d{3,})[,%2C]([+-]?\d+\.\d{3,})', re.IGNORECASE),
    # Google Maps /@lat,lon
    re.compile(r'/@([+-]?\d+\.\d{3,}),([+-]?\d+\.\d{3,})', re.IGNORECASE),
    # geo:lat,lon
    re.compile(r'geo:([+-]?\d+\.\d{3,}),([+-]?\d+\.\d{3,})', re.IGNORECASE),
]

def parse_browser_history_db(db_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
    """
    Parses Safari (History.db) or Chrome (History) SQLite database for geographic URLs.
    """
    points: List[ForensicLocationPoint] = []
    if not os.path.exists(db_path):
        return points

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

        # Target: Safari (history_items, history_visits) or Chrome (urls)
        is_safari = "history_items" in tables
        is_chrome = "urls" in tables

        if is_safari:
            # Safari: history_items.url joined with history_visits.visit_time
            query = """
                SELECT i.url, i.domain_expansion, v.visit_time, v.title
                FROM history_items i
                LEFT JOIN history_visits v ON i.id = v.history_item
                WHERE i.url IS NOT NULL
                LIMIT 15000
            """
            cur.execute(query)
            for row in cur.fetchall():
                url_str = row["url"] or ""
                time_val = row["visit_time"]
                title = row["title"] or ""
                pts = _extract_coords_from_url(url_str, time_val, title, source_display_path, "Safari", "iOS")
                if pts:
                    points.extend(pts)

        elif is_chrome:
            # Chrome: urls (url, title, last_visit_time)
            query = """
                SELECT url, title, last_visit_time
                FROM urls
                WHERE url IS NOT NULL
                LIMIT 15000
            """
            cur.execute(query)
            for row in cur.fetchall():
                url_str = row["url"] or ""
                time_val = row["last_visit_time"]
                title = row["title"] or ""
                pts = _extract_coords_from_url(url_str, time_val, title, source_display_path, "Chrome", "Android")
                if pts:
                    points.extend(pts)

        conn.close()
    except Exception:
        pass

    return points

def _extract_coords_from_url(url_str: str, time_val, title: str, source_display: str, browser_name: str, os_hint: str) -> List[ForensicLocationPoint]:
    found = []
    try:
        decoded_url = urllib.parse.unquote(url_str)
    except Exception:
        decoded_url = url_str

    for idx, pat in enumerate(COORD_URL_PATTERNS):
        m = pat.search(decoded_url)
        if m:
            if idx == 1:
                raw_lon, raw_lat = float(m.group(1)), float(m.group(2))
            else:
                raw_lat, raw_lon = float(m.group(1)), float(m.group(2))

            valid, s_lat, s_lon = validate_coordinates(raw_lat, raw_lon)
            if valid:
                ts_utc, ts_loc, ep = parse_forensic_timestamp(time_val, hint_os=os_hint)
                found.append(ForensicLocationPoint(
                    latitude=s_lat,
                    longitude=s_lon,
                    accuracy=20.0,
                    timestamp_raw=time_val,
                    timestamp_utc=ts_utc,
                    timestamp_local=ts_loc,
                    epoch_type=ep,
                    source_file=source_display,
                    source_type=f"{browser_name} (Historique Web)",
                    category="navigation",
                    table_or_field=f"{browser_name} URL Search",
                    device_os=os_hint,
                    confidence="high",
                    extra_data={
                        "Titre": str(title)[:100] if title else "Recherche Carto Navigateur",
                        "URL": url_str[:250],
                        "Navigateur": browser_name
                    }
                ))
            break
    return found
