from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict

class PromptRequest(BaseModel):
    prompt: str
    params: Optional[Dict] = None

class PlanRouteCSVParams(BaseModel):
    start: str = Field(..., description="Start place or 'lat,lon'")
    end: str = Field(..., description="End place or 'lat,lon'")
    profile: Literal["driving-car", "cycling-regular", "foot-walking"] = "driving-car"
    speed_profile: Literal["eco", "normal", "aggressive"] = "normal"
    driver_hours: float = 6.0
    sample_every_s: int = 10
    start_time_local: Optional[str] = None
    vehicle_id: str = "WB4555"
    trip_id: str = "trip-0001"
    out_name: Optional[str] = None

class ToolResult(BaseModel):
    ok: bool
    message: str
    path: Optional[str] = None
    meta: Optional[Dict] = None

class AgentResponse(BaseModel):
    response: str
    tool_result: Optional[ToolResult] = None
