# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Standalone HTML Forensic Report Generator
Creates a 100% portable, interactive single-file HTML report with embedded Leaflet map, MarkerCluster, Heatmap, and timeline.
"""
import json
from typing import List
from core.models import ForensicLocationPoint, ExtractionSummary

def export_to_standalone_html(
    points: List[ForensicLocationPoint], 
    summary: ExtractionSummary, 
    output_path: str,
    title: str = "GeoTrace2Map (GT2M) - Rapport Forensique Géolocalisation"
):
    points_dict_list = []
    for p in points:
        p_dict = p.model_dump()
        points_dict_list.append(p_dict)
        
    points_json = json.dumps(points_dict_list, ensure_ascii=False)
    summary_json = json.dumps(summary.model_dump(), ensure_ascii=False)
    
    html_content = f"""<!DOCTYPE html>
<html lang="fr" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  
  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {{
      darkMode: 'class',
      theme: {{
        extend: {{
          colors: {{
            brand: {{ 50: '#f0fdf4', 500: '#22c55e', 600: '#16a34a', 700: '#15803d' }},
            forensic: {{ 800: '#0f172a', 900: '#020617' }}
          }}
        }}
      }}
    }}
  </script>
  
  <!-- FontAwesome -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  
  <!-- Leaflet CSS & JS -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  
  <!-- Leaflet MarkerCluster -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
  <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
  
  <!-- Leaflet Heat -->
  <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>

  <!-- Leaflet Ant Path -->
  <script src="https://cdn.jsdelivr.net/npm/leaflet-ant-path@1.3.0/dist/leaflet-ant-path.min.js"></script>

  <style>
    #map {{ height: calc(100vh - 65px); width: 100%; }}
    .custom-scrollbar::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    .custom-scrollbar::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 4px; }}
    .leaflet-popup-content-wrapper {{ background: #0f172a; color: #f8fafc; border-radius: 8px; border: 1px solid #334155; }}
    .leaflet-popup-tip {{ background: #0f172a; }}
  </style>
</head>
<body class="bg-slate-950 text-slate-100 flex flex-col h-screen overflow-hidden">

  <!-- Top Navbar -->
  <header class="h-[65px] bg-slate-900 border-b border-slate-800 px-4 flex items-center justify-between shrink-0">
    <div class="flex items-center space-x-3">
      <div class="w-10 h-10 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
        <i class="fa-solid fa-map-location-dot text-xl"></i>
      </div>
      <div>
        <h1 class="font-bold text-lg leading-tight flex items-center gap-2">
          <span>GeoTrace2Map</span>
          <span class="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">GT2M • Rapport Autonome</span>
          <span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">by Dam-FOR3K</span>
        </h1>
        <p class="text-xs text-slate-400" id="summary-badge">Analyse Forensique Géolocalisation</p>
      </div>
    </div>

    <!-- Quick Stats -->
    <div class="hidden md:flex items-center space-x-6 text-xs">
      <div class="flex flex-col items-center">
        <span class="text-slate-400">Points Détectés</span>
        <span class="font-bold text-sm text-emerald-400" id="stat-total">0</span>
      </div>
      <div class="h-6 w-px bg-slate-800"></div>
      <div class="flex flex-col items-center">
        <span class="text-slate-400">Période Couverte</span>
        <span class="font-semibold text-slate-200" id="stat-dates">N/A</span>
      </div>
      <div class="h-6 w-px bg-slate-800"></div>
      <div class="flex flex-col items-center">
        <span class="text-slate-400">OS Cibles</span>
        <span class="font-semibold text-amber-400" id="stat-os">N/A</span>
      </div>
    </div>

    <!-- Controls -->
    <div class="flex items-center space-x-2">
      <button onclick="toggleHeatmap()" id="btn-heatmap" class="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 flex items-center gap-1.5 transition">
        <i class="fa-solid fa-fire text-orange-400"></i> Heatmap
      </button>
      <button onclick="togglePolyline()" id="btn-track" class="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 flex items-center gap-1.5 transition">
        <i class="fa-solid fa-route text-sky-400"></i> Trajet
      </button>
      <button onclick="toggleSidebar()" class="px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white flex items-center gap-1.5 transition shadow-sm">
        <i class="fa-solid fa-filter"></i> Filtres & Détails
      </button>
    </div>
  </header>

  <!-- Main Container -->
  <div class="flex-1 flex relative overflow-hidden">

    <!-- Map Container -->
    <div class="flex-1 relative">
      <div id="map"></div>

      <!-- Playback / Timeline Control Bar -->
      <div class="absolute bottom-4 left-4 right-4 z-[1000] bg-slate-900/90 backdrop-blur-md border border-slate-700/60 rounded-xl p-3 shadow-2xl flex flex-col gap-2 max-w-2xl mx-auto">
        <div class="flex items-center justify-between text-xs text-slate-300">
          <div class="flex items-center gap-2">
            <button onclick="togglePlayAnimation()" id="btn-play" class="w-7 h-7 rounded-lg bg-emerald-500 text-slate-950 flex items-center justify-center font-bold hover:bg-emerald-400">
              <i class="fa-solid fa-play" id="play-icon"></i>
            </button>
            <span class="font-medium text-slate-200">Timeline / Lecture Chronologique</span>
          </div>
          <span class="text-xs font-mono text-emerald-400" id="current-timeline-date">Tous les points</span>
        </div>
        <input type="range" id="timeline-slider" min="0" max="100" value="100" class="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-500" oninput="onTimelineChange(this.value)">
      </div>
    </div>

    <!-- Right Collapsible Sidebar (Filters & Details) -->
    <div id="sidebar" class="w-96 bg-slate-900 border-l border-slate-800 flex flex-col shrink-0 transition-all duration-300 z-[1001] shadow-2xl">
      <!-- Sidebar Header -->
      <div class="p-3 border-b border-slate-800 flex items-center justify-between">
        <h2 class="font-semibold text-sm flex items-center gap-2">
          <i class="fa-solid fa-sliders text-emerald-400"></i> Filtres & Origines
        </h2>
        <button onclick="toggleSidebar()" class="text-slate-400 hover:text-slate-200 text-sm p-1">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      <!-- Filter Controls -->
      <div class="p-4 space-y-4 overflow-y-auto custom-scrollbar flex-1">
        <!-- Search -->
        <div>
          <label class="text-xs font-medium text-slate-400 block mb-1">Recherche (Fichier, Table, Lieu)</label>
          <div class="relative">
            <i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-slate-500 text-xs"></i>
            <input type="text" id="search-input" placeholder="Ex: CoreRoutine, WhatsApp, Paris..." oninput="applyFilters()" class="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-emerald-500">
          </div>
        </div>

        <!-- Accuracy Slider -->
        <div>
          <div class="flex justify-between text-xs text-slate-400 mb-1">
            <span>Précision Max</span>
            <span id="acc-value" class="text-slate-200 font-mono">Toutes</span>
          </div>
          <input type="range" id="accuracy-slider" min="5" max="5000" step="5" value="5000" class="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-500" oninput="onAccuracyChange(this.value)">
        </div>

        <!-- Categories Filter -->
        <div>
          <label class="text-xs font-medium text-slate-400 block mb-2">Sources & Catégories</label>
          <div class="space-y-1.5" id="category-filters">
            <!-- Rendered dynamically -->
          </div>
        </div>

        <!-- Selected Point Forensic Detail Card -->
        <div id="point-details" class="mt-4 pt-4 border-t border-slate-800">
          <h3 class="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <i class="fa-solid fa-fingerprint text-emerald-400"></i> Fiche Origine Médico-Légale
          </h3>
          <div id="detail-content" class="text-xs text-slate-400 italic bg-slate-950 p-3 rounded-lg border border-slate-800">
            Cliquez sur un marqueur sur la carte pour inspecter sa provenance exacte.
          </div>
        </div>
      </div>
    </div>

  </div>

  <!-- Embedded Dataset -->
  <script>
    const POINTS_DATA = {points_json};
    const SUMMARY_DATA = {summary_json};
    
    // Map State
    let map;
    let markersLayer;
    let heatLayer;
    let polylineLayer;
    let currentFilteredPoints = [...POINTS_DATA];
    let isHeatmapActive = false;
    let isTrackActive = false;
    let isPlaying = false;
    let playInterval = null;
    let selectedAccuracy = 5000;
    let activeCategories = new Set();

    const CATEGORY_COLORS = {{
      gps_fix: '#22c55e',       // Green
      exif_photo: '#f97316',    // Orange
      system_routine: '#38bdf8',// Sky Blue
      wifi: '#eab308',          // Yellow
      cell_tower: '#ef4444',    // Red
      messaging: '#d946ef',     // Pink/Purple
      navigation: '#a855f7',    // Purple
      generic: '#94a3b8'        // Slate
    }};

    const CATEGORY_NAMES = {{
      gps_fix: 'GPS Direct / Fix',
      exif_photo: 'Photos & Médias EXIF',
      system_routine: 'Système (CoreRoutine, Routine)',
      wifi: 'Triangulation Wi-Fi',
      cell_tower: 'Antenne Relais Cellulaire',
      messaging: 'Messageries (WhatsApp, etc.)',
      navigation: 'Navigation (Maps, Waze)',
      generic: 'Autres Bases SQLite'
    }};

    // Init App
    window.addEventListener('DOMContentLoaded', () => {{
      initUIStats();
      initMap();
      initCategoryFilters();
      renderPoints();
    }});

    function initUIStats() {{
      document.getElementById('stat-total').textContent = POINTS_DATA.length.toLocaleString('fr-FR');
      document.getElementById('stat-os').textContent = (SUMMARY_DATA.detected_os || []).join(', ') || 'N/A';
      if (SUMMARY_DATA.date_min && SUMMARY_DATA.date_max) {{
        const d1 = SUMMARY_DATA.date_min.split('T')[0];
        const d2 = SUMMARY_DATA.date_max.split('T')[0];
        document.getElementById('stat-dates').textContent = `${{d1}} → ${{d2}}`;
      }}
    }}

    function initMap() {{
      // Base Layers
      const osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        attribution: '© OpenStreetMap contributors'
      }});
      const dark = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
        attribution: '© CARTO'
      }});
      const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
        attribution: 'Tiles © Esri'
      }});

      map = L.map('map', {{
        center: POINTS_DATA.length > 0 ? [POINTS_DATA[0].latitude, POINTS_DATA[0].longitude] : [48.8566, 2.3522],
        zoom: 12,
        layers: [osm]
      }});

      L.control.layers({{
        "OpenStreetMap (Recommandé)": osm,
        "Vue Satellite HD": satellite,
        "Carte Sombre (Forensic)": dark
      }}).addTo(map);

      markersLayer = L.markerClusterGroup({{
        maxClusterRadius: 40,
        showCoverageOnHover: false,
        spiderfyOnMaxZoom: true
      }});
      map.addLayer(markersLayer);
    }}

    function initCategoryFilters() {{
      const container = document.getElementById('category-filters');
      const catsInSummary = SUMMARY_DATA.categories_count || {{}};
      
      Object.keys(catsInSummary).forEach(cat => {{
        activeCategories.add(cat);
        const count = catsInSummary[cat];
        const color = CATEGORY_COLORS[cat] || '#94a3b8';
        const label = CATEGORY_NAMES[cat] || cat;

        const row = document.createElement('label');
        row.className = 'flex items-center justify-between p-2 rounded bg-slate-950/80 border border-slate-800 cursor-pointer hover:border-slate-700 text-xs';
        row.innerHTML = `
          <div class="flex items-center gap-2">
            <input type="checkbox" checked value="${{cat}}" onchange="onCategoryToggle(this)" class="rounded bg-slate-900 border-slate-700 text-emerald-500 focus:ring-0">
            <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${{color}}"></span>
            <span class="text-slate-300 font-medium">${{label}}</span>
          </div>
          <span class="font-mono text-slate-400 font-semibold">${{count}}</span>
        `;
        container.appendChild(row);
      }});
    }}

    function onCategoryToggle(cb) {{
      if (cb.checked) {{
        activeCategories.add(cb.value);
      }} else {{
        activeCategories.delete(cb.value);
      }}
      applyFilters();
    }}

    function onAccuracyChange(val) {{
      selectedAccuracy = parseInt(val);
      document.getElementById('acc-value').textContent = selectedAccuracy >= 5000 ? 'Toutes' : `< ${{selectedAccuracy}} m`;
      applyFilters();
    }}

    function applyFilters() {{
      const search = document.getElementById('search-input').value.toLowerCase().trim();
      
      currentFilteredPoints = POINTS_DATA.filter(p => {{
        // Category check
        if (!activeCategories.has(p.category)) return false;
        
        // Accuracy check
        if (selectedAccuracy < 5000 && p.accuracy && p.accuracy > selectedAccuracy) return false;
        
        // Search query check
        if (search) {{
          const targetStr = `${{p.source_type}} ${{p.source_file}} ${{p.table_or_field || ''}} ${{JSON.stringify(p.extra_data || {{}})}}`.toLowerCase();
          if (!targetStr.includes(search)) return false;
        }}
        
        return true;
      }});

      renderPoints();
    }}

    function renderPoints() {{
      markersLayer.clearLayers();
      if (heatLayer) map.removeLayer(heatLayer);
      if (polylineLayer) map.removeLayer(polylineLayer);

      const latlngs = [];
      const heatCoords = [];

      // Group points sharing the exact same coordinates
      const locationMap = new Map();
      currentFilteredPoints.forEach(p => {{
        const key = `${{p.latitude.toFixed(6)}},${{p.longitude.toFixed(6)}}`;
        if (!locationMap.has(key)) {{
          locationMap.set(key, []);
        }}
        locationMap.get(key).push(p);
      }});

      locationMap.forEach((ptsAtLoc, key) => {{
        const firstPt = ptsAtLoc[0];
        const latlng = [firstPt.latitude, firstPt.longitude];
        latlngs.push(latlng);
        heatCoords.push([firstPt.latitude, firstPt.longitude, Math.min(1.0, 0.4 + 0.2 * ptsAtLoc.length)]);

        const isMulti = ptsAtLoc.length > 1;
        const color = isMulti ? '#3b82f6' : (CATEGORY_COLORS[firstPt.category] || '#94a3b8');

        // Circle Marker
        const marker = L.circleMarker(latlng, {{
          radius: isMulti ? 9 : 7,
          fillColor: color,
          color: isMulti ? '#fbbf24' : '#ffffff',
          weight: isMulti ? 2.5 : 1.5,
          opacity: 1,
          fillOpacity: 0.9
        }});

        marker.on('click', () => showPointDetail(firstPt));
        
        let popupContent = '';
        if (isMulti) {{
          popupContent = `
            <div class="text-xs p-1 max-w-sm font-sans space-y-2">
              <div class="font-bold text-sm text-amber-400 flex items-center justify-between pb-1.5 border-b border-slate-700">
                <span>📍 ${{ptsAtLoc.length}} Événements à cet endroit</span>
                <span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold font-mono">Même Position</span>
              </div>
              <div class="max-h-60 overflow-y-auto custom-scrollbar space-y-2 divide-y divide-slate-800 pr-1">
                ${{ptsAtLoc.map((p, pIdx) => `
                  <div class="pt-1.5 first:pt-0 space-y-1">
                    <div class="flex items-center justify-between">
                      <span class="font-bold text-emerald-400">#${{pIdx + 1}} • ${{p.source_type}}</span>
                      <span class="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-300">${{p.device_os || 'OS'}}</span>
                    </div>
                    <div class="text-slate-200 font-mono text-[11px]">📅 ${{p.timestamp_local || p.timestamp_utc || 'Date inconnue'}}</div>
                    <div class="text-slate-400 text-[10px]">📁 ${{p.source_file}}</div>
                    <button onclick='showPointDetail(${{JSON.stringify(p)}})' class="w-full py-1 text-center bg-slate-800 hover:bg-emerald-600/30 text-emerald-400 rounded border border-slate-700 font-semibold text-[10px] mt-1 transition">
                      Inspecter cet événement
                    </button>
                  </div>
                `).join('')}}
              </div>
            </div>
          `;
        }} else {{
          const p = firstPt;
          let photoHtml = '';
          if (p.extra_data && p.extra_data.Thumbnail) {{
            photoHtml = `<img src="${{p.extra_data.Thumbnail}}" class="w-full h-24 object-cover rounded mt-2 border border-slate-700">`;
          }}
          popupContent = `
            <div class="text-xs p-1 max-w-xs font-sans">
              <div class="font-bold text-sm text-emerald-400 mb-1 flex items-center justify-between">
                <span>${{p.source_type}}</span>
                <span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">${{p.device_os || 'OS'}}</span>
              </div>
              <div class="text-slate-300 font-mono text-[11px] mb-1">📅 ${{p.timestamp_local || p.timestamp_utc || 'Date inconnue'}}</div>
              <div class="text-slate-400 text-[11px]">📁 <b>Fichier :</b> ${{p.source_file}}</div>
              <div class="text-slate-400 text-[11px]">📍 <b>Précision :</b> ${{p.accuracy ? p.accuracy + ' m' : 'Non précisée'}}</div>
              ${{photoHtml}}
              <button onclick='showPointDetail(${{JSON.stringify(p)}})' class="w-full mt-2 py-1 text-center bg-emerald-600/30 text-emerald-400 border border-emerald-500/40 rounded hover:bg-emerald-600/50 font-medium">Inspecter détails</button>
            </div>
          `;
        }}

        marker.bindPopup(popupContent);
        markersLayer.addLayer(marker);

        // Accuracy Circle Buffer if accuracy available
        if (firstPt.accuracy && firstPt.accuracy > 15 && firstPt.accuracy < 2000) {{
          const accCircle = L.circle(latlng, {{
            radius: firstPt.accuracy,
            color: color,
            weight: 1,
            fillColor: color,
            fillOpacity: 0.1,
            interactive: false
          }});
          markersLayer.addLayer(accCircle);
        }}
      }});

      // Fit bounds if points exist
      if (latlngs.length > 0) {{
        map.fitBounds(L.latLngBounds(latlngs), {{ padding: [30, 30] }});
      }}

      // Init Heatmap
      heatLayer = L.heatLayer(heatCoords, {{ radius: 25, blur: 15, maxZoom: 17 }});
      if (isHeatmapActive) heatLayer.addTo(map);

      // Init Polyline Track
      polylineLayer = L.polyline(latlngs, {{ color: '#38bdf8', weight: 2.5, opacity: 0.8, dashArray: '4, 4' }});
      if (isTrackActive) polylineLayer.addTo(map);

      // Init Ant Path Directional Flow
      if (L.polyline.antPath && latlngs.length > 1) {{
        antPathLayer = L.polyline.antPath(latlngs, {{
          paused: false,
          reverse: false,
          delay: 800,
          dashArray: [10, 20],
          weight: 4,
          color: '#10b981',
          pulseColor: '#ffffff',
          opacity: 0.85
        }});
        antPathLayer.addTo(map);
      }}
    }}

    function showPointDetail(p) {{
      const card = document.getElementById('detail-content');
      let extraHtml = '';
      if (p.extra_data) {{
        for (const [k, v] of Object.entries(p.extra_data)) {{
          if (k !== 'Thumbnail') {{
            extraHtml += `<div><span class="text-slate-400">${{k}} :</span> <span class="text-slate-200 font-mono">${{v}}</span></div>`;
          }}
        }}
      }}

      let thumbHtml = '';
      if (p.extra_data && p.extra_data.Thumbnail) {{
        thumbHtml = `<div class="mt-2"><img src="${{p.extra_data.Thumbnail}}" class="rounded border border-slate-700 max-h-40 mx-auto"></div>`;
      }}

      card.innerHTML = `
        <div class="space-y-2 text-xs">
          <div class="flex items-center justify-between pb-1 border-b border-slate-800">
            <span class="font-bold text-emerald-400 text-sm">${{p.source_type}}</span>
            <span class="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-semibold">${{p.device_os}}</span>
          </div>
          <div><span class="text-slate-400">Coordonnées :</span> <span class="text-slate-200 font-mono font-bold">${{p.latitude}}, ${{p.longitude}}</span></div>
          <div><span class="text-slate-400">Date/Heure UTC :</span> <span class="text-slate-200 font-mono">${{p.timestamp_utc || 'N/A'}}</span></div>
          <div><span class="text-slate-400">Date/Heure Locale :</span> <span class="text-slate-200 font-mono">${{p.timestamp_local || 'N/A'}}</span></div>
          <div><span class="text-slate-400">Précision (Rayon) :</span> <span class="text-emerald-400 font-semibold">${{p.accuracy ? p.accuracy + ' mètres' : 'Non renseignée'}}</span></div>
          <div><span class="text-slate-400">Altitude :</span> <span class="text-slate-200 font-mono">${{p.altitude ? p.altitude + ' m' : 'N/A'}}</span></div>
          <div><span class="text-slate-400">Fichier Source :</span> <span class="text-slate-300 font-mono text-[10px] break-all block bg-slate-900 p-1 rounded mt-0.5">${{p.source_file}}</span></div>
          <div><span class="text-slate-400">Table / Champ SQLite :</span> <span class="text-slate-300 font-mono">${{p.table_or_field || 'N/A'}}</span></div>
          ${{extraHtml}}
          ${{thumbHtml}}
        </div>
      `;

      // Open sidebar if collapsed
      const sidebar = document.getElementById('sidebar');
      sidebar.classList.remove('hidden');
    }}

    function toggleHeatmap() {{
      isHeatmapActive = !isHeatmapActive;
      const btn = document.getElementById('btn-heatmap');
      if (isHeatmapActive) {{
        btn.classList.add('bg-orange-500/20', 'border-orange-500/40', 'text-orange-400');
        if (heatLayer) heatLayer.addTo(map);
      }} else {{
        btn.classList.remove('bg-orange-500/20', 'border-orange-500/40', 'text-orange-400');
        if (heatLayer) map.removeLayer(heatLayer);
      }}
    }}

    function togglePolyline() {{
      isTrackActive = !isTrackActive;
      const btn = document.getElementById('btn-track');
      if (isTrackActive) {{
        btn.classList.add('bg-sky-500/20', 'border-sky-500/40', 'text-sky-400');
        if (polylineLayer) polylineLayer.addTo(map);
      }} else {{
        btn.classList.remove('bg-sky-500/20', 'border-sky-500/40', 'text-sky-400');
        if (polylineLayer) map.removeLayer(polylineLayer);
      }}
    }}

    function toggleSidebar() {{
      const sb = document.getElementById('sidebar');
      sb.classList.toggle('hidden');
    }}

    function onTimelineChange(val) {{
      const pct = parseInt(val);
      if (pct >= 100) {{
        document.getElementById('current-timeline-date').textContent = 'Tous les points';
        currentFilteredPoints = [...POINTS_DATA];
      }} else {{
        const count = Math.max(1, Math.floor((pct / 100) * POINTS_DATA.length));
        currentFilteredPoints = POINTS_DATA.slice(0, count);
        const lastPt = currentFilteredPoints[currentFilteredPoints.length - 1];
        document.getElementById('current-timeline-date').textContent = lastPt.timestamp_utc || `Point #${{count}}`;
      }}
      renderPoints();
    }}

    function togglePlayAnimation() {{
      isPlaying = !isPlaying;
      const btnIcon = document.getElementById('play-icon');
      const slider = document.getElementById('timeline-slider');

      if (isPlaying) {{
        btnIcon.classList.remove('fa-play');
        btnIcon.classList.add('fa-pause');
        let currentVal = parseInt(slider.value);
        if (currentVal >= 100) currentVal = 0;

        playInterval = setInterval(() => {{
          currentVal += 2;
          if (currentVal > 100) {{
            currentVal = 100;
            togglePlayAnimation();
          }}
          slider.value = currentVal;
          onTimelineChange(currentVal);
        }}, 200);
      }} else {{
        btnIcon.classList.remove('fa-pause');
        btnIcon.classList.add('fa-play');
        if (playInterval) clearInterval(playInterval);
      }}
    }}
  </script>
</body>
</html>
"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
