from typing import Tuple, List, Dict, Optional
import os, json, urllib.parse, urllib.request, math
import polyline
from geopy.geocoders import Nominatim
from haversine import haversine, Unit

_geocoder = Nominatim(user_agent="route-agent-demo")
OSRM_BASE = os.getenv("OSRM_BASE", "https://router.project-osrm.org")

def geocode(q: str) -> Tuple[float, float, str]:
    if "," in q:
        # allow "lat,lon"
        try:
            lat, lon = [float(x.strip()) for x in q.split(",", 1)]
            return (lat, lon, f"{lat},{lon}")
        except Exception:
            pass
    loc = _geocoder.geocode(q, timeout=10)
    if not loc:
        raise ValueError(f"Could not geocode: {q}")
    return (loc.latitude, loc.longitude, loc.address)

def route_coords(start: Tuple[float, float], end: Tuple[float, float],
                profile: str = "driving-car",
                avoid: Optional[List[str]] = None) -> Dict:
    profile_map = {"driving-car": "driving", "cycling-regular": "cycling", "foot-walking": "foot"}
    osrm_profile = profile_map.get(profile, "driving")
    avoid = avoid or []
    avoid_map = {"ferries": "ferry", "tolls": "toll", "highways": "motorway"}
    excludes = ",".join(sorted({avoid_map[a] for a in avoid if a in avoid_map}))

    coords_part = f"{start[1]},{start[0]};{end[1]},{end[0]}"
    query = {"overview": "full", "geometries": "polyline", "steps": "false", "alternatives": "false"}
    if excludes:
        query["exclude"] = excludes
    url = f"{OSRM_BASE}/route/v1/{osrm_profile}/{coords_part}?{urllib.parse.urlencode(query)}"

    req = urllib.request.Request(url, headers={"User-Agent": "route-agent-demo"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError(f"OSRM error: {data.get('message', data.get('code'))}")

    route = data["routes"][0]
    distance_km = route.get("distance", 0.0) / 1000.0
    duration_sec = int(route.get("duration", 0.0))
    poly = route.get("geometry", "")
    decoded = polyline.decode(poly, precision=5) if poly else []
    geometry = [{"lat": lat, "lon": lon} for lat, lon in decoded]
    return {"distance_km": round(distance_km, 3), "duration_sec": duration_sec, "polyline": poly, "geometry": geometry}

def _bearing(a, b):
    lat1 = math.radians(a["lat"]); lon1 = math.radians(a["lon"])
    lat2 = math.radians(b["lat"]); lon2 = math.radians(b["lon"])
    dlon = lon2 - lon1
    x = math.sin(dlon)*math.cos(lat2)
    y = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dlon)
    deg = (math.degrees(math.atan2(x, y)) + 360) % 360
    return deg

def _interp(a, b, t):
    return {"lat": a["lat"] + (b["lat"] - a["lat"]) * t, "lon": a["lon"] + (b["lon"] - a["lon"]) * t}

def resample_by_distance(geometry: List[Dict], step_m: float = 100.0) -> List[Dict]:
    out = []
    if not geometry:
        return out
    out.append(geometry[0])
    carry = 0.0
    for i in range(len(geometry) - 1):
        A, B = geometry[i], geometry[i+1]
        seg = haversine((A["lat"], A["lon"]), (B["lat"], B["lon"]), unit=Unit.METERS)
        if seg == 0:
            continue
        cursor = carry
        while cursor + step_m <= seg:
            t = (cursor + step_m) / seg
            out.append(_interp(A, B, t))
            cursor += step_m
        carry = seg - cursor
    if out[-1] != geometry[-1]:
        out.append(geometry[-1])
    return out

def simulate(geometry: List[Dict], sample_every_s: int = 10,
            speed_profile: str = "normal", seed: Optional[int] = None) -> Dict:
    import random
    if seed is not None:
        random.seed(seed)
    # caps = {"eco": 55, "normal": 70, "aggressive": 90}
    caps = {"eco": 40, "normal": 60, "aggressive": 85}
    cap = caps.get(speed_profile, 70)
    pts = resample_by_distance(geometry, step_m=100.0)

    out = []
    ts = 0
    fuel_used = 0.0
    events_count = {"HarshAcceleration": 0, "HarshBraking": 0, "Overspeed": 0}

    def sample_event(state, speed):
        probs = {"aggressive": (0.05, 0.04, 0.08), "normal": (0.02, 0.02, 0.03), "eco": (0.01, 0.01, 0.01)}
        p = probs.get(state, probs["normal"])
        r = random.random()
        cum = [p[0], p[0]+p[1], p[0]+p[1]+p[2]]
        if r < cum[0]: return "HarshAcceleration"
        if r < cum[1]: return "HarshBraking"
        if r < cum[2] or speed > cap: return "Overspeed"
        return None

    for i in range(len(pts)):
        heading = _bearing(pts[i-1], pts[i]) if i > 0 else (_bearing(pts[0], pts[1]) if len(pts) > 1 else 0.0)
        noise = random.uniform(-3, 5) if speed_profile != "eco" else random.uniform(-2, 3)
        speed_kmph = max(0.0, min(cap + noise, cap + 10))
        evt = sample_event(speed_profile, speed_kmph)
        a, b, c = 0.6, 0.04, 0.8
        fuel_rate_lph = a + b * speed_kmph + (c if evt == "HarshAcceleration" else 0.0)
        fuel_tick = fuel_rate_lph * (sample_every_s / 3600.0)
        fuel_used += fuel_tick
        if evt: events_count[evt] += 1

        out.append({
            "ts_s": ts, "lat": round(pts[i]["lat"], 6), "lon": round(pts[i]["lon"], 6),
            "speed_kmph": round(speed_kmph, 1), "heading_deg": round(heading, 1),
            "event": evt, "fuel_l_cumulative": round(fuel_used, 3)
        })
        ts += sample_every_s

    summary = {
        "avg_speed_kmph": round(sum(p["speed_kmph"] for p in out) / len(out), 1) if out else 0,
        "fuel_used_l": round(fuel_used, 2),
        "events": events_count
    }
    return {"telemetry": out, "summary": summary}
