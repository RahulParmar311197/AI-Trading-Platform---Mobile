import { getPortfolioState } from './portfolioStateApi';

export function derivePortfolioRiskState(state) {
  const positions = Array.isArray(state?.positions) ? state.positions : [];
  const holdings = Array.isArray(state?.holdings) ? state.holdings : [];
  const grossExposure = positions.reduce((sum, p) => sum + Math.abs(Number(p.quantity || 0) * Number(p.last_price || 0)), 0);
  const netExposure = Number(state?.net_exposure || 0);
  const unrealizedPnl = Number(state?.unrealized_pnl || 0);
  return { accountId: state?.account_id, broker: state?.broker, positionCount: positions.length, holdingCount: holdings.length, grossExposure, netExposure, unrealizedPnl, exposureUtilization: grossExposure > 0 ? Math.abs(netExposure) / grossExposure : 0, hasOpenPositions: positions.some(p => Number(p.quantity || 0) !== 0), fetchedAt: state?.fetched_at || null };
}

export async function getPortfolioRiskState(accountId) {
  const state = await getPortfolioState(accountId);
  return { state, risk: derivePortfolioRiskState(state) };
}
