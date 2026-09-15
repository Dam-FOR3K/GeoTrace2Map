# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Android MediaProvider / MediaStore Parser
Extracts embedded GPS coordinates indexed by Android from external.db, internal.db, media.db.
"""
import sqlite3
import os
from typing import List
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import validate_coordinates

def parse_media_provider_db(db_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
    """
    Parses Android MediaProvider database (external.db, media.db)
    Extracts coordinates from 'files', 'images', and 'video' tables.
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

        # Target tables: files, images, video
        candidate_tables = [t for t in tables if t.lower() in ("files", "images", "video", "media")]

        for tbl in candidate_tables:
            try:
                cur.execute(f"PRAGMA table_info({tbl})")
                cols = [c[1].lower() for c in cur.fetchall()]

                lat_col = next((c for c in cols if c in ("latitude", "lat")), None)
                lon_col = next((c for c in cols if c in ("longitude", "lon", "lng")), None)

                if not lat_col or not lon_col:
                    continue

                time_col = next((c for c in cols if c in ("datetaken", "date_added", "date_modified")), None)
                data_col = next((c for c in cols if c in ("_data", "relative_path", "data")), None)
                title_col = next((c for c in cols if c in ("_display_name", "title", "name")), None)
                mime_col = next((c for c in cols if c in ("mime_type", "format")), None)

                query = f"SELECT * FROM {tbl} WHERE {lat_col} IS NOT NULL AND {lat_col} != 0 AND {lon_col} IS NOT NULL AND {lon_col} != 0 LIMIT 10000"
                cur.execute(query)

                for row in cur.fetchall():
                    r_dict = {k.lower(): row[k] for k in row.keys()}
                    raw_lat = r_dict.get(lat_col)
                    raw_lon = r_dict.get(lon_col)

                    valid, s_lat, s_lon = validate_coordinates(raw_lat, raw_lon)
                    if valid:
                        raw_t = r_dict.get(time_col) if time_col else None
                        ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t, hint_os="Android")
                        file_path = r_dict.get(data_col) or ""
                        display_name = r_dict.get(title_col) or os.path.basename(str(file_path))
                        mime = r_dict.get(mime_col) or "image/jpeg"

                        points.append(ForensicLocationPoint(
                            latitude=s_lat,
                            longitude=s_lon,
                            accuracy=15.0,
                            timestamp_raw=raw_t,
                            timestamp_utc=ts_utc,
                            timestamp_local=ts_loc,
                            epoch_type=ep,
                            source_file=source_display_path,
                            source_type=f"Android MediaStore ({tbl})",
                            category="exif_photo",
                            table_or_field=f"{tbl} ({lat_col}, {lon_col})",
                            device_os="Android",
                            confidence="high",
                            extra_data={
                                "Fichier_Media": str(file_path)[:200],
                                "Nom_Affiche": str(display_name)[:100],
                                "Type_Mime": str(mime),
                                "Table": tbl
                            }
                        ))
            except Exception:
                pass

        conn.close()
    except Exception:
        pass

    return points
