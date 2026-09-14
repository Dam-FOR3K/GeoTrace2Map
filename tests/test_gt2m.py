# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Automated Test Suite & Validation Script
"""
import sys
import os
import sqlite3
import zipfile
import tempfile
import pandas as pd
from PIL import Image, ExifTags

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import ForensicExtractorEngine
from exporters.kml_exporter import export_to_kml
from exporters.gpx_exporter import export_to_gpx
from exporters.csv_exporter import export_to_csv
from exporters.html_exporter import export_to_standalone_html

def create_synthetic_test_zip(output_zip_path: str):
    temp_dir = tempfile.mkdtemp(prefix="test_gt2m_")
    
    try:
        # 1. Create simulated iOS CoreRoutine.sqlite
        ios_dir = os.path.join(temp_dir, "private", "var", "mobile", "Library", "Caches", "com.apple.routined")
        os.makedirs(ios_dir, exist_ok=True)
        cr_db_path = os.path.join(ios_dir, "CoreRoutine.sqlite")
        
        conn = sqlite3.connect(cr_db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE ZRTCLLOCATIONMO (
                ZLATITUDE REAL, ZLONGITUDE REAL, ZALTITUDE REAL, 
                ZHORIZONTALACCURACY REAL, ZVERTICALACCURACY REAL, 
                ZSPEED REAL, ZCOURSE REAL, ZTIMESTAMP REAL
            )
        """)
        # Cocoa timestamp: 700000000 -> 2023-03-08
        cur.execute("INSERT INTO ZRTCLLOCATIONMO VALUES (48.8584, 2.2945, 35.0, 8.5, 3.0, 1.2, 90.0, 700000000.0)")
        
        cur.execute("""
            CREATE TABLE ZRTVISITMO (
                ZLOCATIONLATITUDE REAL, ZLOCATIONLONGITUDE REAL, 
                ZLOCATIONHORIZONTALACCURACY REAL, ZENTRYDATE REAL, 
                ZEXITDATE REAL, ZCONFIDENCE REAL
            )
        """)
        cur.execute("INSERT INTO ZRTVISITMO VALUES (48.8606, 2.3376, 12.0, 700010000.0, 700020000.0, 1.0)")
        conn.commit()
        conn.close()

        # 2. Create simulated Android location.db
        android_dir = os.path.join(temp_dir, "data", "data", "com.google.android.gms", "databases")
        os.makedirs(android_dir, exist_ok=True)
        and_db_path = os.path.join(android_dir, "location.db")
        
        conn = sqlite3.connect(and_db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE locations (
                latitude REAL, longitude REAL, altitude REAL, accuracy REAL, timestamp INTEGER, provider TEXT
            )
        """)
        # Unix MS timestamp
        cur.execute("INSERT INTO locations VALUES (45.7640, 4.8357, 170.0, 15.0, 1680000000000, 'fused')")
        conn.commit()
        conn.close()

        # 3. Create simulated UFED report Excel file
        ufed_path = os.path.join(temp_dir, "Cellebrite_UFED_Report.xlsx")
        df = pd.DataFrame([
            {
                "#": 1,
                "Time": "2023-05-10 14:30:00",
                "Origin": "WhatsApp",
                "Category": "Shared Location",
                "Name": "Rendez-vous Gare",
                "Description": "Position envoyée par l'utilisateur",
                "Latitude": 43.6047,
                "Longitude": 1.4442,
                "Accuracy": 20.0
            }
        ])
        df.to_excel(ufed_path, index=False)

        # 4. Create simulated GPX file
        gpx_path = os.path.join(temp_dir, "track.gpx")
        with open(gpx_path, 'w', encoding='utf-8') as f:
            f.write("""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Test">
  <trk><trkseg>
    <trkpt lat="43.2965" lon="5.3698"><ele>10.0</ele><time>2023-06-01T12:00:00Z</time><name>Vieux-Port</name></trkpt>
  </trkseg></trk>
</gpx>""")

        # 5. Create simulated JPEG image with EXIF GPS
        img_path = os.path.join(temp_dir, "DCIM_001.jpg")
        img = Image.new('RGB', (200, 200), color=(73, 109, 137))
        exif = img.getexif()
        gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
        gps_ifd[1] = 'N'                           # GPSLatitudeRef
        gps_ifd[2] = (48.0, 51.0, 24.0)            # GPSLatitude (DMS)
        gps_ifd[3] = 'E'                           # GPSLongitudeRef
        gps_ifd[4] = (2.0, 21.0, 7.0)              # GPSLongitude (DMS)
        gps_ifd[29] = '2023:07:15'                 # GPSDateStamp
        img.save(img_path, "jpeg", exif=exif)

        # 6. Create simulated iOS NSURLCache Cache.sqlite
        cache_dir = os.path.join(temp_dir, "private", "var", "mobile", "Containers", "Data", "Application", "TEST_UUID", "Library", "Caches", "com.example.app")
        os.makedirs(cache_dir, exist_ok=True)
        cache_db_path = os.path.join(cache_dir, "Cache.sqlite")
        conn = sqlite3.connect(cache_db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE cfurl_cache_response (
                entry_ID INTEGER PRIMARY KEY,
                request_key TEXT,
                time_stamp REAL
            )
        """)
        cur.execute("INSERT INTO cfurl_cache_response VALUES (1, 'https://api.example.com/search?lat=43.6047&lon=1.4442&radius=100', 700030000.0)")
        conn.commit()
        conn.close()

        # 7. Create simulated Cache.sqlite-wal containing an uncommitted/carved URL
        wal_file_path = cache_db_path + "-wal"
        with open(wal_file_path, "wb") as wf:
            # Write binary WAL padding and an embedded URL
            wf.write(b"\x37\x7f\x06\x82" + b"\x00" * 256)
            wf.write(b"GET https://maps.apple.com/?lat=44.8378&lon=-0.5792&mode=driving HTTP/1.1\r\nHost: maps.apple.com\r\n")
            wf.write(b"\x00" * 512)

        # Pack into ZIP
        with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(temp_dir):
                for f in files:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, temp_dir)
                    zf.write(full_p, rel_p.replace('\\', '/'))
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

