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
    """Generate realistic telemetry samples for a route geometry."""
    import random

    if seed is not None:
        random.seed(seed)

    caps = {"eco": 40, "normal": 60, "aggressive": 85}
    cap = caps.get(speed_profile, 60)
    pts = resample_by_distance(geometry, step_m=100.0)

    # Behaviour parameters tuned per driving style.
    event_prob_map = {
        "eco": (0.04, 0.03, 0.02),        # (HarshAcceleration, HarshBraking, Overspeed)
        "normal": (0.06, 0.05, 0.05),
        "aggressive": (0.1, 0.06, 0.08)
    }
    idle_prob_map = {"eco": 0.08, "normal": 0.12, "aggressive": 0.07}
    idle_ranges = {"eco": (1, 3), "normal": (1, 4), "aggressive": (1, 2)}

    out: List[Dict] = []
    ts = 0
    fuel_used = 0.0
    # Track moving average without idle samples for overspeed comparisons.
    moving_speed_total = 0.0
    moving_samples = 0
    events_count: Dict[str, int] = {
        "HarshAcceleration": 0,
        "HarshBraking": 0,
        "Overspeed": 0,
        "Idle": 0
    }

    # We keep a simple stateful speed so that accelerations/braking feel smoother.
    current_speed = random.uniform(cap * 0.5, cap * 0.7)
    last_heading = 0.0

    a, b, c = 0.6, 0.04, 0.8  # base fuel model parameters

    def avg_moving_speed() -> float:
        return moving_speed_total / moving_samples if moving_samples else cap * 0.65

    def append_entry(lat: float, lon: float, heading: float, speed: float, event: Optional[str]):
        nonlocal ts, fuel_used, moving_speed_total, moving_samples

        # Idle fuel burn is lower while the engine runs but vehicle is stopped.
        if speed <= 0.5:
            fuel_rate_lph = 0.8
        else:
            fuel_rate_lph = a + b * speed + (c if event == "HarshAcceleration" else 0.0)

        fuel_tick = fuel_rate_lph * (sample_every_s / 3600.0)
        fuel_used += fuel_tick

        if event:
            events_count[event] = events_count.get(event, 0) + 1

        if speed > 0.5:
            moving_speed_total += speed
            moving_samples += 1

        out.append({
            "ts_s": ts,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "speed_kmph": round(speed, 1),
            "heading_deg": round(heading, 1),
            "event": event,
            "fuel_l_cumulative": round(fuel_used, 3)
        })
        ts += sample_every_s

    def select_event(base_speed: float) -> Optional[str]:
        acc_p, brake_p, over_p = event_prob_map.get(speed_profile, event_prob_map["normal"])

        # Bias probabilities based on current state.
        if current_speed < 8:
            brake_adj = 0.2
            acc_adj = 1.4
        elif current_speed > cap * 0.9:
            brake_adj = 1.2
            acc_adj = 0.6
        else:
            brake_adj = acc_adj = 1.0

        acc_p *= acc_adj
        brake_p *= brake_adj

        # Overspeed more likely if base speed is already above cap.
        if base_speed > cap:
            over_p = max(over_p, 0.12)

        total = acc_p + brake_p + over_p
        r = random.random()
        if r < acc_p:
            return "HarshAcceleration"
        if r < acc_p + brake_p:
            return "HarshBraking"
        if r < total:
            return "Overspeed"
        return None

    def add_idle_block(lat: float, lon: float, heading: float, forced_steps: Optional[int] = None):
        steps_range = idle_ranges.get(speed_profile, (1, 3))
        steps = forced_steps if forced_steps is not None else random.randint(*steps_range)
        for _ in range(steps):
            append_entry(lat, lon, heading, 0.0, "Idle")

    for idx, pt in enumerate(pts):
        if idx == 0:
            heading = _bearing(pts[0], pts[1]) if len(pts) > 1 else 0.0
        else:
            heading = _bearing(pts[idx - 1], pt)
        last_heading = heading

        # Base cruising speed with mild noise.
        cruise_target = random.uniform(cap * 0.6, cap * 0.85)
        base_speed = max(0.0, min(cruise_target + random.uniform(-4, 4), cap + 5))

        event = select_event(base_speed)
        avg_speed_so_far = avg_moving_speed()

        # Enforce event-driven speed behaviours.
        if event == "HarshBraking":
            speed = 0.0
            current_speed = 0.0
        elif event == "HarshAcceleration":
            speed = min(cap + 12, max(base_speed, current_speed + random.uniform(10, 20)))
            current_speed = speed
        elif event == "Overspeed":
            overspeed_target = max(avg_speed_so_far + random.uniform(5, 12), cap + random.uniform(4, 12))
            speed = min(overspeed_target, cap + 25)
            current_speed = speed
        else:
            # Drift gently towards the base speed.
            delta = base_speed - current_speed
            speed = current_speed + delta * random.uniform(0.4, 0.7)
            speed = max(0.0, min(speed, cap + 8))
            current_speed = speed

            # If we still ended up overspeeding, label it.
            if speed > max(avg_speed_so_far + 3, cap + 2):
                event = "Overspeed"
                current_speed = speed

        append_entry(pt["lat"], pt["lon"], heading, speed, event)

        # After harsh braking, keep the vehicle stationary for a bit to mimic a stop.
        if event == "HarshBraking":
            add_idle_block(pt["lat"], pt["lon"], last_heading, forced_steps=random.randint(1, 3))
            current_speed = 0.0
        else:
            idle_probability = idle_prob_map.get(speed_profile, 0.1)
            if random.random() < idle_probability:
                add_idle_block(pt["lat"], pt["lon"], last_heading)
                current_speed = 0.0

    avg_speed = round(sum(p["speed_kmph"] for p in out) / len(out), 1) if out else 0.0
    summary = {
        "avg_speed_kmph": avg_speed,
        "fuel_used_l": round(fuel_used, 2),
        "events": events_count
    }
    return {"telemetry": out, "summary": summary}
