# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Forensic Geolocation Analytics & Trip Segmentation
Calculates Trips, Interval Speeds, Stop Points (Dwell Places), and Distance metrics.
"""
import math
import datetime
from typing import List, Dict, Any, Optional
from core.models import ForensicLocationPoint

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes distance between two coordinates in meters using Haversine formula.
    """
    R = 6371000.0 # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def parse_iso_utc(ts_str: Optional[str]) -> Optional[datetime.datetime]:
    if not ts_str:
        return None
    try:
        dt = datetime.datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt.astimezone(datetime.timezone.utc)
    except Exception:
        return None

def analyze_trips_and_metrics(points: List[ForensicLocationPoint]) -> Dict[str, Any]:
    """
    Segments points into trips, detects stop points, calculates speeds and distances.
    """
    if not points:
        return {
            "trips": [],
            "days": {},
            "stop_points": [],
            "total_distance_km": 0.0,
            "max_speed_kmh": 0.0,
            "avg_speed_kmh": 0.0
        }

    # Ensure points are sorted by timestamp
    valid_time_pts = [p for p in points if p.timestamp_utc]
    valid_time_pts.sort(key=lambda p: p.timestamp_utc)

    # 1. Calculate speeds between consecutive points & total distance (Forensic accuracy filtering)
    total_distance_m = 0.0
    speeds_kmh: List[float] = []

    # Maximum accuracy tolerance in meters for calculating speed (e.g. max 25m)
    MAX_ACCURACY_FOR_SPEED = 25.0

    for i in range(len(valid_time_pts) - 1):
        p1 = valid_time_pts[i]
        p2 = valid_time_pts[i + 1]
        
        dt1 = parse_iso_utc(p1.timestamp_utc)
        dt2 = parse_iso_utc(p2.timestamp_utc)
        
        if dt1 and dt2:
            time_diff_sec = (dt2 - dt1).total_seconds()
            dist_m = haversine_distance(p1.latitude, p1.longitude, p2.latitude, p2.longitude)
            
            # Check precision eligibility: both points must be high precision (<= 25m)
            p1_acc_ok = (p1.accuracy is None or p1.accuracy <= MAX_ACCURACY_FOR_SPEED)
            p2_acc_ok = (p2.accuracy is None or p2.accuracy <= MAX_ACCURACY_FOR_SPEED)

            if p1_acc_ok and p2_acc_ok and 0 < time_diff_sec < 86400:
                # Discard minor GPS drift/noise under 5 meters if stationary
                if dist_m > 5.0 and time_diff_sec >= 2.0:
                    speed_kmh = (dist_m / time_diff_sec) * 3.6
                    
                    # Accept realistic speeds for human/vehicle movement (<= 250 km/h)
                    if speed_kmh <= 250.0:
                        p1.speed = round(speed_kmh, 1)
                        speeds_kmh.append(speed_kmh)
                        total_distance_m += dist_m
                    else:
                        p1.speed = None
                else:
                    p1.speed = 0.0
            else:
                # Precision is too low (e.g. cell tower > 25m) -> do not calculate speed
                p1.speed = None

    # 2. Segment into Trips (Break on time gap > 20 mins or day change)
    trips: List[Dict[str, Any]] = []
    current_trip_points: List[ForensicLocationPoint] = []
    
    TRIP_GAP_SECONDS = 20 * 60 # 20 minutes inactivity threshold

    for idx, p in enumerate(valid_time_pts):
        if not current_trip_points:
            current_trip_points.append(p)
            continue
            
        prev_p = current_trip_points[-1]
        dt_prev = parse_iso_utc(prev_p.timestamp_utc)
        dt_curr = parse_iso_utc(p.timestamp_utc)
        
        is_new_trip = False
        if dt_prev and dt_curr:
            delta_sec = (dt_curr - dt_prev).total_seconds()
            if delta_sec > TRIP_GAP_SECONDS or dt_prev.date() != dt_curr.date():
                is_new_trip = True
                
        if is_new_trip:
            # Finalize previous trip
            if len(current_trip_points) >= 2:
                trips.append(_build_trip_summary(len(trips) + 1, current_trip_points))
            current_trip_points = [p]
        else:
            current_trip_points.append(p)

    if len(current_trip_points) >= 2:
        trips.append(_build_trip_summary(len(trips) + 1, current_trip_points))

    # 3. Group by Days
    days_dict: Dict[str, Dict[str, Any]] = {}
    for p in valid_time_pts:
        dt = parse_iso_utc(p.timestamp_utc)
        if dt:
            day_key = dt.strftime("%Y-%m-%d")
            if day_key not in days_dict:
                days_dict[day_key] = {
                    "date": day_key,
                    "point_count": 0,
                    "start_time": p.timestamp_utc,
                    "end_time": p.timestamp_utc,
                    "point_ids": []
                }
            days_dict[day_key]["point_count"] += 1
            days_dict[day_key]["end_time"] = p.timestamp_utc
            days_dict[day_key]["point_ids"].append(p.id)

    # 4. Stop Points / Stationnement Detection (Cluster points within 50m for >= 10 mins)
    stop_points = _detect_stop_points(valid_time_pts)

    max_spd = round(max(speeds_kmh), 1) if speeds_kmh else 0.0
    avg_spd = round(sum(speeds_kmh) / len(speeds_kmh), 1) if speeds_kmh else 0.0

    return {
        "trips": trips,
        "days": days_dict,
        "stop_points": stop_points,
        "total_distance_km": round(total_distance_m / 1000.0, 2),
        "max_speed_kmh": max_spd,
        "avg_speed_kmh": avg_spd
    }

