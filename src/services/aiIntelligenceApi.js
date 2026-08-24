const DEFAULT_BASE_URL = 'http://10.0.2.2:8000';

async function postJson(path, body, baseUrl = DEFAULT_BASE_URL) {
  const response = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload.detail || `AI API request failed (${response.status})`;
    throw new Error(message);
  }
  return payload;
}

export const aiIntelligenceApi = {
  research: (question, evidence_packet, baseUrl) =>
    postJson('/api/ai/intelligence/research', { question, evidence_packet }, baseUrl),
  tradeExplanation: (record, baseUrl) =>
    postJson('/api/ai/intelligence/trade-explanation', { record }, baseUrl),
  journal: (record, baseUrl) =>
    postJson('/api/ai/intelligence/journal', { record }, baseUrl),
  performance: (trades, baseUrl) =>
    postJson('/api/ai/intelligence/performance', { trades }, baseUrl),
  setups: (trades, baseUrl) =>
    postJson('/api/ai/intelligence/setups', { trades }, baseUrl),
  strategy: (request, use_llm = false, baseUrl) =>
    postJson('/api/ai/strategy', { request, use_llm }, baseUrl),
};
