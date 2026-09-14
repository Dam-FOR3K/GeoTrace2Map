# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Forensic CSV Exporter
Exports complete forensic data table compatible with Excel and timeline tools.
"""
import csv
import json
from typing import List
from core.models import ForensicLocationPoint

def export_to_csv(points: List[ForensicLocationPoint], output_path: str):
    headers = [
        "ID",
        "Latitude",
        "Longitude",
        "Date_Heure_UTC",
        "Date_Heure_Locale",
        "Type_Epoque",
        "Timestamp_Brut",
        "Precision_Horizontale_Metres",
        "Altitude_Metres",
        "Vitesse",
        "Direction_Cap",
        "Source_Type",
        "Categorie",
        "Fichier_Source",
        "Table_ou_Champ_Origine",
        "OS_Detecte",
        "Niveau_Confiance",
        "Adresse_Postale",
        "Metadonnees_Supplementaires"
    ]
    
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_ALL)
        writer.writerow(headers)
        
        for idx, p in enumerate(points):
            # Clean extra metadata (exclude large base64 thumbnails)
            clean_extra = {k: v for k, v in p.extra_data.items() if k != "Thumbnail"} if p.extra_data else {}
            extra_json = json.dumps(clean_extra, ensure_ascii=False) if clean_extra else ""
            
            row = [
                p.id,
                p.latitude,
                p.longitude,
                p.timestamp_utc or "",
                p.timestamp_local or "",
                p.epoch_type or "",
                str(p.timestamp_raw) if p.timestamp_raw is not None else "",
                p.accuracy if p.accuracy is not None else "",
                p.altitude if p.altitude is not None else "",
                p.speed if p.speed is not None else "",
                p.bearing if p.bearing is not None else "",
                p.source_type,
                p.category,
                p.source_file,
                p.table_or_field or "",
                p.device_os or "",
                p.confidence or "",
                p.address or "",
                extra_json
            ]
            writer.writerow(row)