def _build_trip_summary(trip_id: int, trip_pts: List[ForensicLocationPoint]) -> Dict[str, Any]:
    t_start = trip_pts[0].timestamp_utc
    t_end = trip_pts[-1].timestamp_utc
    dt_start = parse_iso_utc(t_start)
    dt_end = parse_iso_utc(t_end)
    
    duration_min = round((dt_end - dt_start).total_seconds() / 60.0, 1) if dt_start and dt_end else 0.0
    
    dist_m = 0.0
    speeds = []
    for i in range(len(trip_pts) - 1):
        d = haversine_distance(trip_pts[i].latitude, trip_pts[i].longitude, trip_pts[i+1].latitude, trip_pts[i+1].longitude)
        dist_m += d
        if trip_pts[i].speed:
            speeds.append(trip_pts[i].speed)

    avg_spd = round(sum(speeds)/len(speeds), 1) if speeds else 0.0
    max_spd = round(max(speeds), 1) if speeds else 0.0

    return {
        "trip_id": trip_id,
        "name": f"Trajet #{trip_id} ({dt_start.strftime('%d/%m/%Y %H:%M') if dt_start else 'N/A'})",
        "date": dt_start.strftime("%Y-%m-%d") if dt_start else "N/A",
        "start_time": t_start,
        "end_time": t_end,
        "start_time_local": trip_pts[0].timestamp_local,
        "end_time_local": trip_pts[-1].timestamp_local,
        "duration_minutes": duration_min,
        "distance_km": round(dist_m / 1000.0, 2),
        "avg_speed_kmh": avg_spd,
        "max_speed_kmh": max_spd,
        "point_count": len(trip_pts),
        "point_ids": [p.id for p in trip_pts]
    }

def _detect_stop_points(pts: List[ForensicLocationPoint]) -> List[Dict[str, Any]]:
    """
    Finds locations where the device stayed within a radius of 60m for at least 10 minutes.
    """
    stop_points = []
    if len(pts) < 2:
        return stop_points

    i = 0
    while i < len(pts):
        cluster = [pts[i]]
        j = i + 1
        
        while j < len(pts):
            dist = haversine_distance(pts[i].latitude, pts[i].longitude, pts[j].latitude, pts[j].longitude)
            if dist <= 65.0: # within 65m radius
                cluster.append(pts[j])
                j += 1
            else:
                break
                
        if len(cluster) >= 2:
            dt_start = parse_iso_utc(cluster[0].timestamp_utc)
            dt_end = parse_iso_utc(cluster[-1].timestamp_utc)
            if dt_start and dt_end:
                duration_sec = (dt_end - dt_start).total_seconds()
                if duration_sec >= 600: # >= 10 minutes
                    avg_lat = sum(p.latitude for p in cluster) / len(cluster)
                    avg_lon = sum(p.longitude for p in cluster) / len(cluster)
                    duration_min = round(duration_sec / 60.0, 1)
                    
                    stop_points.append({
                        "stop_id": len(stop_points) + 1,
                        "latitude": round(avg_lat, 7),
                        "longitude": round(avg_lon, 7),
                        "start_time": cluster[0].timestamp_utc,
                        "end_time": cluster[-1].timestamp_utc,
                        "start_time_local": cluster[0].timestamp_local,
                        "end_time_local": cluster[-1].timestamp_local,
                        "duration_minutes": duration_min,
                        "duration_str": f"{int(duration_min // 60)}h {int(duration_min % 60)}min" if duration_min >= 60 else f"{int(duration_min)} min",
                        "point_count": len(cluster),
                        "point_ids": [p.id for p in cluster]
                    })
                    i = j
                    continue
        i += 1

    return stop_points
