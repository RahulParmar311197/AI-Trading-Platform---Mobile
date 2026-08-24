import { API_BASE_URL } from './marketDataApi';
import { withAuthHeaders } from './authSession';

export async function getPortfolioState(accountId) {
  const response = await fetch(`${API_BASE_URL}/broker-accounts/${accountId}/portfolio-state`, { headers: withAuthHeaders() });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Portfolio state failed (${response.status})`);
  return body;
}
