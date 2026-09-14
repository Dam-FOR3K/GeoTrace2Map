# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Forensic Geolocation & Interactive Mapping Platform
FastAPI Application & Real-Time Interactive Dashboard
"""
import os
import shutil
import tempfile
import json
import sqlite3
import webbrowser
import threading
import time
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core.models import ForensicLocationPoint, ExtractionSummary
from core.engine import ForensicExtractorEngine
from core.geocoder import reverse_geocode, resolve_wigle_bssid
from exporters.kml_exporter import export_to_kml
from exporters.gpx_exporter import export_to_gpx
from exporters.csv_exporter import export_to_csv
from exporters.html_exporter import export_to_standalone_html

app = FastAPI(
    title="GeoTrace2Map",
    description="Plateforme Forensique d'Extraction et Cartographie de Géolocalisation Mobile (iOS, Android, UFED) - GT2M par Dam-FOR3K",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from core.analytics import analyze_trips_and_metrics

# Global Session State
CURRENT_POINTS: List[ForensicLocationPoint] = []
CURRENT_SUMMARY: ExtractionSummary = ExtractionSummary()
CURRENT_ANALYTICS: Dict[str, Any] = {"trips": [], "days": {}, "stop_points": [], "total_distance_km": 0.0, "max_speed_kmh": 0.0, "avg_speed_kmh": 0.0}
EXTRACTION_PROGRESS: Dict[str, Any] = {"percent": 0, "status": "Prêt", "points_count": 0, "active": False}
APP_SETTINGS: Dict[str, Any] = {
    "allow_online_lookups": False,  # Strict Forensic Air-Gap: no coordinates leave the machine
    "wigle_name": "",
    "wigle_key": "",
    "mls_db_path": "MLS.db",
    "mbtiles_path": "map.mbtiles",
    "osm_email": "forensics@gt2m.local"
}

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                APP_SETTINGS.update(data)
        except Exception:
            pass

def save_settings_to_file():
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(APP_SETTINGS, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

load_settings()

TILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiles")
os.makedirs(TILES_DIR, exist_ok=True)

LAST_LOADED_TARGET: Optional[str] = None
EXPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

@app.on_event("startup")
async def startup_event():
    print("[*] GeoTrace2Map (GT2M) initialisé en mode sécurisé hors-ligne (Air-Gap actif par défaut).")

@app.post("/api/reload")
async def reload_data():
    global CURRENT_POINTS, CURRENT_SUMMARY, CURRENT_ANALYTICS, LAST_LOADED_TARGET
    if LAST_LOADED_TARGET and os.path.exists(LAST_LOADED_TARGET):
        engine = ForensicExtractorEngine(mls_db_path=APP_SETTINGS["mls_db_path"])
        pts, summary = engine.process_target(LAST_LOADED_TARGET)
        CURRENT_POINTS = pts
        CURRENT_SUMMARY = summary
        CURRENT_ANALYTICS = analyze_trips_and_metrics(pts)
        return {"status": "success", "points_count": len(pts)}
    return {"status": "error", "message": "Aucun fichier actif à recharger."}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/", response_class=HTMLResponse)
async def index():
    """
    Renders the main full-featured web interface.
    """
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "dashboard.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Template non trouvé. Veuillez vérifier l'installation.</h1>")

def _resolve_mbtiles_path(raw_path: str) -> Tuple[str, bool, str]:
    """
    Resolves an absolute or relative MBTiles path, checks existence and returns (abs_path, exists, size_str).
    """
    clean = raw_path.strip().strip('"').strip("'") if raw_path else "map.mbtiles"
    if not clean:
        clean = "map.mbtiles"
    if not os.path.isabs(clean):
        abs_p = os.path.join(os.path.dirname(os.path.abspath(__file__)), clean)
    else:
        abs_p = clean
    
    exists = os.path.exists(abs_p) and os.path.isfile(abs_p)
    size_str = ""
    if exists:
        try:
            sz = os.path.getsize(abs_p)
            if sz >= 1024 * 1024 * 1024:
                size_str = f"{sz / (1024 * 1024 * 1024):.2f} Go"
            else:
                size_str = f"{sz / (1024 * 1024):.1f} Mo"
        except Exception:
            pass
    return abs_p, exists, size_str

@app.get("/api/state")
async def get_state():
    mbtiles_input = APP_SETTINGS.get("mbtiles_path", "map.mbtiles")
    abs_mb, mb_exists, mb_size = _resolve_mbtiles_path(mbtiles_input)
    has_offline = (os.path.exists(TILES_DIR) and len(os.listdir(TILES_DIR)) > 0) or mb_exists
    return {
        "summary": CURRENT_SUMMARY.model_dump(),
        "points_count": len(CURRENT_POINTS),
        "progress": EXTRACTION_PROGRESS,
        "analytics": CURRENT_ANALYTICS,
        "settings": {
            "allow_online_lookups": APP_SETTINGS["allow_online_lookups"],
            "has_wigle": bool(APP_SETTINGS["wigle_name"] and APP_SETTINGS["wigle_key"]),
            "mls_db_exists": os.path.exists(APP_SETTINGS["mls_db_path"]),
            "mbtiles_exists": mb_exists,
            "mbtiles_path": mbtiles_input,
            "mbtiles_size": mb_size,
            "has_offline_tiles": has_offline
        }
    }

@app.get("/tiles/{z}/{x}/{y}.png")
async def get_offline_tile(z: int, x: int, y: int):
    """
    Serves offline map tiles from local 'tiles/{z}/{x}/{y}.png' directory
    or from any custom MBTiles file path specified by the analyst (e.g. D:/Maps/france.mbtiles).
    """
    # 1. Try file directory tiles/z/x/y.png
    tile_file = os.path.join(TILES_DIR, str(z), str(x), f"{y}.png")
    if os.path.exists(tile_file):
        return FileResponse(tile_file, media_type="image/png")

    # 2. Try MBTiles archive from user's custom path
    mbtiles_input = APP_SETTINGS.get("mbtiles_path", "map.mbtiles")
    abs_mb, mb_exists, _ = _resolve_mbtiles_path(mbtiles_input)
    if mb_exists:
        try:
            # MBTiles uses TMS coordinates for row: (1 << z) - 1 - y
            tms_y = (1 << z) - 1 - y
            conn = sqlite3.connect(abs_mb)
            cur = conn.cursor()
            cur.execute("SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?", (z, x, tms_y))
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                return Response(content=row[0], media_type="image/png")
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="Tuile hors-ligne non trouvée.")

@app.get("/api/analytics")
async def get_analytics():
    return CURRENT_ANALYTICS

@app.get("/api/points")
async def get_points(
    category: Optional[str] = None,
    accuracy_max: Optional[float] = None,
    search: Optional[str] = None,
    day: Optional[str] = None,
    trip_id: Optional[int] = None
):
    """
    Returns the extracted points with optional filtering.
    """
    filtered = CURRENT_POINTS
    if category:
        cats = category.split(",")
        filtered = [p for p in filtered if p.category in cats]
    if accuracy_max is not None:
        filtered = [p for p in filtered if p.accuracy is None or p.accuracy <= accuracy_max]
    if day:
        filtered = [p for p in filtered if p.timestamp_utc and p.timestamp_utc.startswith(day)]
    if trip_id is not None:
        trip = next((t for t in CURRENT_ANALYTICS.get("trips", []) if t.get("trip_id") == trip_id), None)
        if trip:
            target_ids = set(trip.get("point_ids", []))
            filtered = [p for p in filtered if p.id in target_ids]
    if search:
        s_lower = search.lower().strip()
        filtered = [
            p for p in filtered 
            if s_lower in p.source_type.lower() or s_lower in p.source_file.lower() or s_lower in (p.table_or_field or "").lower()
        ]
        
    for p in filtered:
        if p.accuracy is not None and p.accuracy > 25.0:
            p.speed = None
            
    return [p.model_dump() for p in filtered]

def _progress_callback(pct: int, msg: str, count: int):
    global EXTRACTION_PROGRESS
    EXTRACTION_PROGRESS = {
        "percent": pct,
        "status": msg,
        "points_count": count,
        "active": pct < 100
    }

def _run_extraction_task(file_path: str, is_temp: bool = False):
    global CURRENT_POINTS, CURRENT_SUMMARY, CURRENT_ANALYTICS, EXTRACTION_PROGRESS
    try:
        EXTRACTION_PROGRESS["active"] = True
        engine = ForensicExtractorEngine(mls_db_path=APP_SETTINGS["mls_db_path"])
        pts, summary = engine.process_target(file_path, progress_callback=_progress_callback)
        CURRENT_POINTS = pts
        CURRENT_SUMMARY = summary
        CURRENT_ANALYTICS = analyze_trips_and_metrics(pts)
    except Exception as e:
        EXTRACTION_PROGRESS["status"] = f"Erreur : {str(e)}"
        EXTRACTION_PROGRESS["active"] = False
    finally:
        if is_temp and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

@app.post("/api/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload an archive (ZIP/TAR) or extraction file for processing.
    """
    global EXTRACTION_PROGRESS
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}")
    temp_file_path = temp_file.name
    
    try:
        EXTRACTION_PROGRESS = {"percent": 2, "status": f"Téléversement de {file.filename}...", "points_count": 0, "active": True}
        shutil.copyfileobj(file.file, temp_file)
        temp_file.close()
        
        background_tasks.add_task(_run_extraction_task, temp_file_path, is_temp=True)
        return {"status": "success", "message": f"Fichier {file.filename} reçu, extraction lancée en arrière-plan."}
    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scan-local-folder")
