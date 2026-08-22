from __future__ import annotations
import json
from pathlib import Path
from dataclasses import asdict
from app.order_lifecycle import OrderLifecycle, OrderStatus, PositionStatus

class ExecutionStateStore:
    """Small atomic JSON state store; replaceable by PostgreSQL/Redis adapter later."""
    def __init__(self,path:str='data/execution_state.json'):
        self.path=Path(path)

    def save(self,lifecycle:OrderLifecycle)->None:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        payload={'orders':{},'positions':{}}
        for oid,o in lifecycle.orders.items():
            payload['orders'][oid]={**asdict(o),'status':o.status.value,'created_at':o.created_at.isoformat(),'updated_at':o.updated_at.isoformat()}
        for symbol,p in lifecycle.positions.items():
            payload['positions'][symbol]={**asdict(p),'status':p.status.value}
        tmp=self.path.with_suffix(self.path.suffix+'.tmp')
        tmp.write_text(json.dumps(payload,indent=2),encoding='utf-8'); tmp.replace(self.path)

    def load(self,lifecycle:OrderLifecycle)->bool:
        if not self.path.exists(): return False
        data=json.loads(self.path.read_text(encoding='utf-8'))
        from datetime import datetime
        from app.order_lifecycle import OrderRecord, PositionRecord
        lifecycle.orders.clear(); lifecycle.positions.clear()
        for oid,x in data.get('orders',{}).items():
            x=dict(x); x['status']=OrderStatus(x['status']); x['created_at']=datetime.fromisoformat(x['created_at']); x['updated_at']=datetime.fromisoformat(x['updated_at']); lifecycle.orders[oid]=OrderRecord(**x)
        for symbol,x in data.get('positions',{}).items():
            x=dict(x); x['status']=PositionStatus(x['status']); lifecycle.positions[symbol]=PositionRecord(**x)
        return True
