# """Streamlit UI for the Fleet Synthetic Data Agent."""

# from __future__ import annotations

# import json
# import sys
# from pathlib import Path
# from typing import Dict, Any

# import streamlit as st

# # Ensure the repo root is importable when executed via `streamlit run app/ui/streamlit_app.py`
# # PROJECT_ROOT = Path(__file__).resolve().parents[1]
# # if str(PROJECT_ROOT) not in sys.path:
# #     sys.path.insert(0, str(PROJECT_ROOT))

# PROJECT_ROOT = Path(__file__).resolve().parents[2]  # was parents[1]
# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))

# from app.agents.main_agent import run_general_chat_agent
# from app.config import (
#     DEFAULT_PROFILE,
#     DEFAULT_SPEED_PROFILE,
#     DEFAULT_DRIVER_HOURS,
#     DEFAULT_SAMPLE_EVERY_S,
#     DEFAULT_START_LOCAL,
#     OUTPUT_DIR,
# )


# st.set_page_config(
#     page_title="Fleet Synthetic Data Generator",
#     page_icon="🚚",
#     layout="wide",
# )

# st.title("Fleet Synthetic Data Generator")
# st.write(
#     "Craft a natural-language instruction, tweak route parameters, and generate realistic"
#     "fleet telemetry CSVs with a single click."
# )


# def _build_params(form_values: Dict[str, Any]) -> Dict[str, Any]:
#     params: Dict[str, Any] = {
#         "start": form_values["start"],
#         "end": form_values["end"],
#         "speed_profile": form_values["speed_profile"],
#         "driver_hours": float(form_values["driver_hours"]),
#         "sample_every_s": int(form_values["sample_every_s"]),
#         "vehicle_id": form_values["vehicle_id"],
#         "trip_id": form_values["trip_id"],
#         "split_across_days": form_values["split_across_days"],
#         "per_day_files": form_values["per_day_files"],
#     }

#     if form_values["start_time_local"].strip():
#         params["start_time_local"] = form_values["start_time_local"].strip()

#     if form_values["out_name"].strip():
#         params["out_name"] = form_values["out_name"].strip()

#     if form_values["profile"]:
#         params["profile"] = form_values["profile"]

#     return params


# def _display_download(tool_result: Dict[str, Any]) -> None:
#     path = tool_result.get("path")
#     meta = tool_result.get("meta", {}) or {}

#     if path:
#         file_path = Path(path)
#         if file_path.exists():
#             st.success(f"CSV saved to `{file_path}`")
#             with file_path.open("rb") as fh:
#                 st.download_button(
#                     "Download combined CSV",
#                     data=fh.read(),
#                     file_name=file_path.name,
#                     mime="text/csv",
#                 )
#         else:
#             st.warning(f"CSV path `{file_path}` not found on disk.")

#     per_day_files = meta.get("per_day_files") or []
#     if per_day_files:
#         st.markdown("#### Per-day files")
#         for per_path in per_day_files:
#             sub_path = Path(per_path)
#             if sub_path.exists():
#                 with sub_path.open("rb") as fh:
#                     st.download_button(
#                         f"Download {sub_path.name}",
#                         data=fh.read(),
#                         file_name=sub_path.name,
#                         mime="text/csv",
#                         key=f"per-day-{sub_path.name}",
#                     )
#             else:
#                 st.warning(f"Per-day CSV `{sub_path}` is missing.")

#     st.caption(
#         "Outputs are written to the `outputs/` folder (configured via `OUTPUT_DIR`)."
#     )


# def _display_summary(tool_result: Dict[str, Any]) -> None:
#     meta = tool_result.get("meta") or {}
#     if not meta:
#         return

#     cols = st.columns(3)
#     cols[0].metric("Distance (km)", meta.get("distance_km", "-"))
#     cols[1].metric("Days", meta.get("days", "-"))
#     cols[2].metric("Rows", meta.get("rows", "-"))