async def scan_local_folder(
    background_tasks: BackgroundTasks,
    folder_path: str = Form(...)
):
    """
    Scan an already extracted folder directly from the local disk.
    """
    folder_path = folder_path.strip().strip('"').strip("'")
    if not os.path.exists(folder_path):
        raise HTTPException(status_code=400, detail=f"Dossier introuvable : {folder_path}")
        
    background_tasks.add_task(_run_extraction_task, folder_path, is_temp=False)
    return {"status": "success", "message": f"Dossier {folder_path} ciblé, extraction démarrée."}

@app.post("/api/reverse-geocode")
async def geocode_point(point_id: str = Form(...)):
    """
    Reverse geocodes a specific point on demand and stores its address.
    Strictly blocked if allow_online_lookups is False (Air-Gap Protection).
    """
    if not APP_SETTINGS.get("allow_online_lookups", False):
        raise HTTPException(
            status_code=403, 
            detail="Mode Sécurité Hors-Ligne Strict actif : la transmission de coordonnées GPS sur Internet est bloquée pour préserver le secret de l'enquête. Vous pouvez l'autoriser explicitement dans les Paramètres."
        )
    global CURRENT_POINTS
    pt = next((p for p in CURRENT_POINTS if p.id == point_id), None)
    if not pt:
        raise HTTPException(status_code=404, detail="Point introuvable.")
        
    addr = reverse_geocode(pt.latitude, pt.longitude, email=APP_SETTINGS["osm_email"], allow_online=True)
    if addr:
        pt.address = addr
        return {"status": "success", "address": addr}
    return {"status": "not_found", "message": "Adresse non trouvée ou limite atteinte."}

