from fastapi import APIRouter, HTTPException
from app.data_provider import ProviderRegistry, RetryPolicy
router=APIRouter(prefix="/api/providers",tags=["market-data-providers"])
registry=ProviderRegistry(); retry=RetryPolicy()
@router.get("")
def providers(): return {"providers":registry.names()}
@router.get("/{name}/health")
async def provider_health(name:str):
    try: provider=registry.get(name)
    except KeyError as e: raise HTTPException(404,str(e))
    return {"provider":provider.name,"status":"registered"}
