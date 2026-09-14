# -*- coding: utf-8 -*-
"""
GeoTrace2Map (GT2M) - Timestamps & Epoch Converter
Handles Apple Cocoa CoreData (2001), WebKit (1601), Unix epochs (s/ms/us/ns), GPS epoch, 
Excel serials, Cellebrite UFED timestamps with (UTC+X), Pandas Timestamps & Strings.
"""
import datetime
from typing import Tuple, Optional, Any
import re

try:
    from dateutil import parser as dateutil_parser
except ImportError:
    dateutil_parser = None

# Constants
COCOA_EPOCH_DIFF = 978307200        # Seconds between 1970-01-01 and 2001-01-01 (Apple Mac/iOS Absolute Time)
WEBKIT_EPOCH_DIFF = 11644473600     # Seconds between 1601-01-01 and 1970-01-01 (WebKit/Chrome timestamp)
GPS_EPOCH_DIFF = 315964800          # Seconds between 1970-01-01 and 1980-01-06 (GPS Epoch)

def parse_forensic_timestamp(raw_val: Any, hint_os: Optional[str] = None) -> Tuple[Optional[str], Optional[str], str]:
    """
    Parses any raw timestamp value and returns:
    (timestamp_utc_iso, timestamp_local_iso, epoch_type)
    """
    if raw_val is None:
        return None, None, "None"
        
    str_val = str(raw_val).strip()
    if str_val in ("", "0", "N/A", "None", "-1", "NaT", "nan", "NaN"):
        return None, None, "None"

    # 1. Handle Pandas / Numpy Timestamps and Python datetime/date
    if hasattr(raw_val, 'to_pydatetime'):
        try:
            py_dt = raw_val.to_pydatetime()
            if hasattr(py_dt, 'tzinfo') and py_dt.tzinfo:
                utc_dt = py_dt.astimezone(datetime.timezone.utc)
            else:
                utc_dt = py_dt.replace(tzinfo=datetime.timezone.utc)
            return _format_dt(utc_dt), _format_dt_local(utc_dt), "DateTime"
        except Exception:
            pass

    if isinstance(raw_val, datetime.datetime):
        utc_dt = raw_val.astimezone(datetime.timezone.utc) if raw_val.tzinfo else raw_val.replace(tzinfo=datetime.timezone.utc)
        return _format_dt(utc_dt), _format_dt_local(utc_dt), "DateTime"

    if isinstance(raw_val, datetime.date):
        utc_dt = datetime.datetime.combine(raw_val, datetime.time.min, tzinfo=datetime.timezone.utc)
        return _format_dt(utc_dt), _format_dt_local(utc_dt), "Date"

    # 2. String formatted date
    if isinstance(raw_val, str):
        # Try numeric parse if the string represents a pure number
        if re.match(r'^-?\d+(\.\d+)?$', str_val):
            try:
                num_val = float(str_val)
                return _parse_numeric_timestamp(num_val, hint_os)
            except Exception:
                pass
        
        # Try string date formats (including Cellebrite UFED)
        parsed_dt = _parse_string_date(str_val)
        if parsed_dt:
            return _format_dt(parsed_dt), _format_dt_local(parsed_dt), "String"

    # 3. Numeric timestamp (int or float)
    if isinstance(raw_val, (int, float)):
        return _parse_numeric_timestamp(float(raw_val), hint_os)

    return None, None, "Unknown"

