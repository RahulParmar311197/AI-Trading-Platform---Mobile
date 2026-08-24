import { Linking } from 'react-native';
import { API_BASE_URL } from './marketDataApi';
import { withAuthHeaders } from './authSession';

async function jsonRequest(path, options={}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {...options, headers: withAuthHeaders({'Content-Type':'application/json', ...(options.headers||{})})});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}
export async function startUpstoxOAuth(accountLabel='Upstox') { const body=await jsonRequest(`/broker-accounts/upstox/oauth/start?account_label=${encodeURIComponent(accountLabel)}`); await Linking.openURL(body.authorization_url); return body; }
export async function completeUpstoxOAuth(code,state) { return jsonRequest('/broker-accounts/upstox/oauth/complete',{method:'POST',body:JSON.stringify({code,state})}); }
export async function checkUpstoxHealth(accountId) { return jsonRequest(`/broker-accounts/${accountId}/health`); }
