const DEFAULT_BASE_URL = 'http://10.0.2.2:8000';

async function post(path, body, baseUrl = DEFAULT_BASE_URL) {
  const response = await fetch(`${baseUrl}${path}`, { method: 'POST', headers: {'Content-Type':'application/json','Accept':'application/json'}, body: JSON.stringify(body) });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Auth request failed (${response.status})`);
  return payload;
}

export const authApi = {
  register: (username, password, baseUrl) => post('/auth/register', {username, password}, baseUrl),
  login: (username, password, baseUrl) => post('/auth/login', {username, password}, baseUrl),
};
