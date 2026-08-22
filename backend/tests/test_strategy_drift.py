from app.strategy_drift import detect_strategy_drift, DriftLimits

BASE={'trade_count':100,'win_rate':0.60,'profit_factor':1.8,'expectancy':100,'max_drawdown':0.05}


def test_normal_performance_has_no_drift():
    current={'trade_count':30,'win_rate':0.58,'profit_factor':1.7,'expectancy':95,'max_drawdown':0.07}
    result=detect_strategy_drift(BASE,current)
    assert not result.drifted
    assert result.severity=='NORMAL'


def test_bad_drawdown_and_expectancy_are_drift():
    current={'trade_count':30,'win_rate':0.40,'profit_factor':1.0,'expectancy':50,'max_drawdown':0.15}
    result=detect_strategy_drift(BASE,current)
    assert result.drifted
    assert result.severity=='CRITICAL'
    assert 'DRAWDOWN_DRIFT' in result.reasons


def test_small_sample_is_flagged():
    result=detect_strategy_drift(BASE,{'trade_count':5,'win_rate':0.60,'profit_factor':1.8,'expectancy':100,'max_drawdown':0.05},DriftLimits(min_trades=20))
    assert result.drifted
    assert 'INSUFFICIENT_LIVE_SAMPLE' in result.reasons
