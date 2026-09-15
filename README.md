# GeoTrace2Map (GT2M) - Forensic Geolocation Extraction & Mapping Platform

**GeoTrace2Map (GT2M)** is an advanced Digital Forensics and Incident Response (DFIR) platform designed for automated extraction, normalization, deduplication, and interactive mapping of geolocation data from full smartphone physical/file system dumps (**iOS**, **Android**) and forensic extraction reports (**Cellebrite UFED**, **Oxygen Forensics**, etc.).

> **Author**: Developed by **Dam-FOR3K** | Forensic Geolocation & DFIR Tools

---

## 🌟 Key Features

### 1. Multi-Source Ingestion & Automated Detection
* **Full Extraction Archives**: .zip, .tar, .tgz, .tar.gz.
* **Uncompressed Local Directories**: Direct in-place scanning without disk duplication.
* **Forensic Extraction Reports**: .xlsx and .csv files from Cellebrite Physical Analyzer, UFED Reader, and Oxygen Forensics (with automated header row detection and timezone offsets UTC+X).
* **Standalone Files**: SQLite databases (.sqlite, .db, .db3, .mapsdata), track logs (.gpx, .kml, .geojson), Google Takeout JSON files, and media with embedded EXIF GPS tags (JPEG, HEIC, PNG, TIFF, WebP).
* **iOS Cache.sqlite & CFNetwork Harvester**: Deep inspection of application network caches (`Library/Caches/<bundle_id>/Cache.sqlite`), extracting GPS coordinates embedded in API request URLs (`cfurl_cache_response`), slippy map tile URLs (`/z/x/y.png`), cached response JSON blobs (`cfurl_cache_receiver_data`), and legacy `locationd` databases with Write-Ahead Log (`-wal`) binary carving.
* **Android MediaStore / MediaProvider (`external.db`)**: Direct extraction from Android MediaProvider databases indexing coordinates of camera photos and downloads, recovering evidence even if original image files have been purged.
* **Apple Maps GeoBookmarks & Pins (`GeoBookmarks.plist`)**: Automatic extraction of user saved places, Home/Work labels, and dropped pins from binary/XML plists.
* **Mobile Browser Navigation History**: Parsing Safari (`History.db`) and Google Chrome (`History`) for search URLs containing map destinations, Google/Apple Maps pins, and coordinate links.
* **SMS & Messaging Location Shares**: Detection of geographic links (`geo:`, Google Maps, Apple Maps, Waze) in iOS `sms.db`, Android `mmssms.db`, and chat applications.
* **Generic SQLite Scraper**: Heuristic pattern matching on unindexed SQLite databases to extract coordinates, accuracy, altitude, and epoch timestamps automatically.

### 2. Forensic Traceability & Chain of Custody
For every single geographic fix rendered on the interactive map:
* **Exact Source File**: Relative path within the extraction archive (e.g. ar/mobile/Library/Caches/com.apple.routined/CoreRoutine.sqlite).
* **Origin SQLite Table / Field / EXIF Tag**: E.g. ZRTCLLOCATIONMO (ZLATITUDE).
* **Multi-Zone Timestamp Normalization**:
  * UTC Date & Time (ISO 8601 standard).
  * Analyst's Local Date & Time.
  * Automated epoch resolution (Apple Cocoa CoreData 2001, WebKit/Chrome 1601, Unix seconds/ms/us/ns, GPS epoch 1980).
