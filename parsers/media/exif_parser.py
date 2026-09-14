# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - EXIF & Media Geolocation Parser
Extracts GPS tags from JPEG, HEIC, PNG, TIFF, WebP, and generates inline base64 thumbnails.
"""
import os
import io
import base64
from typing import List, Optional
from PIL import Image, ExifTags
from core.models import ForensicLocationPoint
from core.timestamps import parse_forensic_timestamp
from core.coordinates import parse_exif_dms, validate_coordinates

# Try registering HEIF/HEIC support if pillow-heif is present
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    try:
        import pi_heif
        pi_heif.register_heif_opener()
    except Exception:
        pass

def parse_media_exif(file_path: str, source_display_path: str, generate_thumb: bool = True) -> List[ForensicLocationPoint]:
    points: List[ForensicLocationPoint] = []
    if not os.path.exists(file_path):
        return points
        
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.heic', '.heif', '.png', '.tiff', '.tif', '.webp'):
        return points
        
    try:
        with Image.open(file_path) as img:
            gps_info = {}
            exif = img.getexif()
            
            # Method 1: get_ifd GPSInfo (Pillow 8+)
            if exif:
                try:
                    gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
                    if gps_ifd and len(gps_ifd) > 0:
                        gps_info = dict(gps_ifd)
                except Exception:
                    pass
                    
            # Method 2: _getexif fallback (legacy Pillow)
            if not gps_info and hasattr(img, '_getexif'):
                try:
                    raw_exif = img._getexif()
                    if raw_exif:
                        gps_val = raw_exif.get(34853)
                        if isinstance(gps_val, dict):
                            gps_info = gps_val
                except Exception:
                    pass
                    
            if not gps_info:
                return points
                
            # Decode GPS tags
            decoded_gps = {}
            for t_id, t_val in gps_info.items():
                t_name = ExifTags.GPSTAGS.get(t_id, t_id)
                decoded_gps[t_name] = t_val
                
            lat_dms = decoded_gps.get('GPSLatitude')
            lat_ref = decoded_gps.get('GPSLatitudeRef', 'N')
            lon_dms = decoded_gps.get('GPSLongitude')
            lon_ref = decoded_gps.get('GPSLongitudeRef', 'E')
            
            if lat_dms and lon_dms:
                lat = parse_exif_dms(lat_dms, lat_ref)
                lon = parse_exif_dms(lon_dms, lon_ref)
                valid, s_lat, s_lon = validate_coordinates(lat, lon)
                
                if valid:
                    # Altitude
                    alt = None
                    if 'GPSAltitude' in decoded_gps:
                        try:
                            raw_alt = decoded_gps['GPSAltitude']
                            alt = float(raw_alt) if not hasattr(raw_alt, 'num') else float(raw_alt.num)/float(raw_alt.den)
                            if decoded_gps.get('GPSAltitudeRef') == 1:
                                alt = -alt
                        except Exception:
                            pass
                            
                    # Date/Time
                    date_str = None
                    # Try Exif DateTimeOriginal
                    dt_original_tag = next((k for k, v in ExifTags.TAGS.items() if v == "DateTimeOriginal"), None)
                    if dt_original_tag and dt_original_tag in exif:
                        date_str = str(exif[dt_original_tag])
                    elif 'GPSDateStamp' in decoded_gps:
                        date_stamp = decoded_gps['GPSDateStamp']
                        time_stamp = decoded_gps.get('GPSTimeStamp')
                        if time_stamp and len(time_stamp) == 3:
                            h, m, s = int(time_stamp[0]), int(time_stamp[1]), int(time_stamp[2])
                            date_str = f"{date_stamp} {h:02d}:{m:02d}:{s:02d}"
                        else:
                            date_str = str(date_stamp)
                            
                    ts_utc, ts_loc, ep = parse_forensic_timestamp(date_str)
                    
                    # Generate Base64 thumbnail
                    thumb_b64 = None
                    if generate_thumb:
                        try:
                            thumb_img = img.copy()
                            thumb_img.thumbnail((160, 160))
                            if thumb_img.mode in ('RGBA', 'P'):
                                thumb_img = thumb_img.convert('RGB')
                            buf = io.BytesIO()
                            thumb_img.save(buf, format='JPEG', quality=75)
                            thumb_b64 = f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
                        except Exception:
                            pass
                            
                    camera_make = exif.get(next((k for k, v in ExifTags.TAGS.items() if v == "Make"), None), "")
                    camera_model = exif.get(next((k for k, v in ExifTags.TAGS.items() if v == "Model"), None), "")
                    camera_str = f"{camera_make} {camera_model}".strip() or "Appareil photo"
                    
                    points.append(ForensicLocationPoint(
                        latitude=s_lat,
                        longitude=s_lon,
                        altitude=alt,
                        accuracy=10.0, # High precision GPS
                        timestamp_raw=date_str,
                        timestamp_utc=ts_utc,
                        timestamp_local=ts_loc,
                        epoch_type=ep,
                        source_file=source_display_path,
                        source_type="Photo/Média EXIF",
                        category="exif_photo",
                        table_or_field="Exif.GPSInfo",
                        device_os="Unknown",
                        confidence="high",
                        extra_data={
                            "Fichier": os.path.basename(file_path),
                            "Appareil": camera_str,
                            "Thumbnail": thumb_b64
                        }
                    ))
    except Exception:
        pass
        
    return points
