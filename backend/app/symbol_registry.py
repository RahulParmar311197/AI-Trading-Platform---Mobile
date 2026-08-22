from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class SymbolMetadata:
    symbol:str; exchange:str; asset_class:str='equity'
class SymbolRegistry:
    def __init__(self, symbols:list[SymbolMetadata]|None=None):
        self._symbols={(x.exchange.upper(),x.symbol.upper()):x for x in (symbols or [])}
    def register(self,metadata:SymbolMetadata): self._symbols[(metadata.exchange.upper(),metadata.symbol.upper())]=metadata
    def validate(self,symbol:str,exchange:str)->SymbolMetadata:
        key=(exchange.strip().upper(),symbol.strip().upper())
        if key not in self._symbols: raise ValueError(f'symbol {key[1]} is not registered on exchange {key[0]}')
        return self._symbols[key]