* **Horizontal Accuracy Radii**: Visual uncertainty circles scaled in meters (hAccuracy).
* **Media Thumbnails**: Embedded thumbnail preview for geotagged photographs.
* **Intelligent Deduplication & Corroboration**: Identical coordinates and timestamps are merged into a single clean map marker, while retaining full evidence provenance (e.g., Item #158 (Active table) corroborated by Item #548 (WAL journal/carved)).

### 3. Advanced Forensic Mobility Analytics
* **Trip & Session Segmentation**: Automatic grouping of fixes into distinct journeys based on inactivity thresholds and calendar days.
* **Stop Point & Dwell Time Detector (🛑)**: Identifies stationary periods (>= 10 minutes within a 65 m radius) with arrival time, departure time, and total dwell duration.
* **Velocity Filtering**: Estimated speeds (km/h) are computed chronologically and filtered by forensic GPS accuracy (<= 25 m) to eliminate erroneous satellite drift anomalies.
* **Directional Flow Animation (Ant Path)**: Live marching vector arrows indicating the true heading and direction of movement along trajectories.

### 4. Air-Gap Forensic Security & Privacy (Zero Data Leakage)
* **100% Offline Processing**: All parsing, calculations, and deduplication run strictly on your local CPU. No forensic data or coordinates ever leave the workstation.
* **Air-Gap Guard**: External lookups (Nominatim Reverse Geocoding, WiGLE BSSID) are blocked by default with explicit security notices to prevent leaking suspect or victim coordinates over the Internet.
* **Local Cell Tower Resolution**: Offline lookups via local `MLS.db` (Mozilla Location Service / OpenCellID) without network dependency.
* **Native Offline Map Support**: Direct rendering from local `.mbtiles` archives or `tiles/` folder.

### 5. Multi-Format Forensic Exports
* 🌍 **Standalone Portable HTML Report**: Self-contained HTML file embedding interactive maps, Ant Path animations, stop points, and evidence sheets (viewable offline on any browser without Python).
* 🌐 **Enriched Google Earth KML**: 3D timeline-enabled markers color-coded by forensic category.
* 🧭 **GPX Track & Waypoints**: Compatible with GIS tools (QGIS, ArcGIS) and GPS software.
* 📊 **Forensic CSV / Excel Spreadsheet**: Full tabular export including all technical chain-of-custody fields.

### 6. Bilingual User Interface (English / French)
* Full instant toggle between **English (EN)** and **French (FR)** across all controls, modals, metrics, inspector sheets, and popups, with preference saved in `localStorage`.

---

## 🗺️ Offline Cartography Setup (Air-Gap Operation)

To operate in a strictly air-gapped lab environment without Internet access, GeoTrace2Map (GT2M) provides built-in support for local map tiles:

### Supported Offline Formats
1. **SQLite MBTiles Archive (Recommended)**:
   * **Flexible Location**: Your `.mbtiles` file can be stored **anywhere** on your system (e.g., on a dedicated external forensic SSD, secondary hard drive, or network share, such as `D:\Forensic_Maps\france.mbtiles` or `/mnt/data/world.mbtiles`).
   * **Custom Path Configuration**: Open **Settings ⚙️** in the top navbar and type or paste your absolute or relative path. Windows quote marks (e.g., from *Copy as path*) are automatically sanitized.
   * **Live Validation & File Size Badge**: The settings dialog immediately validates the path and shows a green status badge with the exact file size (e.g., `✓ File detected and valid (3.42 GB)`).
   * **Persistent Configuration (`settings.json`)**: All settings, including your custom MBTiles path, are automatically saved to `settings.json` so you never have to re-enter the path after restarting the software.
   * **Direct SQLite Streaming**: The Python backend extracts the compressed PNG tiles on the fly directly from the database without requiring any third-party tile server.
2. **Standard Tiles Directory**:
   * You can also place raw pre-extracted tiles in a `tiles/` folder in the root directory: `tiles/{z}/{x}/{y}.png`.

### How to Get Offline Map Data
* **Pre-packaged MBTiles**: Download country or regional extracts from [OpenMapTiles](https://openmaptiles.org/downloads/) or [Protomaps Extracts](https://protomaps.com/extracts).
* **Mobile Atlas Creator (MOBAC)**:
  1. Download [MOBAC (portable Windows app)](https://mobac.sourceforge.io/).
  2. Select your map source (e.g., *OpenStreetMap Standard*).
  3. Select your geographic area (department, region, or country).
  4. Select zoom levels (e.g., zooms **6 to 16** for street and building details).
  5. Under *Atlas Settings*, select **`MBTiles SQLite`** (or *OpenStreetMap OsmTracker tile storage* for raw folders).
  6. Click **Create Atlas**, rename the output file to `map.mbtiles`, and drop it in the project root or configure your custom path in Settings.
* **QGIS**: Use the built-in *Generate XYZ Tiles (MBTiles)* tool from the Processing Toolbox.

### Enabling in the Interface
* In the map view, hover over the layer control (top-right corner of the map) and select **`Local Offline Map (Air-Gap)`** / **`Carte Hors-Ligne Locale (Air-Gap)`**.

---

## 📶 WiGLE BSSID Lookup Configuration

When analyzing Wi-Fi cache artifacts (e.g., iOS `locationd` `cache_encryptedA.db` or Android Wi-Fi caches) that contain MAC addresses (BSSIDs):

1. **Obtain API Credentials**: Register for free at [wigle.net](https://wigle.net) and generate your credentials under **Account > API Name & Token**.
2. **Enable Online Lookups**:
   * In GeoTrace2Map (GT2M), click the **⚙️ Settings** icon in the top navbar.
   * Check **"Allow external online queries"** (this explicitly disables the Air-Gap block for the session).
   * Enter your **WiGLE API Username** and **WiGLE API Token / Key**.
   * Click **Save**.
3. **Trigger Resolution**:
   * Click on any Wi-Fi point marker on the map.
   * In the right-hand **Forensic Origin Sheet**, click **`Lookup BSSID on WiGLE`** / **`Rechercher BSSID sur WiGLE`**.
   * The trilaterated GPS coordinates and network SSID will be fetched and stored with the point.

---

## 🚀 Quick Start

### Windows:
Simply double-click:
```cmd
start.bat
```
The script will check Python dependencies, launch the local server, and open your default browser at http://127.0.0.1:8765.

### Command Line (Windows / macOS / Linux):
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the platform
python run.py
```

---

## 📁 Targeted Artifact Matrix

| Operating System / Source | Artifact Location & Files | Recovered Forensic Data |
| :--- | :--- | :--- |
| **iOS System** | CoreRoutine.sqlite, **Local.sqlite** (`com.apple.routined`), cache_encryptedA.db, cache_encryptedB.db, lockCache_encryptedA.db, legacy locationd/Cache.sqlite (or consolidated.db) | GPS fixes, Significant visits, local frequent locations, paired Bluetooth vehicles, Wi-Fi hotspots, cell towers |
| **iOS Apps & Media** | Photos.sqlite, GeoHistory.mapsdata, **GeoBookmarks.plist**, **Safari (History.db)**, **SMS/iMessage (sms.db)**, WhatsApp (ChatStorage.sqlite), **App Cache.sqlite** (CFNetwork / NSURLCache in `Library/Caches/<bundle_id>/Cache.sqlite`: Google Maps, Apple Maps, Waze, Uber, Social Media, Browsers) | Geotagged camera rolls, Apple Maps search history & saved bookmarks/pins, Safari map searches, shared SMS pin drops, live locations, **embedded GPS coordinates in HTTP/API request URLs (`cfurl_cache_response`), slippy map tile URLs (`/z/x/y.png`), and carved WAL frames (`Cache.sqlite-wal`)** |
| **Android System** | gservices.db, location.db, fused_location, telephony.db, geolocation.db, **external.db / media.db (MediaStore / MediaProvider)** | Google Location History cache, Fused Location Provider, base stations (cell towers), **indexed image/video GPS coordinates from camera & downloads** |
| **Android Apps** | **Google Maps (`gmm_storage.db`, `da_destination_history`)**, **Chrome (`History`)**, **SMS/MMS (`mmssms.db`)**, WhatsApp (`msgstore.db`), Waze | Turn-by-turn navigation history, search destinations, web browser map searches, shared SMS/MMS geographic links & coordinates, shared WhatsApp coordinates |
| **Forensic Reports** | .xlsx / .csv (Cellebrite Physical Analyzer, UFED Reader, Oxygen) | Normalized location tables, carved records, WAL journal recoveries |
| **Raw Media & Tracks** | JPEG, HEIC, PNG, GPX, KML, Google Takeout JSON | EXIF GPS tags, GPX tracks, KML waypoints, Google Location records |
| **Generic Scraper** | Any unindexed .sqlite, .db, .db3 file | Heuristic extraction of latitude, longitude, timestamp, accuracy, altitude |

---

## ⚖️ License & Ethical Usage
Designed for law enforcement digital forensics units, certified private investigators, and cybersecurity DFIR teams. Ensure authorized forensic custody before analyzing evidentiary data.

---

## 👤 Author
Developed with passion by **Dam-FOR3K**.  
Feedback, suggestions, and forensic artifact contributions are welcome!