@app.post("/api/wigle-lookup")
async def wigle_lookup(bssid: str = Form(...), point_id: Optional[str] = Form(None)):
    """
    Looks up a Wi-Fi BSSID (MAC address) via WiGLE API.
    Strictly blocked if allow_online_lookups is False (Air-Gap Protection).
    """
    if not APP_SETTINGS.get("allow_online_lookups", False):
        raise HTTPException(
            status_code=403, 
            detail="Mode Sécurité Hors-Ligne Strict actif : la transmission de requêtes sur Internet est bloquée pour préserver le secret de l'enquête. Vous pouvez l'autoriser explicitement dans les Paramètres."
        )
    wigle_name = APP_SETTINGS.get("wigle_name")
    wigle_key = APP_SETTINGS.get("wigle_key")
    if not wigle_name or not wigle_key:
        raise HTTPException(
            status_code=400,
            detail="Identifiants WiGLE non configurés. Veuillez renseigner votre WiGLE Username et Token dans les Paramètres (icône ⚙️)."
        )
        
    lat, lon, ssid = resolve_wigle_bssid(bssid, wigle_name, wigle_key, allow_online=True)
    if lat is not None and lon is not None:
        global CURRENT_POINTS
        if point_id:
            pt = next((p for p in CURRENT_POINTS if p.id == point_id), None)
            if pt:
                if not pt.extra_data:
                    pt.extra_data = {}
                pt.extra_data["WiGLE_SSID"] = ssid or "Inconnu"
                pt.extra_data["WiGLE_Coordinates"] = f"{lat}, {lon}"
        return {"status": "success", "latitude": lat, "longitude": lon, "ssid": ssid}
    return {"status": "not_found", "message": f"BSSID {bssid} introuvable dans la base WiGLE."}

