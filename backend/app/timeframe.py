from __future__ import annotations
from datetime import timedelta
import re

def timeframe_interval(value:str)->timedelta:
    if not isinstance(value,str): raise ValueError('timeframe must be a string')
    s=value.strip().lower()
    if s in {'1d','d','1day','day'}: return timedelta(days=1)
    if s in {'1w','w','1week','week'}: return timedelta(weeks=1)
    m=re.fullmatch(r'(\d+)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|w|week|weeks)',s)
    if not m: raise ValueError(f'unsupported timeframe: {value}')
    n=int(m.group(1)); unit=m.group(2)
    if unit.startswith('m'): return timedelta(minutes=n)
    if unit.startswith('h'): return timedelta(hours=n)
    if unit.startswith('d'): return timedelta(days=n)
    return timedelta(weeks=n)
