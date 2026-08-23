from fastapi import APIRouter, HTTPException
from app.mtf_engine import confirm_dict
router=APIRouter(prefix='/api/mtf',tags=['mtf'])
@router.get('/health')
def health(): return {'status':'ok'}
