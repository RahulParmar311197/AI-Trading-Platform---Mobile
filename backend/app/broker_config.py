from __future__ import annotations
import os
from dataclasses import dataclass
from enum import Enum

class ExecutionMode(str,Enum):
    PAPER='PAPER'; LIVE='LIVE'

@dataclass(frozen=True)
class BrokerCredentials:
    api_key:str
    api_secret:str
    access_token:str|None=None

@dataclass(frozen=True)
class BrokerConfig:
    name:str
    mode:ExecutionMode
    credentials:BrokerCredentials|None


def load_broker_config(prefix:str='BROKER_')->BrokerConfig:
    mode=ExecutionMode(os.getenv(prefix+'MODE','PAPER').upper())
    name=os.getenv(prefix+'NAME','paper')
    if mode==ExecutionMode.PAPER:
        return BrokerConfig(name,mode,None)
    api_key=os.getenv(prefix+'API_KEY'); api_secret=os.getenv(prefix+'API_SECRET'); token=os.getenv(prefix+'ACCESS_TOKEN')
    if not api_key or not api_secret: raise RuntimeError('LIVE broker credentials are not configured')
    return BrokerConfig(name,mode,BrokerCredentials(api_key,api_secret,token))


def redact(value:str|None)->str:
    if not value: return ''
    return value[:2]+'***'+value[-2:] if len(value)>4 else '***'
