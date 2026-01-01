from datetime import datetime
from pydantic import BaseModel


class GenerationReading(BaseModel):
    time: datetime
    bidding_zone_mrid: str
    psr_type: str
    actual_generation_mw: float
    quality_code: str = "A"


class LoadReading(BaseModel):
    time: datetime
    bidding_zone_mrid: str
    load_consumption_mw: float
    quality_code: str = "A"