#     if meta.get("events"):
#         st.subheader("Event Summary")
#         st.json(meta["events"])


# with st.form("telemetry_form"):
#     prompt = st.text_area(
#         "Prompt",
#         placeholder="Describe the telemetry you need...",
#         height=120,
#     )

#     with st.expander("Route parameters", expanded=True):
#         col_a, col_b, col_c = st.columns(3)
#         start = col_a.text_input("Start", value="Kolkata")
#         end = col_b.text_input("End", value="Patna")
#         profile = col_c.selectbox(
#             "OSRM profile",
#             options=["driving-car", "cycling-regular", "foot-walking"],
#             index=["driving-car", "cycling-regular", "foot-walking"].index(DEFAULT_PROFILE if DEFAULT_PROFILE in ["driving-car", "cycling-regular", "foot-walking"] else "driving-car"),
#         )

#         col_d, col_e, col_f = st.columns(3)
#         speed_profile = col_d.selectbox(
#             "Speed profile",
#             options=["eco", "normal", "aggressive"],
#             index=["eco", "normal", "aggressive"].index(DEFAULT_SPEED_PROFILE),
#         )
#         driver_hours = col_e.number_input(
#             "Driver hours per day",
#             min_value=1.0,
#             max_value=12.0,
#             value=float(DEFAULT_DRIVER_HOURS),
#             step=0.5,
#         )
#         sample_every_s = col_f.number_input(
#             "Sample every (s)",
#             min_value=10,
#             max_value=600,
#             value=int(DEFAULT_SAMPLE_EVERY_S),
#             step=10,
#         )

#         col_g, col_h, col_i = st.columns(3)
#         start_time_local = col_g.text_input(
#             "Start time (local)",
#             value=DEFAULT_START_LOCAL,
#             help="Format: YYYY-MM-DD HH:MM",
#         )
#         vehicle_id = col_h.text_input("Vehicle ID", value="WB4222")
#         trip_id = col_i.text_input("Trip ID", value="trip-0002")

#         col_j, col_k = st.columns(2)
#         out_name = col_j.text_input("Output filename", value="")
#         split_across_days = col_j.checkbox("Split across days", value=True)
#         per_day_files = col_k.checkbox("Generate per-day files", value=False)

#     submitted = st.form_submit_button("Generate telemetry", use_container_width=True)

# if submitted:
#     if not prompt.strip():
#         st.error("Please describe what you need in the prompt before generating.")
#         st.stop()

#     form_values = {
#         "start": start.strip() or "Kolkata",
#         "end": end.strip() or "Patna",
#         "profile": profile,
#         "speed_profile": speed_profile,
#         "driver_hours": driver_hours,
#         "sample_every_s": sample_every_s,
#         "start_time_local": start_time_local,
#         "vehicle_id": vehicle_id.strip() or "WB4222",
#         "trip_id": trip_id.strip() or "trip-0002",
#         "out_name": out_name,
#         "split_across_days": split_across_days,
#         "per_day_files": per_day_files,
#     }

#     params = _build_params(form_values)
#     st.session_state["last_params"] = params

#     request_text = prompt.strip()
#     if params:
#         request_text = f"{request_text}\n\nParams: {json.dumps(params)}"

#     with st.spinner("Generating telemetry..."):
#         result = run_general_chat_agent(request_text, session_id="streamlit-ui")

#     response_text = result.get("response") if isinstance(result, dict) else str(result)
#     st.subheader("Agent response")
#     st.write(response_text)

#     tool_result = result.get("tool_result") if isinstance(result, dict) else None
#     if tool_result:
#         st.markdown("---")
#         st.subheader("Generated files")
#         _display_download(tool_result)
#         _display_summary(tool_result)
#     else:
#         st.info("No structured tool output was returned. Check the response above for details.")

# st.sidebar.header("Outputs directory")
# st.sidebar.write(f"Files are stored in `{Path(OUTPUT_DIR).resolve()}`")

