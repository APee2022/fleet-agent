import os
from pathlib import Path
from typing import Optional, Dict, List
import pandas as pd
from datetime import datetime, timedelta
from langchain_core.tools import tool
from .geo_tools import geocode, route_coords, simulate
from ..config import OUTPUT_DIR, DEFAULT_PROFILE, DEFAULT_SPEED_PROFILE, DEFAULT_SAMPLE_EVERY_S
import json

# Ensures the parent directory of p exists (creates it recursively if not).
def _ensure_dir(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)

# Parse a local datetime from string, or return default (today 08:00) if None/empty.
def _parse_dt(s: Optional[str]) -> datetime:
    if not s:
        # default shift start 08:00 today
        now = datetime.now()
        return now.replace(hour=8, minute=0, second=0, microsecond=0)
    # allow both "YYYY-MM-DD HH:MM" and full ISO
    return datetime.fromisoformat(s)

# Assign timestamps so the driver only 'moves' during on-duty time windows.
# This function maps those rows onto the calendar so that only driver_hours per day get timestamps.
# When the day’s budget is exhausted, it jumps to next day 08:00 and continues.
def _schedule_across_days(
    df: pd.DataFrame,
    start_time: datetime,
    driver_hours: float,
    sample_every_s: int
) -> pd.DataFrame:
    """
    Assign timestamps so the driver only 'moves' during on-duty time windows.
    We consume the telemetry rows sequentially, but only 6h/day (driver_hours).
    At the end of each day's budget, we jump to next day 08:00 and continue.
    """
    df = df.copy().reset_index(drop=True)
    sec_per_day = int(driver_hours * 3600)

    # current duty window start/end
    cur = start_time
    duty_end = cur + timedelta(seconds=sec_per_day)

    assigned_ts: List[datetime] = []
    day_index: List[int] = []
    is_on_duty: List[bool] = []

    remaining_today = sec_per_day
    day = 1

    # we ignore df['ts_s'] for timestamping (ts_s is sim-time, not wall-clock)
    for _ in range(len(df)):
        # if out of daily budget, move to next day 08:00
        if remaining_today <= 0:
            # next day, same 08:00 start as start_time provided
            base = (cur + timedelta(days=1)).replace(
                hour=start_time.hour, minute=start_time.minute, second=0, microsecond=0
            )
            cur = base
            duty_end = cur + timedelta(seconds=sec_per_day)
            remaining_today = sec_per_day
            day += 1

        # assign this row to current time
        assigned_ts.append(cur)
        day_index.append(day)
        is_on_duty.append(True)

        # advance clock by sampling step
        cur = cur + timedelta(seconds=sample_every_s)
        remaining_today -= sample_every_s

        # guard against overshoot a little: keep timestamps <= duty_end (cosmetic)
        if cur > duty_end and remaining_today < 0:
            cur = duty_end

    df["timestamp"] = assigned_ts
    df["drive_day"] = day_index
    df["is_on_duty"] = is_on_duty
    return df

def json_dumps(d: Dict) -> str:
    return json.dumps(d, ensure_ascii=False)

# Tool to plan a route and generate a telemetry CSV.
@tool("plan_route_to_csv", return_direct=False)
def plan_route_to_csv(
    start: str,
    end: str,
    profile: str = DEFAULT_PROFILE,
    speed_profile: str = DEFAULT_SPEED_PROFILE,
    driver_hours: float = 6.0,
    sample_every_s: int = DEFAULT_SAMPLE_EVERY_S,
    start_time_local: Optional[str] = None,
    vehicle_id: str = "WB4222",
    trip_id: str = "trip-0002",
    out_name: Optional[str] = None,
    split_across_days: bool = True,
    per_day_files: bool = False
) -> str:
    """
    Build a telemetry CSV for one trip.

    If split_across_days=True, drive `driver_hours` per calendar day,
    then resume next day at the same local start time, repeating until all
    telemetry rows are assigned (i.e., until the route is 'completed').

    If per_day_files=True, also writes separate CSVs per drive_day.
    """

    print(f"Tool called with start={start}, end={end}, profile={profile}, speed_profile={speed_profile}, "
        f"driver_hours={driver_hours}, sample_every_s={sample_every_s}, start_time_local={start_time_local}, "
        f"vehicle_id={vehicle_id}, trip_id={trip_id}, out_name={out_name}")
    try:
        # 1) Geocode and route
        start_lat, start_lon, start_label = geocode(start)
        end_lat, end_lon, end_label = geocode(end)
        route = route_coords((start_lat, start_lon), (end_lat, end_lon), profile=profile)

        # 2) Simulate full route once (this yields the whole geometry’s telemetry)
        sim = simulate(
            route["geometry"],
            sample_every_s=sample_every_s,
            speed_profile=speed_profile,
            seed=42
        )
        df = pd.DataFrame(sim["telemetry"])
        if df.empty:
            return json_dumps({"ok": False, "message": "No telemetry generated (empty geometry?)"})

        # 3) Multi-day scheduling
        start_dt = _parse_dt(start_time_local)
        if split_across_days:
            df = _schedule_across_days(df, start_dt, driver_hours, sample_every_s)
        else:
            # legacy: single-window truncate/pad (kept for compatibility)
            # Assign timestamps as simple start + ts_s, then trim to driver_hours
            df = df.copy()
            df["timestamp"] = [start_dt + timedelta(seconds=int(t)) for t in df["ts_s"]]
            window_end = start_dt + timedelta(hours=driver_hours)
            df = df[df["timestamp"] <= window_end].reset_index(drop=True)
            df["drive_day"] = 1
            # df["is_on_duty"] = True

        # 4) Add required columns and tidy order
        df.insert(0, "vehicleID", vehicle_id)
        df.insert(1, "tripID", trip_id)

        cols = [
            "timestamp", "vehicleID", "tripID", "drive_day",
            "lat", "lon", "speed_kmph", "heading_deg", "event", "fuel_l_cumulative", "ts_s"
        ]
        df = df[[c for c in cols if c in df.columns]]

        # 5) Save combined CSV
        out_dir = Path(OUTPUT_DIR)
        _ensure_dir(out_dir)
        base_name = out_name or f"{trip_id}-{start_label[:12].replace(' ','_')}-{end_label[:12].replace(' ','_')}.csv"
        out_path = out_dir / base_name
        df.to_csv(out_path, index=False)

        # 6) Optionally save per-day files
        per_day_paths: List[str] = []
        if per_day_files:
            for d, g in df.groupby("drive_day", sort=True):
                per_path = out_dir / f"{Path(base_name).stem}-day{d}{Path(base_name).suffix}"
                g.to_csv(per_path, index=False)
                per_day_paths.append(str(per_path))

        meta = {
            "distance_km": route["distance_km"],
            "route_duration_sec": route["duration_sec"],
            "sim_avg_speed_kmph": sim["summary"]["avg_speed_kmph"],
            "fuel_used_l": sim["summary"]["fuel_used_l"],
            "events": sim["summary"]["events"],
            "rows": len(df),
            "days": int(df["drive_day"].max()),
            "per_day_files": per_day_paths
        }
        return json_dumps({"ok": True, "message": "CSV generated", "path": str(out_path), "meta": meta})

    except Exception as e:
        return json_dumps({"ok": False, "message": f"Tool error: {e}"})
