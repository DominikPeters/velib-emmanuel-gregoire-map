#!/usr/bin/env python3
"""
Poll the bike tracker API for new rides and update rides.json.
Fetches Google Maps cycling routes for any new station pairs.

Usage:
  GOOGLE_MAPS_API_KEY=... python3 poll.py

Environment variables:
  GOOGLE_MAPS_API_KEY  - required for routing new station pairs
"""

import json, os, sys, urllib.request
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

BIKE_API = "https://tdqr.ovh/api/rides/bike/bike_90157?limit=5"
RIDES_JSON = os.path.join(os.path.dirname(__file__) or ".", "rides.json")
STATIONS_JSON = os.path.join(os.path.dirname(__file__) or ".", "stations.json")

PARIS_TZ = ZoneInfo("Europe/Paris")
DAY_ROLLOVER_HOUR = 3  # days roll over at 3am


def ride_day(iso_time):
    """Return the date key for a ride, rolling over at 3am Paris time."""
    dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00")).astimezone(PARIS_TZ)
    if dt.hour < DAY_ROLLOVER_HOUR:
        dt -= timedelta(days=1)
    return dt.strftime("%Y-%m-%d")


def paris_time_str(iso_time):
    """Return 'HHhMM' in Paris time."""
    dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00")).astimezone(PARIS_TZ)
    return f"{dt.hour:02d}h{dt.minute:02d}"


def load_station_db():
    """Load the Vélib station database."""
    with open(STATIONS_JSON) as f:
        data = json.load(f)
    stations = data["data"]["stations"]
    # Index by stationCode for fast lookup
    by_code = {}
    for s in stations:
        by_code[s["stationCode"]] = s
    return by_code


def resolve_station(station_id, station_db):
    """Resolve 'station_XXXXX' to {name, lat, lon}."""
    code = station_id.replace("station_", "")
    if code in station_db:
        s = station_db[code]
        return {"id": station_id, "name": s["name"], "lat": s["lat"], "lon": s["lon"]}
    print(f"  Warning: station code {code} not found in database")
    return None


def fetch_route(orig, dest, cache, api_key):
    """Fetch cycling route polyline, using cache."""
    cache_key = f"{orig['lat']:.5f},{orig['lon']:.5f}->{dest['lat']:.5f},{dest['lon']:.5f}"
    if cache_key in cache:
        return cache[cache_key]

    if not api_key:
        print(f"  Skipping route {orig['name']} → {dest['name']} (no API key)")
        return None

    print(f"  Fetching route {orig['name']} → {dest['name']} ...")
    url = (
        f"https://maps.googleapis.com/maps/api/directions/json"
        f"?origin={orig['lat']},{orig['lon']}"
        f"&destination={dest['lat']},{dest['lon']}"
        f"&mode=bicycling&key={api_key}"
    )
    with urllib.request.urlopen(url) as r:
        resp = json.loads(r.read())
    if resp["status"] != "OK":
        print(f"  API error: {resp['status']}")
        return None

    poly = resp["routes"][0]["overview_polyline"]["points"]
    cache[cache_key] = poly
    print(f"  → cached")
    return poly


