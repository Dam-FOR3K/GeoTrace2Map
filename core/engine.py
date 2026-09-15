# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Core Extraction Engine
Orchestrates file inspection, ZIP/archive unpacking, parser dispatching, and deduplication.
"""
import os
import zipfile
import tarfile
import tempfile
import shutil
import time
from typing import List, Dict, Any, Callable, Optional, Tuple

from core.models import ForensicLocationPoint, ExtractionSummary
from parsers.ios.coreroutine import parse_coreroutine_db
from parsers.ios.locationd import parse_locationd_db
from parsers.ios.photos import parse_photos_db
from parsers.ios.apple_maps import parse_apple_maps_db
from parsers.ios.cache_sqlite import parse_ios_cache_sqlite
from parsers.android.google_location import parse_android_location_db
from parsers.android.google_maps import parse_android_maps_db
from parsers.android.telephony import parse_android_telephony_db
from parsers.ufed.ufed_parser import parse_ufed_file
from parsers.media.exif_parser import parse_media_exif
from parsers.apps.messaging_parser import parse_messaging_db
from parsers.generic.sqlite_scraper import scrape_generic_sqlite
from parsers.generic.geo_files import parse_geo_file
from parsers.android.media_provider import parse_media_provider_db
from parsers.ios.geobookmarks import parse_geobookmarks_plist
from parsers.apps.browser_history import parse_browser_history_db

class ForensicExtractorEngine:
    def __init__(self, mls_db_path: str = "MLS.db"):
        self.mls_db_path = mls_db_path

    def process_target(
        self, 
        target_path: str, 
        progress_callback: Optional[Callable[[int, str, int], None]] = None
    ) -> Tuple[List[ForensicLocationPoint], ExtractionSummary]:
        """
        Main entrypoint. Ingests a ZIP file, TAR archive, folder path, or standalone file.
        """
        t_start = time.time()
        temp_dir = None
        extracted_root = None
        
        try:
            if not os.path.exists(target_path):
                raise FileNotFoundError(f"Fichier ou dossier introuvable : {target_path}")

            # 1. Handle Archive uncompression
            if os.path.isfile(target_path):
                ext = os.path.splitext(target_path)[1].lower()
                if ext in ('.zip', '.tar', '.gz', '.tgz', '.bz2'):
                    if progress_callback:
                        progress_callback(5, f"Extraction de l'archive {os.path.basename(target_path)}...", 0)
                    temp_dir = tempfile.mkdtemp(prefix="gt2m_")
                    self._unpack_archive(target_path, temp_dir)
                    extracted_root = temp_dir
                else:
                    # Single standalone file
                    extracted_root = target_path
            else:
                # Directory
                extracted_root = target_path

            # 2. Gather all files
            all_files = []
            if os.path.isdir(extracted_root):
                for root, _, files in os.walk(extracted_root):
                    for f in files:
                        full_p = os.path.join(root, f)
                        rel_p = os.path.relpath(full_p, extracted_root)
                        all_files.append((full_p, rel_p))
            else:
                all_files.append((extracted_root, os.path.basename(extracted_root)))

            total_files = len(all_files)
            if progress_callback:
                progress_callback(15, f"{total_files} fichiers découverts. Analyse en cours...", 0)

            # 3. Detect OS Heuristics
            detected_os_set = set()
            for _, rel_p in all_files:
                r_lower = rel_p.lower()
                if "mobile/library" in r_lower or "coreroutine" in r_lower or "locationd" in r_lower or "apple" in r_lower:
                    detected_os_set.add("iOS")
                if "data/data" in r_lower or "com.google.android" in r_lower or "gservices" in r_lower:
                    detected_os_set.add("Android")
                if "ufed" in r_lower or "cellebrite" in r_lower:
                    detected_os_set.add("UFED")

            primary_os = "iOS" if "iOS" in detected_os_set and "Android" not in detected_os_set else (
                "Android" if "Android" in detected_os_set and "iOS" not in detected_os_set else "Multi-OS / Hybride"
            )

            # 4. Iterate and parse files
            raw_points: List[ForensicLocationPoint] = []
            scanned_count = 0
            
            for idx, (full_p, rel_p) in enumerate(all_files):
                fname = os.path.basename(full_p).lower()
                fext = os.path.splitext(full_p)[1].lower()
                
                # Skip standalone SQLite journal/wal files (they are processed with their parent database)
                if fname.endswith(('-wal', '-shm', '-journal')):
                    continue
                    
                file_pts = []
                
                # Check for specialized parsers
                if ("coreroutine" in fname or fname == "local.sqlite" or ("routined" in rel_p.lower() and fext in ('.sqlite', '.db'))) and fext in ('.sqlite', '.db', ''):
                    file_pts = parse_coreroutine_db(full_p, rel_p)
                elif "cache_encrypted" in fname or "lockcache" in fname:
                    file_pts = parse_locationd_db(full_p, rel_p)
                elif "cache.sqlite" in fname or (fname.startswith("cache") and fext in ('.sqlite', '.db')):
                    file_pts = parse_ios_cache_sqlite(full_p, rel_p)
                elif "photos.sqlite" in fname:
                    file_pts = parse_photos_db(full_p, rel_p)
                elif "geobookmarks" in fname and fext in ('.plist', ''):
                    file_pts = parse_geobookmarks_plist(full_p, rel_p)
                elif fname in ("external.db", "media.db", "external-primary.db") or ("providers.media" in rel_p.lower() and fext in ('.db', '.sqlite')):
                    file_pts = parse_media_provider_db(full_p, rel_p)
                elif "geohistory" in fname or "gmm_storage" in fname or ("maps" in fname and fext in ('.db', '.sqlite', '.mapsdata')):
                    file_pts = parse_apple_maps_db(full_p, rel_p) or parse_android_maps_db(full_p, rel_p)
                elif fname in ("location.db", "gservices.db", "geolocation.db") or "fused" in fname:
                    file_pts = parse_android_location_db(full_p, rel_p)
                elif "telephony.db" in fname:
                    file_pts = parse_android_telephony_db(full_p, rel_p, self.mls_db_path)
                elif "chatstorage" in fname or "msgstore" in fname or "waze" in fname or fname in ("sms.db", "mmssms.db"):
                    file_pts = parse_messaging_db(full_p, rel_p)
                elif fname in ("history.db", "history") and ("safari" in rel_p.lower() or "chrome" in rel_p.lower() or "browser" in rel_p.lower()):
                    file_pts = parse_browser_history_db(full_p, rel_p)
                elif fext in ('.xlsx', '.xls'):
                    file_pts = parse_ufed_file(full_p, rel_p)
                elif fext in ('.jpg', '.jpeg', '.heic', '.heif', '.png', '.tiff', '.webp'):
                    file_pts = parse_media_exif(full_p, rel_p)
                elif fext in ('.gpx', '.kml', '.geojson') or (fext == '.json' and ("record" in fname or "location" in fname)):
                    file_pts = parse_geo_file(full_p, rel_p)
                elif fext in ('.sqlite', '.sqlite3', '.db', '.db3'):
                    # Generic SQLite Fallback
                    file_pts = scrape_generic_sqlite(full_p, rel_p, hint_os="iOS" if "iOS" in detected_os_set else "Android")
                elif fext == '.csv':
                    file_pts = parse_ufed_file(full_p, rel_p)

                if file_pts:
                    raw_points.extend(file_pts)
                
                scanned_count += 1
                if progress_callback and (idx % 25 == 0 or idx == total_files - 1):
                    pct = int(15 + (idx / total_files) * 75)
                    progress_callback(pct, f"Analyse : {rel_p[:40]}...", len(raw_points))

            # 5. Deduplication and Normalization
            if progress_callback:
                progress_callback(92, "Déduplication et synthèse des coordonnées...", len(raw_points))

            deduped_points: List[ForensicLocationPoint] = []
            seen_dict: Dict[Any, ForensicLocationPoint] = {}
            dup_count = 0
            
            for p in raw_points:
                # Key based on 5 decimals (~1.1 meter resolution) + timestamp
                key = (round(p.latitude, 5), round(p.longitude, 5), p.timestamp_utc or "no_time")
                if key in seen_dict:
                    dup_count += 1
                    orig_pt = seen_dict[key]
                    if "Occurrences" not in orig_pt.extra_data:
                        orig_label = orig_pt.table_or_field or f"Ligne #1 ({orig_pt.source_type})"
                        orig_pt.extra_data["Occurrences"] = [orig_label]
                    
                    dup_label = p.table_or_field or f"Ligne #{dup_count+1} ({p.source_type})"
                    if dup_label not in orig_pt.extra_data["Occurrences"]:
                        orig_pt.extra_data["Occurrences"].append(dup_label)
                    continue

                seen_dict[key] = p
                deduped_points.append(p)

            # Sort chronologically (oldest to newest, points without timestamps at the end)
            def _sort_key(p: ForensicLocationPoint):
                return p.timestamp_utc or "9999-99-99"
            deduped_points.sort(key=_sort_key)

            # 6. Generate Summary
            dates_list = [p.timestamp_utc for p in deduped_points if p.timestamp_utc]
            date_min = min(dates_list) if dates_list else None
            date_max = max(dates_list) if dates_list else None

            sources_count: Dict[str, int] = {}
            categories_count: Dict[str, int] = {}
            for p in deduped_points:
                sources_count[p.source_type] = sources_count.get(p.source_type, 0) + 1
                categories_count[p.category] = categories_count.get(p.category, 0) + 1

            summary = ExtractionSummary(
                total_points=len(raw_points),
                valid_points=len(deduped_points),
                duplicate_points_removed=dup_count,
                date_min=date_min,
                date_max=date_max,
                sources_count=sources_count,
                categories_count=categories_count,
                detected_os=list(detected_os_set) if detected_os_set else [primary_os],
                scanned_files_count=scanned_count,
                execution_time_seconds=round(time.time() - t_start, 2)
            )

            if progress_callback:
                progress_callback(100, f"Extraction terminée : {len(deduped_points)} points géographiques identifiés.", len(deduped_points))

            return deduped_points, summary

        finally:
            # Clean up temp folder if one was created
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass

    def _unpack_archive(self, archive_path: str, extract_dir: str):
        """
        Unpacks ZIP or TAR safely with file extension filtering to optimize space and memory.
        """
        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path, 'r') as zf:
                # Filter useful extensions to save time and disk
                valid_exts = ('.sqlite', '.db', '.sqlite3', '.db3', '.mapsdata', '.xlsx', '.xls', '.csv', 
                              '.jpg', '.jpeg', '.heic', '.png', '.gpx', '.kml', '.geojson', '.json', '.xml',
                              '.plist', '-wal', '-shm')
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    m_lower = member.filename.lower()
                    if any(m_lower.endswith(ext) for ext in valid_exts) or "cache" in m_lower or "location" in m_lower or "history" in m_lower or "geobookmarks" in m_lower:
                        try:
                            zf.extract(member, extract_dir)
                        except Exception:
                            pass
        elif tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path, 'r:*') as tf:
                tf.extractall(extract_dir)