# if "last_params" in st.session_state:
#     st.sidebar.subheader("Last used parameters")
#     st.sidebar.json(st.session_state["last_params"])

# *************************************************************************************
# app/ui/streamlit_app.py
"""Streamlit UI for the Fleet Synthetic Data Agent (single CSV download, no sidebar)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import glob

import streamlit as st

# --- Make repo root importable when running: streamlit run app/ui/streamlit_app.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # repo root (.. / .. from /app/ui/)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --- App imports
from app.agents.main_agent import run_general_chat_agent
from app.config import (
    DEFAULT_PROFILE,
    DEFAULT_SPEED_PROFILE,
    DEFAULT_DRIVER_HOURS,
    DEFAULT_SAMPLE_EVERY_S,
    DEFAULT_START_LOCAL,
    OUTPUT_DIR,
)

# -------------------------- Streamlit Page Config ---------------------------
st.set_page_config(
    page_title="Fleet Synthetic Data Generator",
    page_icon="🚚",
    layout="wide",
)

st.title("Fleet Synthetic Data Generator")
st.write(
    "Craft a natural-language instruction, tweak route parameters, and generate realistic "
    "fleet telemetry CSVs with a single click."
)

# ----------------------------- Helpers -------------------------------------
def _build_params(form_values: Dict[str, Any]) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "start": form_values["start"],
        "end": form_values["end"],
        "speed_profile": form_values["speed_profile"],
        "driver_hours": float(form_values["driver_hours"]),
        "sample_every_s": int(form_values["sample_every_s"]),
        "vehicle_id": form_values["vehicle_id"],
        "trip_id": form_values["trip_id"],
        "split_across_days": form_values["split_across_days"],
        "per_day_files": form_values["per_day_files"],
    }
    if form_values["start_time_local"].strip():
        params["start_time_local"] = form_values["start_time_local"].strip()
    if form_values["out_name"].strip():
        params["out_name"] = form_values["out_name"].strip()
    if form_values["profile"]:
        params["profile"] = form_values["profile"]
    return params


def _display_summary(tool_result: Dict[str, Any]) -> None:
    meta = tool_result.get("meta") or {}
    if not meta:
        return
    cols = st.columns(3)
    cols[0].metric("Distance (km)", meta.get("distance_km", "-"))
    cols[1].metric("Days", meta.get("days", "-"))
    cols[2].metric("Rows", meta.get("rows", "-"))
    if meta.get("events"):
        st.subheader("Event Summary")
        st.json(meta["events"])

# ----------------------------- Form UI -------------------------------------
with st.form("telemetry_form"):
    prompt = st.text_area(
        "Prompt",
        placeholder="Describe the telemetry you need (e.g., 'Kolkata → Patna, 6-hour duty, realistic idle times')...",
        height=120,
    )

    with st.expander("Route parameters", expanded=True):
        col_a, col_b, col_c = st.columns(3)
        start = col_a.text_input("Start", value="Kolkata")
        end = col_b.text_input("End", value="Patna")
        profile = col_c.selectbox(
            "OSRM profile",
            options=["driving-truck", "driving-car", "moter-bike"],
            index=["driving-truck", "driving-car", "moter-bike"].index(
                DEFAULT_PROFILE if DEFAULT_PROFILE in ["driving-truck", "driving-car", "moter-bike"] else "driving-truck"
            ),
        )

        col_d, col_e, col_f = st.columns(3)
        speed_profile = col_d.selectbox(
            "Speed profile",
            options=["eco", "normal", "aggressive"],
            index=["eco", "normal", "aggressive"].index(DEFAULT_SPEED_PROFILE),
        )
        driver_hours = col_e.number_input(
            "Driver hours per day", min_value=1.0, max_value=12.0,
            value=float(DEFAULT_DRIVER_HOURS), step=0.5,
        )
        sample_every_s = col_f.number_input(
            "Sample every (s)", min_value=10, max_value=600,
            value=int(DEFAULT_SAMPLE_EVERY_S), step=10,
        )

        col_g, col_h, col_i = st.columns(3)
        start_time_local = col_g.text_input(
            "Start time (local)",
            value=DEFAULT_START_LOCAL,
            help="Format: YYYY-MM-DD HH:MM",
        )
        vehicle_id = col_h.text_input("Vehicle ID", value="WB1234")
        trip_id = col_i.text_input("Trip ID", value="trip-0010")

        col_j, col_k = st.columns(2)
        out_name = col_j.text_input(
            "Output filename (optional)",
            value="",
            help="If empty, a sensible name is chosen automatically."
        )
        # Keep these two inputs to feed the tool; UI won’t show per-day files anyway.
        split_across_days = col_j.checkbox("Split across days", value=True)
        per_day_files = col_k.checkbox("Generate per-day files (tool may write them)", value=False)

    submitted = st.form_submit_button("Generate telemetry", use_container_width=True)

# -------------------------- Submit Handling ---------------------------------
if submitted:
    if not prompt.strip():
        st.error("Please describe what you need in the prompt before generating.")
        st.stop()

    form_values = {
        "start": start.strip() or "Kolkata",
        "end": end.strip() or "Patna",
        "profile": profile,
        "speed_profile": speed_profile,
        "driver_hours": driver_hours,
        "sample_every_s": sample_every_s,
        "start_time_local": start_time_local,
        "vehicle_id": vehicle_id.strip() or "WB1234",
        "trip_id": trip_id.strip() or "trip-0010",
        "out_name": out_name,
        "split_across_days": split_across_days,
        "per_day_files": per_day_files,
    }
    params = _build_params(form_values)

    # show last used params somewhere lightweight (not sidebar)
    with st.expander("Last used parameters", expanded=False):
        st.json(params)

    request_text = f"{prompt.strip()}\n\nParams: {json.dumps(params)}"

    with st.spinner("Generating telemetry..."):
        result = run_general_chat_agent(request_text, session_id="streamlit-ui")

    # ---------------- Agent Response ----------------
    response_text = result.get("response") if isinstance(result, dict) else str(result)
    st.subheader("Agent response")
    st.write(response_text)

    # ---------------- Unified Download Button ----------------
    tool_result = result.get("tool_result") if isinstance(result, dict) else None
    st.markdown("---")
    st.subheader("Download data")

    csv_file_path = None

    # 1) Prefer the structured tool JSON
    if tool_result and isinstance(tool_result, dict):
        csv_path = tool_result.get("path")
        if csv_path:
            p = Path(csv_path)
            if p.exists():
                csv_file_path = p
            else:
                st.warning(f"CSV path returned by tool not found on disk: {p}")
        # Show summary if we have it
        try:
            _display_summary(tool_result)
        except Exception:
            pass

    # 2) Fallback: newest CSV in OUTPUT_DIR
    if csv_file_path is None:
        try:
            pat = str(Path(OUTPUT_DIR) / "*.csv")
            candidates = glob.glob(pat)
            if candidates:
                newest = max(candidates, key=lambda x: Path(x).stat().st_mtime)
                csv_file_path = Path(newest)
                st.info("Tool JSON not found; offering the most recently created CSV in outputs.")
            else:
                st.info("No CSV found in outputs directory.")
        except Exception as e:
            st.warning(f"Could not scan outputs directory: {e}")

    # 3) If we found a CSV file, show the download button
    if csv_file_path and csv_file_path.exists():
        with csv_file_path.open("rb") as fh:
            st.download_button(
                label="⬇️ Download CSV",
                data=fh.read(),
                file_name=csv_file_path.name,
                mime="text/csv",
            )
    else:
        st.info("No structured tool output was returned and no CSV file was located.")

# Note: no sidebar content — cleaner layout.
# Outputs are still written to OUTPUT_DIR on disk, but we surface a single download button above.
