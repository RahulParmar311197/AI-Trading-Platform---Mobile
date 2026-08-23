from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/notifications", tags=["notifications"])

class Notification(BaseModel):
    title: str
    message: str
    severity: str = "info"

@router.post("/preview")
def preview(notification: Notification):
    return {"channel": "mobile", "queued": False, "notification": notification.model_dump()}
