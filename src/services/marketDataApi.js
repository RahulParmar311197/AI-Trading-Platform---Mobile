const DEFAULT_BASE_URL = 'http://10.0.2.2:8000';

async function getJson(path, baseUrl = DEFAULT_BASE_URL) {
  const response = await fetch(`${baseUrl}${path}`, { headers: { Accept: 'application/json' } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Market data request failed (${response.status})`);
  return payload;
}

export const marketDataApi = {
  quote: (symbol, baseUrl) => getJson(`/api/market/quote/${encodeURIComponent(symbol)}`, baseUrl),
  candles: (symbol, timeframe = '5m', limit = 200, baseUrl) => getJson(`/api/market/candles/${encodeURIComponent(symbol)}?timeframe=${encodeURIComponent(timeframe)}&limit=${limit}`, baseUrl),
  health: (baseUrl) => getJson('/api/market/health', baseUrl),
};
