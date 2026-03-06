from datetime import datetime

from pydantic import BaseModel


class APIMessage(BaseModel):
    message: str


class TimeStamped(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
