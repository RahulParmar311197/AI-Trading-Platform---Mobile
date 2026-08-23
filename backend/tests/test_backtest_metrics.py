from app.backtest_metrics import calculate_metrics, compare_backtests


def test_metrics_basic():
    trades=[{'pnl':100},{'pnl':-50},{'pnl':150}]
    m=calculate_metrics(10000,10200,trades,[10000,10100,10050,10200],10,5)
    assert m.net_pnl==200
    assert m.trade_count==3
    assert m.win_rate==2/3
    assert m.profit_factor==5
    assert m.average_win==125
    assert m.average_loss==-50
    assert m.total_commission==10
    assert m.total_slippage==5


def test_compare_backtests_preserves_strategy_names():
    results=[{'strategy':'traditional','starting_equity':10000,'ending_equity':10100,'trade_journal':[{'pnl':100}],'equity_curve':[10000,10100]}, {'strategy':'smc_ict','starting_equity':10000,'ending_equity':10200,'trade_journal':[{'pnl':200}],'equity_curve':[10000,10200]}]
    rows=compare_backtests(results)
    assert [r['strategy'] for r in rows]==['traditional','smc_ict']
    assert rows[1]['net_pnl']>rows[0]['net_pnl']
