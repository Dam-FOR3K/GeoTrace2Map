# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - iOS Cache.sqlite Parser
Extracts coordinates from CFNetwork / NSURLCache (cfurl_cache_response, cfurl_cache_receiver_data)
and legacy locationd Cache.sqlite databases.
"""
import sqlite3
import os
import re
import math
import urllib.parse
from typing import List
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import validate_coordinates

# Regex patterns for coordinates in request URLs
COORD_URL_PATTERNS = [
    # lat=...&lon=...
    re.compile(r'[?&](?:latitude|lat)=([+-]?\d+\.\d{3,})[^\s&]*&[^\s&]*(?:longitude|lon|lng)=([+-]?\d+\.\d{3,})', re.IGNORECASE),
    # lon=...&lat=...
    re.compile(r'[?&](?:longitude|lon|lng)=([+-]?\d+\.\d{3,})[^\s&]*&[^\s&]*(?:latitude|lat)=([+-]?\d+\.\d{3,})', re.IGNORECASE),
    # center=lat,lon or loc=lat,lon or ll=lat,lon or point=lat,lon
    re.compile(r'[?&](?:center|loc|ll|latlng|point|near|saddr|daddr|coords?)=([+-]?\d+\.\d{3,})[,%2C]([+-]?\d+\.\d{3,})', re.IGNORECASE),
    # Google Maps URL pattern: /@lat,lon
    re.compile(r'/@([+-]?\d+\.\d{3,}),([+-]?\d+\.\d{3,})', re.IGNORECASE),
]

# Regex for slippy map tiles: /z/x/y.(png|jpg|pbf)
TILE_URL_PATTERN = re.compile(r'/(?:tiles?|maps?|v4|v3|osm|standard)/(\d{1,2})/(\d+)/(\d+)(?:\.(?:png|jpg|jpeg|pbf|mvt|webp)|\b)', re.IGNORECASE)

# Regex for coordinates inside JSON / text blobs
JSON_COORD_PATTERN = re.compile(r'["\'](?:latitude|lat)["\']\s*:\s*([+-]?\d+\.\d{3,})\s*,\s*["\'](?:longitude|lon|lng)["\']\s*:\s*([+-]?\d+\.\d{3,})', re.IGNORECASE)

def _tile_to_latlon(z: int, x: int, y: int):
    """Converts Slippy Map tile numbers (z, x, y) to center latitude and longitude."""
    try:
        n = 2.0 ** z
        lon_deg = (x + 0.5) / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * (y + 0.5) / n)))
        lat_deg = math.degrees(lat_rad)
        return lat_deg, lon_deg
    except Exception:
        return None, None

def parse_ios_cache_sqlite(db_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
    """
    Parses iOS Cache.sqlite databases:
    1. CFNetwork NSURLCache (cfurl_cache_response, request_key URLs, receiver_data blobs)
    2. Legacy locationd Cache.sqlite (CellLocation, WifiLocation)
    """
    points: List[ForensicLocationPoint] = []
    if not os.path.exists(db_path):
        return points

    # ==========================================================
    # Step 1: Forensic Carving of accompanying Write-Ahead Log (-wal)
    # Read WAL binary BEFORE SQLite connection can truncate or checkpoint it
    # ==========================================================
    seen_coords = set()
    wal_candidates = [
        db_path + "-wal",
        os.path.splitext(db_path)[0] + ".sqlite-wal",
        os.path.splitext(db_path)[0] + "-wal"
    ]
    for w_path in wal_candidates:
        if os.path.exists(w_path) and os.path.getsize(w_path) > 0:
            carved_pts = _carve_wal_file(w_path, source_display_path, seen_coords)
            if carved_pts:
                points.extend(carved_pts)
            break

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Force passive WAL checkpoint to merge any pending journal frames
        try:
            cur.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception:
            pass

        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = set(r[0] for r in cur.fetchall())

        # ==========================================================
        # Case A: CFNetwork NSURLCache (cfurl_cache_response)
        # ==========================================================
        if "cfurl_cache_response" in tables:
            cur.execute("PRAGMA table_info(cfurl_cache_response)")
            cols = [c[1].lower() for c in cur.fetchall()]
            
            has_request_key = "request_key" in cols
            time_col = "time_stamp" if "time_stamp" in cols else None

            if has_request_key:
                cur.execute("SELECT * FROM cfurl_cache_response WHERE request_key IS NOT NULL LIMIT 20000")
                for row in cur.fetchall():
                    raw_url = row["request_key"]
                    if not raw_url or len(raw_url) < 10:
                        continue

                    raw_t = row[time_col] if time_col else None
                    ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t, hint_os="iOS")

                    try:
                        decoded_url = urllib.parse.unquote(raw_url)
                    except Exception:
                        decoded_url = raw_url

                    found_coords = False
                    for idx, pat in enumerate(COORD_URL_PATTERNS):
                        m = pat.search(decoded_url)
                        if m:
                            if idx == 1:
                                raw_lon, raw_lat = float(m.group(1)), float(m.group(2))
                            else:
                                raw_lat, raw_lon = float(m.group(1)), float(m.group(2))

                            valid, s_lat, s_lon = validate_coordinates(raw_lat, raw_lon)
                            if valid:
                                points.append(ForensicLocationPoint(
                                    latitude=s_lat,
                                    longitude=s_lon,
                                    accuracy=25.0,
                                    timestamp_raw=raw_t,
                                    timestamp_utc=ts_utc,
                                    timestamp_local=ts_loc,
                                    epoch_type=ep,
                                    source_file=source_display_path,
                                    source_type="iOS Cache.sqlite (NSURLCache Request)",
                                    category="system_routine",
                                    table_or_field="cfurl_cache_response (request_key)",
                                    device_os="iOS",
                                    confidence="high",
                                    extra_data={
                                        "URL_Requete": raw_url[:200],
                                        "Table": "cfurl_cache_response"
                                    }
                                ))
                                found_coords = True
                                break

                    if not found_coords:
                        tile_m = TILE_URL_PATTERN.search(decoded_url)
                        if tile_m:
                            z = int(tile_m.group(1))
                            x = int(tile_m.group(2))
                            y = int(tile_m.group(3))
                            if 8 <= z <= 19:
                                t_lat, t_lon = _tile_to_latlon(z, x, y)
                                if t_lat is not None:
                                    valid, s_lat, s_lon = validate_coordinates(t_lat, t_lon)
                                    if valid:
                                        approx_acc = round(40075016.686 * math.cos(math.radians(s_lat)) / (2 ** z) * 0.5)
                                        points.append(ForensicLocationPoint(
                                            latitude=s_lat,
                                            longitude=s_lon,
                                            accuracy=float(approx_acc),
                                            timestamp_raw=raw_t,
                                            timestamp_utc=ts_utc,
                                            timestamp_local=ts_loc,
                                            epoch_type=ep,
                                            source_file=source_display_path,
                                            source_type="iOS Cache.sqlite (Map Tile Cache)",
                                            category="system_routine",
                                            table_or_field="cfurl_cache_response (tile)",
                                            device_os="iOS",
                                            confidence="medium",
                                            extra_data={
                                                "Tile_Zoom": z,
                                                "Tile_X": x,
                                                "Tile_Y": y,
                                                "URL": raw_url[:150],
                                                "Table": "cfurl_cache_response"
                                            }
                                        ))

            if "cfurl_cache_receiver_data" in tables:
                try:
                    cur.execute("SELECT entry_ID, receiver_data FROM cfurl_cache_receiver_data WHERE receiver_data IS NOT NULL LIMIT 500")
                    for r_row in cur.fetchall():
                        blob = r_row["receiver_data"]
                        if isinstance(blob, bytes) and len(blob) > 20:
                            text_snippet = blob[:4096].decode('utf-8', errors='ignore')
                            m_json = JSON_COORD_PATTERN.search(text_snippet)
                            if m_json:
                                j_lat, j_lon = float(m_json.group(1)), float(m_json.group(2))
                                valid, s_lat, s_lon = validate_coordinates(j_lat, j_lon)
                                if valid:
                                    points.append(ForensicLocationPoint(
                                        latitude=s_lat,
                                        longitude=s_lon,
                                        accuracy=50.0,
                                        timestamp_raw=None,
                                        timestamp_utc=None,
                                        timestamp_local=None,
                                        epoch_type=None,
                                        source_file=source_display_path,
                                        source_type="iOS Cache.sqlite (Receiver Data Blob)",
                                        category="system_routine",
                                        table_or_field="cfurl_cache_receiver_data",
                                        device_os="iOS",
                                        confidence="medium",
                                        extra_data={
                                            "Entry_ID": r_row["entry_ID"],
                                            "Table": "cfurl_cache_receiver_data"
                                        }
                                    ))
                except Exception:
                    pass

        # ==========================================================
        # Case B: Legacy iOS locationd Cache.sqlite / consolidated.db
        # ==========================================================
        loc_tables = [t for t in tables if any(k in t.lower() for k in ("wifilocation", "celllocation", "location", "cdmacell", "ltecell", "gsmcell"))]
        if loc_tables:
            from parsers.ios.locationd import parse_locationd_db
            loc_pts = parse_locationd_db(db_path, source_display_path)
            if loc_pts:
                points.extend(loc_pts)

        conn.close()
    except Exception:
        pass

    # ==========================================================
    # Case C: Fallback to generic SQLite scraper if no points yet
    # ==========================================================
    if not points:
        from parsers.generic.sqlite_scraper import scrape_generic_sqlite
        points = scrape_generic_sqlite(db_path, source_display_path, hint_os="iOS")

    return points

def _carve_wal_file(wal_path: str, source_display_path: str, seen_coords: set) -> List[ForensicLocationPoint]:
    """Carves uncommitted, deleted, or un-checkpointed URLs and coordinates from binary WAL frames."""
    carved: List[ForensicLocationPoint] = []
    try:
        with open(wal_path, "rb") as f:
            data = f.read()

        # Search for HTTP/HTTPS URLs inside WAL pages
        url_matches = re.finditer(rb'https?://[^\s\x00-\x1f\x7f-\xff"\'<>]{10,500}', data)
        for m in url_matches:
            try:
                raw_url = m.group(0).decode('utf-8', errors='ignore')
                decoded_url = urllib.parse.unquote(raw_url)
                for idx, pat in enumerate(COORD_URL_PATTERNS):
                    m_coord = pat.search(decoded_url)
                    if m_coord:
                        if idx == 1:
                            raw_lon, raw_lat = float(m_coord.group(1)), float(m_coord.group(2))
                        else:
                            raw_lat, raw_lon = float(m_coord.group(1)), float(m_coord.group(2))

                        valid, s_lat, s_lon = validate_coordinates(raw_lat, raw_lon)
                        coord_key = (round(s_lat, 5), round(s_lon, 5))
                        if valid and coord_key not in seen_coords:
                            seen_coords.add(coord_key)
                            carved.append(ForensicLocationPoint(
                                latitude=s_lat,
                                longitude=s_lon,
                                accuracy=35.0,
                                timestamp_raw=None,
                                timestamp_utc=None,
                                timestamp_local=None,
                                epoch_type=None,
                                source_file=source_display_path + "-wal",
                                source_type="iOS Cache.sqlite-wal (Carved WAL Frame)",
                                category="system_routine",
                                table_or_field="WAL Journal Frame (Carved)",
                                device_os="iOS",
                                confidence="medium",
                                extra_data={
                                    "Carved_URL": raw_url[:200],
                                    "Origine": "SQLite Write-Ahead Log (WAL)"
                                }
                            ))
                            break
            except Exception:
                continue
    except Exception:
        pass
    return carved
