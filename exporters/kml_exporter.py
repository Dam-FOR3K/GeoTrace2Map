# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - KML Exporter
Generates KML files with TimeSpan/TimeStamp tags for Google Earth 3D playback.
"""
import html
from typing import List
from core.models import ForensicLocationPoint

def export_to_kml(points: List[ForensicLocationPoint], output_path: str, title: str = "GeoTrace2Map Forensic Extraction"):
    kml_header = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{html.escape(title)}</name>
    <description>Rapport d'extraction de géolocalisation forensique généré par GeoTrace2Map (GT2M)</description>
    
    <!-- Styles par catégorie -->
    <Style id="style_gps_fix">
      <IconStyle>
        <color>ff00ff00</color>
        <scale>1.1</scale>
        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/grn-circle.png</href></Icon>
      </IconStyle>
    </Style>
    <Style id="style_exif_photo">
      <IconStyle>
        <color>ff00aaff</color>
        <scale>1.1</scale>
        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/orange-circle.png</href></Icon>
      </IconStyle>
    </Style>
    <Style id="style_system_routine">
      <IconStyle>
        <color>ffffaa00</color>
        <scale>1.1</scale>
        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/blu-circle.png</href></Icon>
      </IconStyle>
    </Style>
    <Style id="style_wifi">
      <IconStyle>
        <color>ff00ffff</color>
        <scale>1.0</scale>
        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png</href></Icon>
      </IconStyle>
    </Style>
    <Style id="style_cell_tower">
      <IconStyle>
        <color>ff0000ff</color>
        <scale>1.0</scale>
        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/red-circle.png</href></Icon>
      </IconStyle>
    </Style>
    <Style id="style_messaging">
      <IconStyle>
        <color>ffff00ff</color>
        <scale>1.1</scale>
        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/purple-circle.png</href></Icon>
      </IconStyle>
    </Style>
    <Style id="style_generic">
      <IconStyle>
        <color>ffffffff</color>
        <scale>0.9</scale>
        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/wht-circle.png</href></Icon>
      </IconStyle>
    </Style>
"""
    kml_body = []
    
    for p in points:
        style_id = f"style_{p.category}" if f"style_{p.category}" in (
            "style_gps_fix", "style_exif_photo", "style_system_routine", "style_wifi", "style_cell_tower", "style_messaging"
        ) else "style_generic"
        
        time_tag = f"<TimeStamp><when>{p.timestamp_utc}</when></TimeStamp>" if p.timestamp_utc else ""
        
        # Build HTML table for description
        desc_rows = [
            f"<tr><td><b>Date UTC :</b></td><td>{p.timestamp_utc or 'N/A'}</td></tr>",
            f"<tr><td><b>Date Locale :</b></td><td>{p.timestamp_local or 'N/A'}</td></tr>",
            f"<tr><td><b>Source :</b></td><td>{html.escape(p.source_type)}</td></tr>",
            f"<tr><td><b>Fichier :</b></td><td>{html.escape(p.source_file)}</td></tr>",
            f"<tr><td><b>Table / Champ :</b></td><td>{html.escape(p.table_or_field or 'N/A')}</td></tr>",
            f"<tr><td><b>Précision :</b></td><td>{f'{p.accuracy} m' if p.accuracy else 'Inconnue'}</td></tr>",
            f"<tr><td><b>Altitude :</b></td><td>{f'{p.altitude} m' if p.altitude else 'N/A'}</td></tr>",
            f"<tr><td><b>OS Détecté :</b></td><td>{p.device_os}</td></tr>",
        ]
        
        if p.extra_data:
            for k, v in p.extra_data.items():
                if k != "Thumbnail": # don't blow up KML with huge b64 strings
                    desc_rows.append(f"<tr><td><b>{html.escape(str(k))} :</b></td><td>{html.escape(str(v))}</td></tr>")
                    
        desc_html = f"<![CDATA[<table border='1' cellpadding='4' cellspacing='0' style='font-family:sans-serif;font-size:12px;'>{''.join(desc_rows)}</table>]]>"
        
        kml_body.append(f"""
    <Placemark>
      <name>{html.escape(p.source_type)}</name>
      <styleUrl>#{style_id}</styleUrl>
      <description>{desc_html}</description>
      {time_tag}
      <Point>
        <coordinates>{p.longitude},{p.latitude},{p.altitude or 0}</coordinates>
      </Point>
    </Placemark>""")

    kml_footer = """
  </Document>
</kml>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(kml_header + "\n".join(kml_body) + kml_footer)