def run_tests():
    print("[*] Démarrage des tests de validation GeoTrace2Map (GT2M)...")
    
    test_zip = os.path.join(tempfile.gettempdir(), "gt2m_test_extraction.zip")
    create_synthetic_test_zip(test_zip)
    print(f"[+] Archive de test générée : {test_zip}")

    engine = ForensicExtractorEngine()
    points, summary = engine.process_target(test_zip)

    print(f"[+] Points extraits : {len(points)} (Total brut: {summary.total_points})")
    print(f"[+] Sources détectées : {summary.sources_count}")
    print(f"[+] OS détectés : {summary.detected_os}")
    print(f"[+] Période : {summary.date_min} à {summary.date_max}")

    # Assertions
    assert len(points) >= 5, f"Erreur : attendu au moins 5 points, obtenu {len(points)}"
    
    # Test exporters
    export_dir = os.path.join(tempfile.gettempdir(), "gt2m_test_exports")
    os.makedirs(export_dir, exist_ok=True)
    
    kml_p = os.path.join(export_dir, "test.kml")
    gpx_p = os.path.join(export_dir, "test.gpx")
    csv_p = os.path.join(export_dir, "test.csv")
    html_p = os.path.join(export_dir, "test.html")
    
    export_to_kml(points, kml_p)
    export_to_gpx(points, gpx_p)
    export_to_csv(points, csv_p)
    export_to_standalone_html(points, summary, html_p)

    assert os.path.exists(kml_p) and os.path.getsize(kml_p) > 500, "Erreur export KML"
    assert os.path.exists(gpx_p) and os.path.getsize(gpx_p) > 300, "Erreur export GPX"
    assert os.path.exists(csv_p) and os.path.getsize(csv_p) > 300, "Erreur export CSV"
    assert os.path.exists(html_p) and os.path.getsize(html_p) > 1000, "Erreur export HTML"

    print("\n[OK] TOUS LES TESTS ONT REUSSI AVEC SUCCES !")

if __name__ == "__main__":
    run_tests()
