# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - GPX, KML, GeoJSON & Google Takeout Parser
"""
import os
import json
import xml.etree.ElementTree as ET
from typing import List
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import validate_coordinates

def parse_geo_file(file_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
    points: List[ForensicLocationPoint] = []
    if not os.path.exists(file_path):
        return points
        
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == ".gpx":
            points.extend(_parse_gpx(file_path, source_display_path))
        elif ext in (".kml", ".xml"):
            points.extend(_parse_kml(file_path, source_display_path))
        elif ext in (".geojson", ".json"):
            points.extend(_parse_json_or_geojson(file_path, source_display_path))
    except Exception:
        pass
        
    return points

def _parse_gpx(file_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
    pts: List[ForensicLocationPoint] = []
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        # Handle namespaces
        ns = {'gpx': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
        prefix = 'gpx:' if ns else ''
        
        # Look for wpt, trkpt, rtept
        elements = root.findall(f".//{prefix}trkpt", ns) + root.findall(f".//{prefix}wpt", ns) + root.findall(f".//{prefix}rtept", ns)
        for elem in elements:
            lat = elem.attrib.get('lat')
            lon = elem.attrib.get('lon')
            valid, s_lat, s_lon = validate_coordinates(lat, lon)
            if valid:
                ele_node = elem.find(f"{prefix}ele", ns)
                time_node = elem.find(f"{prefix}time", ns)
                name_node = elem.find(f"{prefix}name", ns)
                
                alt = float(ele_node.text) if ele_node is not None and ele_node.text else None
                raw_t = time_node.text if time_node is not None else None
                ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t)
                name = name_node.text if name_node is not None else "Point GPX"
                
                pts.append(ForensicLocationPoint(
                    latitude=s_lat,
                    longitude=s_lon,
                    altitude=alt,
                    accuracy=5.0,
                    timestamp_raw=raw_t,
                    timestamp_utc=ts_utc,
                    timestamp_local=ts_loc,
                    epoch_type=ep,
                    source_file=source_display_path,
                    source_type="Trace GPX",
                    category="gps_fix",
                    table_or_field=elem.tag.split('}')[-1],
                    device_os="Unknown",
                    confidence="high",
                    extra_data={"Nom": name}
                ))
    except Exception:
        pass
    return pts

def _parse_kml(file_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
    pts: List[ForensicLocationPoint] = []
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        ns = {'kml': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
        prefix = 'kml:' if ns else ''
        
        for placemark in root.findall(f".//{prefix}Placemark", ns):
            name_node = placemark.find(f"{prefix}name", ns)
            time_node = placemark.find(f".//{prefix}when", ns)
            coord_node = placemark.find(f".//{prefix}coordinates", ns)
            
            if coord_node is not None and coord_node.text:
                coords_str = coord_node.text.strip()
                # May contain multiple coordinates separated by whitespace
                for item in coords_str.split():
                    parts = item.split(',')
                    if len(parts) >= 2:
                        lon, lat = parts[0], parts[1]
                        alt = float(parts[2]) if len(parts) > 2 else None
                        valid, s_lat, s_lon = validate_coordinates(lat, lon)
                        if valid:
                            raw_t = time_node.text if time_node is not None else None
                            ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t)
                            name = name_node.text if name_node is not None else "Placemark KML"
                            
                            pts.append(ForensicLocationPoint(
                                latitude=s_lat,
                                longitude=s_lon,
                                altitude=alt,
                                accuracy=10.0,
                                timestamp_raw=raw_t,
                                timestamp_utc=ts_utc,
                                timestamp_local=ts_loc,
                                epoch_type=ep,
                                source_file=source_display_path,
                                source_type="Fichier KML",
                                category="gps_fix",
                                table_or_field="Placemark/coordinates",
                                device_os="Unknown",
                                confidence="high",
                                extra_data={"Nom": name}
                            ))
    except Exception:
        pass
    return pts

def _parse_json_or_geojson(file_path: str, source_display_path: str) -> List[ForensicLocationPoint]:
    pts: List[ForensicLocationPoint] = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            data = json.load(f)
            
        # Case A: GeoJSON
        if isinstance(data, dict) and data.get("type") in ("FeatureCollection", "Feature"):
            features = data.get("features", []) if data.get("type") == "FeatureCollection" else [data]
            for feat in features:
                geom = feat.get("geometry", {})
                props = feat.get("properties", {})
                if geom.get("type") == "Point":
                    coords = geom.get("coordinates", [])
                    if len(coords) >= 2:
                        lon, lat = coords[0], coords[1]
                        alt = coords[2] if len(coords) > 2 else None
                        valid, s_lat, s_lon = validate_coordinates(lat, lon)
                        if valid:
                            raw_t = props.get("time") or props.get("timestamp")
                            ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t)
                            pts.append(ForensicLocationPoint(
                                latitude=s_lat,
                                longitude=s_lon,
                                altitude=alt,
                                timestamp_raw=raw_t,
                                timestamp_utc=ts_utc,
                                timestamp_local=ts_loc,
                                epoch_type=ep,
                                source_file=source_display_path,
                                source_type="GeoJSON Feature",
                                category="gps_fix",
                                table_or_field="geometry.coordinates",
                                confidence="high",
                                extra_data=props
                            ))
                            
        # Case B: Google Takeout Records.json / Location History.json
        elif isinstance(data, dict) and ("locations" in data or "timelineObjects" in data):
            locations = data.get("locations", [])
            for loc in locations:
                raw_lat = loc.get("latitudeE7") or loc.get("latitude")
                raw_lon = loc.get("longitudeE7") or loc.get("longitude")
                if raw_lat and raw_lon:
                    if loc.get("latitudeE7"):
                        raw_lat = float(raw_lat) / 1e7
                        raw_lon = float(raw_lon) / 1e7
                    valid, s_lat, s_lon = validate_coordinates(raw_lat, raw_lon)
                    if valid:
                        raw_t = loc.get("timestamp") or loc.get("timestampMs")
                        ts_utc, ts_loc, ep = parse_forensic_timestamp(raw_t)
                        acc = loc.get("accuracy")
                        pts.append(ForensicLocationPoint(
                            latitude=s_lat,
                            longitude=s_lon,
                            altitude=loc.get("altitude"),
                            accuracy=float(acc) if acc else None,
                            timestamp_raw=raw_t,
                            timestamp_utc=ts_utc,
                            timestamp_local=ts_loc,
                            epoch_type=ep,
                            source_file=source_display_path,
                            source_type="Google Takeout (Location History)",
                            category="gps_fix",
                            table_or_field="locations",
                            device_os="Android",
                            confidence="high"
                        ))
    except Exception:
        pass
    return pts
