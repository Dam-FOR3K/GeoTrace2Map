# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - GPX Exporter
Generates standard GPX 1.1 with waypoints and track points.
"""
import html
from typing import List
from core.models import ForensicLocationPoint

def export_to_gpx(points: List[ForensicLocationPoint], output_path: str, title: str = "GeoTrace2Map Forensic Track"):
    gpx_header = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="GeoTrace2Map (GT2M)" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>{html.escape(title)}</name>
    <desc>Trace GPS extraite pour analyse forensique</desc>
  </metadata>
  <trk>
    <name>Trajectoire Chronologique</name>
    <trkseg>
"""
    trk_body = []
    wpt_body = []
    
    for p in points:
        time_tag = f"<time>{p.timestamp_utc}</time>" if p.timestamp_utc else ""
        ele_tag = f"<ele>{p.altitude}</ele>" if p.altitude is not None else ""
        name_tag = f"<name>{html.escape(p.source_type)}</name>"
        desc_tag = f"<desc>{html.escape(p.source_file)} - {html.escape(p.table_or_field or '')}</desc>"
        
        # Add to track segment if timestamp exists
        if p.timestamp_utc:
            trk_body.append(f"""      <trkpt lat="{p.latitude}" lon="{p.longitude}">
        {ele_tag}
        {time_tag}
        {name_tag}
      </trkpt>""")
        else:
            # Standalone waypoint
            wpt_body.append(f"""  <wpt lat="{p.latitude}" lon="{p.longitude}">
    {ele_tag}
    {name_tag}
    {desc_tag}
  </wpt>""")

    gpx_footer = """    </trkseg>
  </trk>
</gpx>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(gpx_header + "\n".join(trk_body) + "\n" + gpx_footer + "\n" + "\n".join(wpt_body))
