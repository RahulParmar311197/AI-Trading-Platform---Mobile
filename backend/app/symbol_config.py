from __future__ import annotations
import json
from pathlib import Path
from app.symbol_registry import SymbolMetadata,SymbolRegistry

def load_symbol_registry(path:str|Path)->SymbolRegistry:
    p=Path(path)
    if not p.exists(): raise FileNotFoundError(f'symbol catalog not found: {p}')
    data=json.loads(p.read_text(encoding='utf-8'))
    if not isinstance(data,list): raise ValueError('symbol catalog must be a JSON array')
    return SymbolRegistry([SymbolMetadata(str(x['symbol']),str(x['exchange']),str(x.get('asset_class','equity'))) for x in data])