@app.get("/api/export/{fmt}")
async def export_data(fmt: str):
    """
    Generates and downloads KML, GPX, CSV, or standalone HTML.
    """
    if not CURRENT_POINTS:
        raise HTTPException(status_code=400, detail="Aucune donnée à exporter.")
        
    t_stamp = time.strftime("%Y%m%d_%H%M%S")
    fmt_clean = fmt.lower()
    
    if fmt_clean == "kml":
        out_path = os.path.join(EXPORT_DIR, f"GeoTrace2Map_Export_{t_stamp}.kml")
        export_to_kml(CURRENT_POINTS, out_path)
        return FileResponse(out_path, filename=f"GeoTrace2Map_Export_{t_stamp}.kml", media_type="application/vnd.google-earth.kml+xml")
    elif fmt_clean == "gpx":
        out_path = os.path.join(EXPORT_DIR, f"GeoTrace2Map_Export_{t_stamp}.gpx")
        export_to_gpx(CURRENT_POINTS, out_path)
        return FileResponse(out_path, filename=f"GeoTrace2Map_Export_{t_stamp}.gpx", media_type="application/gpx+xml")
    elif fmt_clean == "csv":
        out_path = os.path.join(EXPORT_DIR, f"GeoTrace2Map_Export_{t_stamp}.csv")
        export_to_csv(CURRENT_POINTS, out_path)
        return FileResponse(out_path, filename=f"GeoTrace2Map_Export_{t_stamp}.csv", media_type="text/csv")
    elif fmt_clean == "html":
        out_path = os.path.join(EXPORT_DIR, f"GeoTrace2Map_Rapport_Autonome_{t_stamp}.html")
        export_to_standalone_html(CURRENT_POINTS, CURRENT_SUMMARY, out_path)
        return FileResponse(out_path, filename=f"GeoTrace2Map_Rapport_Autonome_{t_stamp}.html", media_type="text/html")
    else:
        raise HTTPException(status_code=400, detail=f"Format d'export inconnu : {fmt}")

@app.post("/api/settings")
async def save_settings(
    allow_online: Optional[str] = Form("false"),
    wigle_name: Optional[str] = Form(""),
    wigle_key: Optional[str] = Form(""),
    mls_db_path: Optional[str] = Form("MLS.db"),
    mbtiles_path: Optional[str] = Form("map.mbtiles")
):
    global APP_SETTINGS
    APP_SETTINGS["allow_online_lookups"] = allow_online.lower() in ("true", "1", "yes", "on")
    APP_SETTINGS["wigle_name"] = wigle_name.strip() if wigle_name else ""
    APP_SETTINGS["wigle_key"] = wigle_key.strip() if wigle_key else ""
    APP_SETTINGS["mls_db_path"] = mls_db_path.strip().strip('"').strip("'") if mls_db_path else "MLS.db"
    APP_SETTINGS["mbtiles_path"] = mbtiles_path.strip().strip('"').strip("'") if mbtiles_path else "map.mbtiles"
    save_settings_to_file()
    return {"status": "success", "message": "Paramètres enregistrés et sauvegardés avec succès."}

def start_server(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True):
    if open_browser:
        def _open():
            time.sleep(1.2)
            webbrowser.open(f"http://{host}:{port}")
        threading.Thread(target=_open, daemon=True).start()
        
    uvicorn.run("app:app", host=host, port=port, reload=True, log_level="info")

if __name__ == "__main__":
    start_server()
