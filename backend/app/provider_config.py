from __future__ import annotations
import os
from dataclasses import dataclass
@dataclass(frozen=True)
class ProviderConfig:
    name:str; api_key:str|None=None; api_secret:str|None=None; base_url:str|None=None; timeout_seconds:float=10.0; rate_limit_per_second:float=5.0; enabled:bool=True
    @classmethod
    def from_env(cls,name:str):
        prefix=f"TRADING_PROVIDER_{name.upper()}_"
        return cls(name=name,api_key=os.getenv(prefix+"API_KEY"),api_secret=os.getenv(prefix+"API_SECRET"),base_url=os.getenv(prefix+"BASE_URL"),timeout_seconds=float(os.getenv(prefix+"TIMEOUT_SECONDS","10")),rate_limit_per_second=float(os.getenv(prefix+"RATE_LIMIT_PER_SECOND","5")),enabled=os.getenv(prefix+"ENABLED","true").lower() in {"1","true","yes"})