def main():
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")

    # Load rides data
    with open(RIDES_JSON) as f:
        data = json.load(f)

    station_db = load_station_db()
    cache = data.get("route_cache", {})
    days = data.get("days", {})
    rides_raw = data.get("rides_raw", {})

    # Fetch latest rides from API
    print("Fetching latest rides...")
    try:
        req = urllib.request.Request(BIKE_API, headers={
            "User-Agent": "Mozilla/5.0 (compatible; velib-tracker/1.0; +https://github.com/DominikPeters/velib-emmanuel-gregoire-map) Dominik Peters <mail@dominik-peters.de>"
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            api_resp = json.loads(r.read())
    except Exception as e:
        print(f"API request failed: {e}")
        sys.exit(1)

    if not api_resp.get("success"):
        print("API returned error")
        sys.exit(1)

    rides = api_resp["data"]
    known_ids = set()
    for day_rides in rides_raw.values():
        for ride in day_rides:
            known_ids.add(ride["id"])

    new_count = 0
    updated_count = 0
    # Build index of stored rides by id for fast update lookup
    stored_by_id = {}
    for day_rides in rides_raw.values():
        for ride in day_rides:
            stored_by_id[ride["id"]] = ride

    for ride in rides:
        stored = stored_by_id.get(ride["id"])
        if stored is not None:
            # Update ongoing rides that are now completed
            if stored["status"] == "ongoing" and ride["status"] == "completed":
                stored.update({
                    "end_station_id": ride["end_station_id"],
                    "end_time": ride["end_time"],
                    "status": "completed",
                })
                updated_count += 1
                print(f"  Updated ride: → {ride['end_station_id']} ({ride['end_time']})")
            continue

        day_key = ride_day(ride["start_time"])
        if day_key not in rides_raw:
            rides_raw[day_key] = []

        # Store raw ride
        rides_raw[day_key].append({
            "id": ride["id"],
            "start_station_id": ride["start_station_id"],
            "end_station_id": ride["end_station_id"],
            "start_time": ride["start_time"],
            "end_time": ride["end_time"],
            "status": ride["status"],
        })
        new_count += 1
        print(f"  New ride: {ride['start_station_id']} → {ride['end_station_id']} ({ride['start_time']})")

    if new_count == 0 and updated_count == 0:
        print("No new rides found.")
    if updated_count > 0:
        print(f"  {updated_count} ongoing ride(s) updated to completed.")

    # Rebuild station lists per day from raw rides
    for day_key, day_rides in rides_raw.items():
        # Sort rides by start_time
        day_rides.sort(key=lambda r: r["start_time"])

        stations = []
        seen_times = set()
        for ride in day_rides:
            if ride["status"] not in ("completed", "ongoing"):
                continue

            # Add start station
            start = resolve_station(ride["start_station_id"], station_db)
            if start:
                time_str = paris_time_str(ride["start_time"])
                key = (start["id"], time_str)
                if key not in seen_times:
                    seen_times.add(key)
                    start["time"] = time_str
                    stations.append(start)

            # Add end station (if completed)
            if ride["status"] == "completed" and ride["end_station_id"]:
                end = resolve_station(ride["end_station_id"], station_db)
                if end and ride["end_time"]:
                    time_str = paris_time_str(ride["end_time"])
                    key = (end["id"], time_str)
                    if key not in seen_times:
                        seen_times.add(key)
                        end["time"] = time_str
                        stations.append(end)

        # Deduplicate consecutive same-station entries
        deduped = []
        for s in stations:
            if not deduped or deduped[-1]["id"] != s["id"]:
                deduped.append(s)

        # Build segments with actual ride departure/arrival times
        segments = []
        for ride in day_rides:
            if ride["status"] not in ("completed", "ongoing"):
                continue
            start = resolve_station(ride["start_station_id"], station_db)
            end = None
            if ride["status"] == "completed" and ride["end_station_id"]:
                end = resolve_station(ride["end_station_id"], station_db)
            if start and end and ride["end_time"]:
                segments.append({
                    "depart": paris_time_str(ride["start_time"]),
                    "arrive": paris_time_str(ride["end_time"]),
                })

        if day_key in days and "stations" in days[day_key] and any("station_unknown" in s.get("id", "") for s in days[day_key]["stations"]):
            # Don't overwrite manually entered day-24 data
            continue

        days[day_key] = {"stations": deduped, "segments": segments}

    # Fetch routes for all consecutive station pairs
    for day_key, day_data in days.items():
        stations = day_data["stations"]
        for i in range(len(stations) - 1):
            fetch_route(stations[i], stations[i + 1], cache, api_key)

    # Save
    data["days"] = days
    data["rides_raw"] = rides_raw
    data["route_cache"] = cache
    with open(RIDES_JSON, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Done. {new_count} new rides, {updated_count} updated. {len(days)} days tracked.")


if __name__ == "__main__":
    main()
