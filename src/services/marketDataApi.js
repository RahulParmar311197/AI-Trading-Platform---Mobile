const DEFAULT_BASE_URL = 'http://10.0.2.2:8000';

async function getJson(path, baseUrl = DEFAULT_BASE_URL) {
  const response = await fetch(`${baseUrl}${path}`, { headers: { Accept: 'application/json' } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Market data request failed (${response.status})`);
  return payload;
}

export const marketDataApi = {
  markets: (baseUrl) => getJson('/markets', baseUrl),
  candles: (symbol = 'NIFTY', limit = 200, baseUrl) => getJson(`/candles?symbol=${encodeURIComponent(symbol)}&limit=${limit}`, baseUrl),
  normalizedCandles: (symbol = 'NIFTY', timeframe = '5m', limit = 200, baseUrl) => getJson(`/api/market-data/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&limit=${limit}`, baseUrl),
  marketAnalysis: (symbol = 'NIFTY', limit = 200, baseUrl) => getJson(`/analysis?symbol=${encodeURIComponent(symbol)}&limit=${limit}`, baseUrl),
};
