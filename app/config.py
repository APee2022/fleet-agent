import os

OSRM_BASE = os.getenv("OSRM_BASE", "https://router.project-osrm.org")
DEFAULT_PROFILE = "driving-truck"          # maps to OSRM "driving"
DEFAULT_SPEED_PROFILE = "normal"         # eco | normal | aggressive
DEFAULT_SAMPLE_EVERY_S = 60
DEFAULT_DRIVER_HOURS = 6                 # your requirement
DEFAULT_START_LOCAL = "2025-09-20 08:00" # used if user didn't specify
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
