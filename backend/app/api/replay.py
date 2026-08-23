from datetime import datetime, timezone
from fastapi import APIRouter
router=APIRouter(tags=["replay"])
sessions={}

@router.post("/replay")
def create_replay(symbol:str="NIFTY",timeframe:str="5m",start:str|None=None,end:str|None=None):
    sid=str(len(sessions)+1); sessions[sid]={"id":sid,"symbol":symbol,"timeframe":timeframe,"start":start,"end":end,"state":"PAUSED","cursor":0,"created_at":datetime.now(timezone.utc).isoformat()}; return sessions[sid]

@router.post("/replay/{session_id}/step")
def step(session_id:str):
    s=sessions.get(session_id)
    if not s: return {"error":"not found"}
    s["cursor"]+=1; return s

@router.post("/replay/{session_id}/play")
def play(session_id:str):
    s=sessions.get(session_id)
    if not s: return {"error":"not found"}
    s["state"]="PLAYING"; return s

@router.post("/replay/{session_id}/pause")
def pause(session_id:str):
    s=sessions.get(session_id)
    if not s: return {"error":"not found"}
    s["state"]="PAUSED"; return s
