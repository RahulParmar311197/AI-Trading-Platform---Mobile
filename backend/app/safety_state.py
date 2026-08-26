from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import json, os
from pathlib import Path
from app.reconciliation_result import ReconciliationResult

@dataclass
class SafetyState:
    trading_halted: bool = False
    halt_reason: str | None = None
    last_reconciliation_at: datetime | None = None
    halted_at: datetime | None = None
    reconciliation_generation: int | None = None
    reconciliation_account_id: str | None = None
    broker_snapshot_fingerprint: str | None = None

class SafetyStateStore:
    def __init__(self, path: str = "data/safety_state.json") -> None:
        self.path=Path(path); self.backup_path=self.path.with_suffix(self.path.suffix+".bak")
    def save(self,state:SafetyState)->None:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        payload={"trading_halted":state.trading_halted,"halt_reason":state.halt_reason,"last_reconciliation_at":state.last_reconciliation_at.isoformat() if state.last_reconciliation_at else None,"halted_at":state.halted_at.isoformat() if state.halted_at else None,"reconciliation_generation":state.reconciliation_generation,"reconciliation_account_id":state.reconciliation_account_id,"broker_snapshot_fingerprint":state.broker_snapshot_fingerprint}
        tmp=self.path.with_suffix(self.path.suffix+".tmp")
        with tmp.open("wb") as h: h.write(json.dumps(payload,indent=2).encode()); h.flush(); os.fsync(h.fileno())
        if self.path.exists():
            bt=self.backup_path.with_suffix(self.backup_path.suffix+".tmp")
            with bt.open("wb") as h: h.write(self.path.read_bytes()); h.flush(); os.fsync(h.fileno())
            bt.replace(self.backup_path)
        tmp.replace(self.path)
        try:
            fd=os.open(self.path.parent,os.O_RDONLY); os.fsync(fd); os.close(fd)
        except OSError: pass
    @staticmethod
    def _decode(path:Path)->SafetyState:
        d=json.loads(path.read_text(encoding="utf-8")); ra=d.get("last_reconciliation_at"); ha=d.get("halted_at")
        return SafetyState(bool(d.get("trading_halted",False)),d.get("halt_reason"),datetime.fromisoformat(ra) if ra else None,datetime.fromisoformat(ha) if ha else None,d.get("reconciliation_generation"),d.get("reconciliation_account_id"),d.get("broker_snapshot_fingerprint"))
    def load(self)->SafetyState:
        try:
            if not self.path.exists(): return self._decode(self.backup_path) if self.backup_path.exists() else SafetyState()
            return self._decode(self.path)
        except (OSError,ValueError,TypeError,json.JSONDecodeError) as e:
            try: return self._decode(self.backup_path)
            except (OSError,ValueError,TypeError,json.JSONDecodeError) as be: raise RuntimeError("invalid persisted safety state") from be
    def halt(self,reason:str)->SafetyState:
        if not reason.strip(): raise ValueError("halt reason is required")
        state=SafetyState(True,reason,None,datetime.now(timezone.utc),None,None,None); self.save(state); return state
    def clear(self,reconciliation:ReconciliationResult)->SafetyState:
        if not isinstance(reconciliation,ReconciliationResult) or not reconciliation.verified: raise ValueError("verified reconciliation result is required before clearing safety halt")
        state=self.load(); at=reconciliation.reconciled_at.astimezone(timezone.utc)
        if state.trading_halted and state.halted_at is not None and at<=state.halted_at: raise RuntimeError("reconciliation must occur after the safety halt")
        cleared=SafetyState(False,None,at,None,reconciliation.generation,reconciliation.account_id,reconciliation.broker_snapshot_fingerprint); self.save(cleared); return cleared
