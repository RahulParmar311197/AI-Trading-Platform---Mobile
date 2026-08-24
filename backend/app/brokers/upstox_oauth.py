import hashlib, secrets, urllib.parse, urllib.request, json
from datetime import datetime, timezone, timedelta
from typing import Any
AUTH_URL = "https://api.upstox.com/v2/login/authorization/dialog"
TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"
def new_state() -> str: return secrets.token_urlsafe(32)
def state_hash(state: str) -> str: return hashlib.sha256(state.encode()).hexdigest()
def authorization_url(client_id: str, redirect_uri: str, state: str) -> str:
    if not client_id or not redirect_uri: raise RuntimeError("Upstox OAuth is not configured")
    return AUTH_URL + "?" + urllib.parse.urlencode({"response_type":"code","client_id":client_id,"redirect_uri":redirect_uri,"state":state})
def exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict[str, Any]:
    if not all([code, client_id, client_secret, redirect_uri]): raise ValueError("Incomplete Upstox OAuth parameters")
    body = urllib.parse.urlencode({"code":code,"client_id":client_id,"client_secret":client_secret,"redirect_uri":redirect_uri,"grant_type":"authorization_code"}).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, headers={"Accept":"application/json","Content-Type":"application/x-www-form-urlencoded"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as response: return json.loads(response.read().decode())
def expires_at() -> datetime: return datetime.now(timezone.utc) + timedelta(minutes=10)
