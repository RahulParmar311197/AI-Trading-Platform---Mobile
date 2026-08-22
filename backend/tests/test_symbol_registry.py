from app.symbol_registry import SymbolMetadata,SymbolRegistry
def test_exchange_specific_symbol_validation():
 r=SymbolRegistry([SymbolMetadata('NIFTY','NSE'),SymbolMetadata('SENSEX','BSE')]); assert r.validate('nifty','nse').symbol=='NIFTY'; assert r.validate('sensex','bse').symbol=='SENSEX'
def test_wrong_exchange_rejected():
 r=SymbolRegistry([SymbolMetadata('NIFTY','NSE')])
 try:r.validate('NIFTY','BSE'); assert False
 except ValueError as e:assert 'not registered' in str(e)
