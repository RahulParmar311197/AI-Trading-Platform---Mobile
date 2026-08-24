import { API_BASE_URL } from './marketDataApi';
import { withAuthHeaders } from './authSession';
async function get(path) { const r=await fetch(`${API_BASE_URL}${path}`,{headers:withAuthHeaders()}); const body=await r.json().catch(()=>({})); if(!r.ok) throw new Error(body.detail||`Request failed (${r.status})`); return body; }
export const getBrokerProfile=id=>get(`/broker-accounts/${id}/profile`);
export const getBrokerPositions=id=>get(`/broker-accounts/${id}/positions`);
export const getBrokerHoldings=id=>get(`/broker-accounts/${id}/holdings`);
