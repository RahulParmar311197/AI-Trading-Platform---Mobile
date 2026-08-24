import { Linking } from 'react-native';
import { API_BASE_URL } from './marketDataApi';
import { withAuthHeaders } from './authSession';

export async function startUpstoxOAuth(accountLabel='Upstox') {
  const response = await fetch(`${API_BASE_URL}/broker-accounts/upstox/oauth/start?account_label=${encodeURIComponent(accountLabel)}`, { headers: withAuthHeaders() });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Unable to start Upstox connection (${response.status})`);
  await Linking.openURL(body.authorization_url);
  return body;
}

export async function checkUpstoxHealth(accountId) {
  const response = await fetch(`${API_BASE_URL}/broker-accounts/${accountId}/health`, { headers: withAuthHeaders() });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Health check failed (${response.status})`);
  return body;
}
