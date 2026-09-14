# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - iOS CoreRoutine.sqlite Parser
Extracts Apple CoreRoutine artifacts: Significant Locations, Visits, Learned Locations, Vehicle Events.
"""
import sqlite3
import os
from typing import List
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import validate_coordinates

def parse_coreroutine_db(db_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
    points: List[ForensicLocationPoint] = []
    if not os.path.exists(db_path):
        return points
        
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Check available tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        
        # 1. ZRTCLLOCATIONMO (Raw & Processed CoreLocation Fixes)
        if "ZRTCLLOCATIONMO" in tables:
            try:
                cur.execute("""
                    SELECT ZLATITUDE, ZLONGITUDE, ZALTITUDE, ZHORIZONTALACCURACY, 
                           ZVERTICALACCURACY, ZSPEED, ZCOURSE, ZTIMESTAMP 
                    FROM ZRTCLLOCATIONMO
                """)
                for row in cur.fetchall():
                    lat, lon = row["ZLATITUDE"], row["ZLONGITUDE"]
                    valid, s_lat, s_lon = validate_coordinates(lat, lon)
                    if valid:
                        ts_utc, ts_loc, ep = parse_forensic_timestamp(row["ZTIMESTAMP"], hint_os="iOS")
                        points.append(ForensicLocationPoint(
                            latitude=s_lat,
                            longitude=s_lon,
                            altitude=row["ZALTITUDE"],
                            accuracy=row["ZHORIZONTALACCURACY"],
                            vertical_accuracy=row["ZVERTICALACCURACY"],
                            speed=row["ZSPEED"],
                            bearing=row["ZCOURSE"],
                            timestamp_raw=row["ZTIMESTAMP"],
                            timestamp_utc=ts_utc,
                            timestamp_local=ts_loc,
                            epoch_type=ep,
                            source_file=source_display_path,
                            source_type="iOS CoreRoutine (Location Fix)",
                            category="system_routine",
                            table_or_field="ZRTCLLOCATIONMO",
                            device_os="iOS",
                            confidence="high" if (row["ZHORIZONTALACCURACY"] and row["ZHORIZONTALACCURACY"] < 30) else "medium"
                        ))
            except Exception:
                pass

        # 2. ZRTVISITMO (Significant Visits / Places stayed)
        if "ZRTVISITMO" in tables:
            try:
                cur.execute("""
                    SELECT ZLOCATIONLATITUDE, ZLOCATIONLONGITUDE, ZLOCATIONHORIZONTALACCURACY, 
                           ZENTRYDATE, ZEXITDATE, ZCONFIDENCE 
                    FROM ZRTVISITMO
                """)
                for row in cur.fetchall():
                    lat, lon = row["ZLOCATIONLATITUDE"], row["ZLOCATIONLONGITUDE"]
                    valid, s_lat, s_lon = validate_coordinates(lat, lon)
                    if valid:
                        ts_utc, ts_loc, ep = parse_forensic_timestamp(row["ZENTRYDATE"], hint_os="iOS")
                        exit_utc, _, _ = parse_forensic_timestamp(row["ZEXITDATE"], hint_os="iOS")
                        points.append(ForensicLocationPoint(
                            latitude=s_lat,
                            longitude=s_lon,
                            accuracy=row["ZLOCATIONHORIZONTALACCURACY"],
                            timestamp_raw=row["ZENTRYDATE"],
                            timestamp_utc=ts_utc,
                            timestamp_local=ts_loc,
                            epoch_type=ep,
                            source_file=source_display_path,
                            source_type="iOS CoreRoutine (Visit / Lieu Fréquent)",
                            category="system_routine",
                            table_or_field="ZRTVISITMO",
                            device_os="iOS",
                            confidence="high",
                            extra_data={
                                "Date_Entree": ts_utc,
                                "Date_Sortie": exit_utc,
                                "Confiance": row["ZCONFIDENCE"]
                            }
                        ))
            except Exception:
                pass

        # 3. ZRTLEARNEDLOCATIONOFINTERESTMO (Learned Places / Home / Work)
        if "ZRTLEARNEDLOCATIONOFINTERESTMO" in tables:
            try:
                cur.execute("""
                    SELECT ZLOCATIONLATITUDE, ZLOCATIONLONGITUDE, ZLOCATIONHORIZONTALACCURACY, 
                           ZCREATIONDATE, ZPLACE_TYPE, ZCUSTOM_LABEL 
                    FROM ZRTLEARNEDLOCATIONOFINTERESTMO
                """)
                for row in cur.fetchall():
                    lat, lon = row["ZLOCATIONLATITUDE"], row["ZLOCATIONLONGITUDE"]
                    valid, s_lat, s_lon = validate_coordinates(lat, lon)
                    if valid:
                        ts_utc, ts_loc, ep = parse_forensic_timestamp(row["ZCREATIONDATE"], hint_os="iOS")
                        points.append(ForensicLocationPoint(
                            latitude=s_lat,
                            longitude=s_lon,
                            accuracy=row["ZLOCATIONHORIZONTALACCURACY"],
                            timestamp_raw=row["ZCREATIONDATE"],
                            timestamp_utc=ts_utc,
                            timestamp_local=ts_loc,
                            epoch_type=ep,
                            source_file=source_display_path,
                            source_type="iOS CoreRoutine (Point d'Intérêt / Lieu Appris)",
                            category="system_routine",
                            table_or_field="ZRTLEARNEDLOCATIONOFINTERESTMO",
                            device_os="iOS",
                            confidence="high",
                            extra_data={
                                "Label": row["ZCUSTOM_LABEL"] or "Non spécifié",
                                "Type": row["ZPLACE_TYPE"]
                            }
                        ))
            except Exception:
                pass

        # 4. ZRTVEHICLEEVENTMO (Vehicle Parked / Disconnect Events)
        if "ZRTVEHICLEEVENTMO" in tables:
            try:
                cur.execute("""
                    SELECT ZLOCATIONLATITUDE, ZLOCATIONLONGITUDE, ZLOCATIONHORIZONTALACCURACY, 
                           ZDATE, ZVEHICLENAME, ZUSERCONFIRMED 
                    FROM ZRTVEHICLEEVENTMO
                """)
                for row in cur.fetchall():
                    lat, lon = row["ZLOCATIONLATITUDE"], row["ZLOCATIONLONGITUDE"]
                    valid, s_lat, s_lon = validate_coordinates(lat, lon)
                    if valid:
                        ts_utc, ts_loc, ep = parse_forensic_timestamp(row["ZDATE"], hint_os="iOS")
                        points.append(ForensicLocationPoint(
                            latitude=s_lat,
                            longitude=s_lon,
                            accuracy=row["ZLOCATIONHORIZONTALACCURACY"],
                            timestamp_raw=row["ZDATE"],
                            timestamp_utc=ts_utc,
                            timestamp_local=ts_loc,
                            epoch_type=ep,
                            source_file=source_display_path,
                            source_type="iOS CoreRoutine (Véhicule / Stationnement)",
                            category="system_routine",
                            table_or_field="ZRTVEHICLEEVENTMO",
                            device_os="iOS",
                            confidence="high",
                            extra_data={
                                "Vehicule": row["ZVEHICLENAME"] or "Bluetooth Véhicule",
                                "Confirme": bool(row["ZUSERCONFIRMED"])
                            }
                        ))
            except Exception:
                pass
                
        conn.close()
    except Exception:
        pass
        
    return points
