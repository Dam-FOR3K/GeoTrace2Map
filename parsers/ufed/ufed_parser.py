# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - UFED & Cellebrite Report Parser
Parses Cellebrite UFED Excel (.xlsx) and CSV reports with all forensic metadata.
"""
import os
import pandas as pd
from typing import List, Optional
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import parse_coordinate, validate_coordinates

def parse_ufed_file(file_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
    points: List[ForensicLocationPoint] = []
    if not os.path.exists(file_path):
        return points
        
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext in (".xlsx", ".xls"):
            excel_file = pd.ExcelFile(file_path)
            for sheet_name in excel_file.sheet_names:
                try:
                    # Read sheet without header first to detect actual header row
                    raw_df = excel_file.parse(sheet_name, header=None)
                    header_row_idx = None
                    for r_idx in range(min(20, len(raw_df))):
                        row_vals = [str(v).lower().strip() for v in raw_df.iloc[r_idx] if not pd.isna(v)]
                        has_lat = any(("lat" in v or "latitude" in v) and "delta" not in v for v in row_vals)
                        has_lon = any(("lon" in v or "lng" in v or "longitude" in v) and "delta" not in v for v in row_vals)
                        if has_lat and has_lon:
                            header_row_idx = r_idx
                            break
                            
                    if header_row_idx is not None:
                        df = excel_file.parse(sheet_name, skiprows=header_row_idx)
                        points.extend(_process_dataframe(df, f"{source_display_path} [{sheet_name}]", "UFED Excel"))
                    else:
                        # Fallback default read
                        df = excel_file.parse(sheet_name)
                        if _has_coords(df):
                            points.extend(_process_dataframe(df, f"{source_display_path} [{sheet_name}]", "UFED Excel"))
                except Exception:
                    pass
        elif ext in (".csv", ".tsv"):
            sep = '\t' if ext == ".tsv" else ','
            try:
                # Read first rows to detect header
                raw_df = pd.read_csv(file_path, sep=sep, header=None, nrows=25)
                header_row_idx = None
                for r_idx in range(len(raw_df)):
                    row_vals = [str(v).lower().strip() for v in raw_df.iloc[r_idx] if not pd.isna(v)]
                    has_lat = any(("lat" in v or "latitude" in v) and "delta" not in v for v in row_vals)
                    has_lon = any(("lon" in v or "lng" in v or "longitude" in v) and "delta" not in v for v in row_vals)
                    if has_lat and has_lon:
                        header_row_idx = r_idx
                        break
                        
                if header_row_idx is not None and header_row_idx > 0:
                    df = pd.read_csv(file_path, sep=sep, skiprows=header_row_idx)
                else:
                    df = pd.read_csv(file_path, sep=sep)
                    
                if _has_coords(df):
                    points.extend(_process_dataframe(df, source_display_path, "UFED/Forensic CSV"))
            except Exception:
                pass
    except Exception:
        pass
        
    return points

def _has_coords(df: pd.DataFrame) -> bool:
    cols = [str(c).lower().strip() for c in df.columns]
    has_lat = any(("lat" in c or "latitude" in c or "y_coord" in c) and "delta" not in c for c in cols)
    has_lon = any(("lon" in c or "lng" in c or "longitude" in c or "x_coord" in c) and "delta" not in c for c in cols)
    return has_lat and has_lon

def _process_dataframe(df: pd.DataFrame, source_display_path: str, report_type: str) -> List[ForensicLocationPoint]:
    pts: List[ForensicLocationPoint] = []
    cols_map = {str(c).lower().strip(): c for c in df.columns}
    
    # 1. Identify Latitude Column
    lat_candidates = [cols_map[c] for c in cols_map if any(k in c for k in ("latitude", "lat", "y_coord")) and "delta" not in c and "span" not in c]
    # 2. Identify Longitude Column
    lon_candidates = [cols_map[c] for c in cols_map if any(k in c for k in ("longitude", "lon", "lng", "x_coord")) and "delta" not in c and "span" not in c]
    
    if not lat_candidates or not lon_candidates:
        return pts
        
    lat_col = lat_candidates[0]
    lon_col = lon_candidates[0]
    
    # 3. Identify Timestamp / Date Column (with smart priority)
    time_keywords = ("timestamp", "time", "date", "heure", "horodatage", "temps", "created", "modified", "start", "stop", "entry", "fix", "added", "when", "instant")
    time_candidates = [cols_map[c] for c in cols_map if any(k in c for k in time_keywords) and "end" not in c]
    if not time_candidates:
        time_candidates = [cols_map[c] for c in cols_map if any(k in c for k in time_keywords)]
    
    def _time_col_priority(col_name: str) -> int:
        c_low = col_name.lower()
        if "utc" in c_low:
            return 0
        if "time" == c_low or "timestamp" == c_low or "date" == c_low:
            return 1
        if "timestamp" in c_low:
            return 2
        if "date/time" in c_low or "date & time" in c_low:
            return 3
        if "time" in c_low:
            return 4
        if "date" in c_low:
            return 5
        if "horodatage" in c_low or "heure" in c_low:
            return 6
        return 10
        
    time_candidates.sort(key=_time_col_priority)
    time_col = time_candidates[0] if time_candidates else None
    
    # 4. Other metadata columns
    origin_col = next((cols_map[c] for c in cols_map if any(k in c for k in ("origin", "source", "provenance"))), None)
    cat_col = next((cols_map[c] for c in cols_map if any(k in c for k in ("category", "type", "categorie"))), None)
    name_col = next((cols_map[c] for c in cols_map if any(k in c for k in ("name", "title", "label", "nom", "titre"))), None)
    desc_col = next((cols_map[c] for c in cols_map if any(k in c for k in ("description", "details", "notes", "detail", "texte"))), None)
    acc_col = next((cols_map[c] for c in cols_map if any(k in c for k in ("precision", "accuracy", "radius", "incertitude"))), None)
    id_col = next((cols_map[c] for c in cols_map if c in ("#", "id", "index", "n°", "numero")), None)
    alt_col = next((cols_map[c] for c in cols_map if any(k in c for k in ("altitude", "alt", "elevation", "hauteur"))), None)
    addr_col = next((cols_map[c] for c in cols_map if any(k in c for k in ("address", "adresse", "map address"))), None)
    
    for idx, row in df.iterrows():
        raw_lat = parse_coordinate(row[lat_col])
        raw_lon = parse_coordinate(row[lon_col])
        valid, s_lat, s_lon = validate_coordinates(raw_lat, raw_lon)
        if valid:
            raw_t = row[time_col] if time_col else None
            ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t)
            
            origin = str(row[origin_col]) if origin_col and not pd.isna(row[origin_col]) and str(row[origin_col]).strip() != "" else "Rapport Forensic"
            cat = str(row[cat_col]) if cat_col and not pd.isna(row[cat_col]) and str(row[cat_col]).strip() != "" else "Extraction"
            name = str(row[name_col]) if name_col and not pd.isna(row[name_col]) else ""
            desc = str(row[desc_col]) if desc_col and not pd.isna(row[desc_col]) else ""
            acc = parse_coordinate(row[acc_col]) if acc_col and not pd.isna(row[acc_col]) else None
            alt = parse_coordinate(row[alt_col]) if alt_col and not pd.isna(row[alt_col]) else None
            addr = str(row[addr_col]) if addr_col and not pd.isna(row[addr_col]) and str(row[addr_col]).strip() != "" else None
            item_id = str(row[id_col]) if id_col and not pd.isna(row[id_col]) else str(idx + 1)
            
            extra = {
                "ID_Rapport": item_id,
                "Origine": origin,
                "Categorie": cat,
                "Nom": name,
                "Description": desc,
                "Colonne_Temps": str(time_col) if time_col else "Non trouvée"
            }
            if addr:
                extra["Adresse_Rapport"] = addr

            pts.append(ForensicLocationPoint(
                latitude=s_lat,
                longitude=s_lon,
                altitude=alt,
                accuracy=acc,
                address=addr,
                timestamp_raw=str(raw_t) if raw_t is not None else None,
                timestamp_utc=ts_utc,
                timestamp_local=ts_loc,
                epoch_type=ep,
                source_file=source_display_path,
                source_type=f"{report_type} ({origin})",
                category="gps_fix",
                table_or_field=f"Item #{item_id} (Col: {lat_col})",
                device_os="UFED",
                confidence="high",
                extra_data=extra
            ))
            
    return pts
