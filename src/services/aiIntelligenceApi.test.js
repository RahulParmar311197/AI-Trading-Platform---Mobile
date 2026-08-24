import { aiIntelligenceApi } from './aiIntelligenceApi';

test('strategy client sends canonical payload', async () => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ provider: 'local', strategy: { name: 'test' } }),
  });

  const result = await aiIntelligenceApi.strategy('SMC FVG strategy');
  expect(result.strategy.name).toBe('test');
  expect(fetch).toHaveBeenCalledWith(
    'http://10.0.2.2:8000/api/ai/strategy',
    expect.objectContaining({ method: 'POST' }),
  );
});