def _parse_numeric_timestamp(val: float, hint_os: Optional[str] = None) -> Tuple[Optional[str], Optional[str], str]:
    if val <= 0:
        return None, None, "Invalid (<0)"

    # Case A: Apple Cocoa Absolute Time (iOS/macOS)
    if hint_os == "iOS" and val < 1300000000:
        try:
            unix_sec = val + COCOA_EPOCH_DIFF
            dt = datetime.datetime.fromtimestamp(unix_sec, tz=datetime.timezone.utc)
            if 2001 <= dt.year <= 2040:
                return _format_dt(dt), _format_dt_local(dt), "Cocoa (2001)"
        except Exception:
            pass

    # Case B: Unix seconds (yr 2000 to ~ yr 2049)
    if 946684800 <= val <= 2500000000:
        try:
            dt = datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc)
            return _format_dt(dt), _format_dt_local(dt), "Unix Sec"
        except Exception:
            pass

    # Case C: Cocoa Absolute Time without explicit iOS hint (e.g. 2010 to 2030)
    if 100000000 <= val < 946684800:
        try:
            unix_sec = val + COCOA_EPOCH_DIFF
            dt = datetime.datetime.fromtimestamp(unix_sec, tz=datetime.timezone.utc)
            if 2001 <= dt.year <= 2040:
                return _format_dt(dt), _format_dt_local(dt), "Cocoa (2001)"
        except Exception:
            pass

    # Case D: Unix Milliseconds (13 digits)
    if 946684800000 <= val <= 2500000000000:
        try:
            dt = datetime.datetime.fromtimestamp(val / 1000.0, tz=datetime.timezone.utc)
            return _format_dt(dt), _format_dt_local(dt), "Unix MS"
        except Exception:
            pass

    # Case E: Unix Microseconds (16 digits)
    if 946684800000000 <= val <= 2500000000000000:
        try:
            dt = datetime.datetime.fromtimestamp(val / 1000000.0, tz=datetime.timezone.utc)
            return _format_dt(dt), _format_dt_local(dt), "Unix MicroSec"
        except Exception:
            pass

    # Case F: WebKit / Chrome epoch (Microseconds since 1601)
    if 12000000000000000 <= val <= 15000000000000000:
        try:
            unix_sec = (val / 1000000.0) - WEBKIT_EPOCH_DIFF
            dt = datetime.datetime.fromtimestamp(unix_sec, tz=datetime.timezone.utc)
            return _format_dt(dt), _format_dt_local(dt), "WebKit (1601)"
        except Exception:
            pass

    # Case G: Unix Nanoseconds (19 digits)
    if val > 2500000000000000:
        try:
            dt = datetime.datetime.fromtimestamp(val / 1000000000.0, tz=datetime.timezone.utc)
            return _format_dt(dt), _format_dt_local(dt), "Unix NanoSec"
        except Exception:
            pass

    # Case H: Excel Serial float date (e.g. 44000.5 -> year 2020)
    if 30000 <= val <= 60000:
        try:
            base_date = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc)
            dt = base_date + datetime.timedelta(days=val)
            return _format_dt(dt), _format_dt_local(dt), "Excel Serial"
        except Exception:
            pass

    # Fallback to direct Unix timestamp
    try:
        dt = datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc)
        return _format_dt(dt), _format_dt_local(dt), "Unix Float"
    except Exception:
        return None, None, "Unparseable"

def _parse_string_date(s: str) -> Optional[datetime.datetime]:
    s_clean = s.strip()
    
    # Check for Cellebrite Physical Analyzer timezone pattern: e.g. "06.03.2022 17:31:13(UTC+1)" or "(UTC+02:00)"
    ufed_tz_match = re.search(r'\(UTC([+-]?\d+)(?::(\d+))?\)|\[UTC([+-]?\d+)(?::(\d+))?\]', s_clean, re.IGNORECASE)
    tz_offset = None
    if ufed_tz_match:
        h_str = ufed_tz_match.group(1) or ufed_tz_match.group(3)
        m_str = ufed_tz_match.group(2) or ufed_tz_match.group(4)
        h = int(h_str) if h_str else 0
        m = int(m_str) if m_str else 0
        if h < 0:
            m = -m
        tz_offset = datetime.timezone(datetime.timedelta(hours=h, minutes=m))
        s_clean = re.sub(r'\(UTC[+-]?\d*(?::\d+)?\)|\[UTC[+-]?\d*(?::\d+)?\]', '', s_clean, flags=re.IGNORECASE).strip()

    # Common formats
    formats = [
        "%d.%m.%Y %H:%M:%S",     # European dot separator (Cellebrite default: 06.03.2022 17:31:13)
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(s_clean, fmt)
            if tz_offset:
                dt = dt.replace(tzinfo=tz_offset)
            elif not dt.tzinfo:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        except ValueError:
            continue

    # Fallback to dateutil flexible parser
    if dateutil_parser:
        try:
            dt = dateutil_parser.parse(s_clean, fuzzy=False, dayfirst=True)
            if tz_offset:
                dt = dt.replace(tzinfo=tz_offset)
            elif not dt.tzinfo:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        except Exception:
            pass

    # Try ISO format
    try:
        dt = datetime.datetime.fromisoformat(s_clean.replace('Z', '+00:00'))
        if tz_offset:
            dt = dt.replace(tzinfo=tz_offset)
        elif not dt.tzinfo:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        pass
        
    return None

def _format_dt(dt: datetime.datetime) -> str:
    if hasattr(dt, 'to_pydatetime'):
        dt = dt.to_pydatetime()
    utc_dt = dt.astimezone(datetime.timezone.utc) if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def _format_dt_local(dt: datetime.datetime) -> str:
    if hasattr(dt, 'to_pydatetime'):
        dt = dt.to_pydatetime()
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    local_dt = dt.astimezone()
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")
