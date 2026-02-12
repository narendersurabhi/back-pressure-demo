from pydantic import BaseModel, Field
from typing import Optional

class ProcessRequest(BaseModel):
    payload: str = Field(..., example="do work")

class ProcessResponse(BaseModel):
    id: str
    status: str

class Health(BaseModel):
    status: str = "ok"
    uptime: Optional[float] = None

class ErrorModel(BaseModel):
    detail: str
