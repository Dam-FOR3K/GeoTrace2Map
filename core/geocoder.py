# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Geocoder & Network Resolvers
Supports Reverse Geocoding (Nominatim/OSM), Wi-Fi BSSID (WiGLE API), and Cell Tower lookups (MLS.db).
"""
import requests
import sqlite3
import os
import json
import time
from typing import Optional, Dict, Any, Tuple
from functools import lru_cache

# In-memory cache for reverse geocoding to avoid rate limits
_GEOCODE_CACHE: Dict[str, str] = {}
_LAST_REQUEST_TIME = 0.0

def reverse_geocode(lat: float, lon: float, email: str = "forensics@gt2m.local", allow_online: bool = False) -> Optional[str]:
    """
    Look up postal address from lat/lon via OpenStreetMap Nominatim with caching.
    Strictly blocked if allow_online is False (Forensic Air-Gap protection).
    """
    if not allow_online:
        return None

    global _LAST_REQUEST_TIME
    
    # Rounded cache key to ~10 meters
    cache_key = f"{round(lat, 4)},{round(lon, 4)}"
    if cache_key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[cache_key]
        
    # Respect Nominatim 1 req/sec policy
    now = time.time()
    if now - _LAST_REQUEST_TIME < 1.0:
        time.sleep(1.0 - (now - _LAST_REQUEST_TIME))
    _LAST_REQUEST_TIME = time.time()
    
    headers = {
        "User-Agent": "GeoTrace2Map_Forensic_Platform/1.0",
        "Accept-Language": "fr,en;q=0.8"
    }
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1&email={email}"
    
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            display_name = data.get("display_name")
            if display_name:
                _GEOCODE_CACHE[cache_key] = display_name
                return display_name
    except Exception:
        pass
        
    return None

def resolve_cell_tower(mcc: Any, mnc: Any, lac: Any, cid: Any, mls_db_path: str = "MLS.db") -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Look up Cell Tower coordinates (lat, lon, range) in a local MLS (Mozilla Location Service / OpenCellID) SQLite database.
    Returns: (lat, lon, range_meters)
    """
    if not os.path.exists(mls_db_path):
        return None, None, None
        
    try:
        # Convert hex if provided as hex string
        mcc_int = int(str(mcc))
        mnc_int = int(str(mnc))
        lac_int = int(str(lac), 16) if isinstance(lac, str) and lac.startswith(('0x', '0X')) else int(str(lac))
        cid_int = int(str(cid), 16) if isinstance(cid, str) and cid.startswith(('0x', '0X')) else int(str(cid))
        
        conn = sqlite3.connect(mls_db_path)
        cur = conn.cursor()
        cur.execute("SELECT lat, lon, range FROM MLS WHERE mcc = ? AND net = ? AND area = ? AND cell = ?", (mcc_int, mnc_int, lac_int, cid_int))
        row = cur.fetchone()
        conn.close()
        
        if row:
            return float(row[0]), float(row[1]), float(row[2]) if row[2] else 1000.0
    except Exception:
        pass
        
    return None, None, None

def resolve_wigle_bssid(bssid: str, wigle_api_name: str, wigle_api_token: str, allow_online: bool = False) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Query WiGLE API for Wi-Fi BSSID (MAC address).
    Strictly blocked if allow_online is False (Forensic Air-Gap protection).
    Returns: (lat, lon, ssid)
    """
    if not allow_online or not wigle_api_name or not wigle_api_token or not bssid:
        return None, None, None
        
    # Clean BSSID
    bssid_clean = bssid.strip().replace('-', ':').lower()
    url = f"https://api.wigle.net/api/v2/network/detail?netid={bssid_clean}"
    
    try:
        resp = requests.get(url, auth=(wigle_api_name, wigle_api_token), timeout=6)
        if resp.status_code == 200:
            res = resp.json().get("results")
            if res and len(res) > 0:
                lat = float(res[0].get("trilat"))
                lon = float(res[0].get("trilong"))
                ssid = res[0].get("ssid")
                return lat, lon, ssid
    except Exception:
        pass
        
    return None, None, None
