from types import SimpleNamespace
from datetime import datetime, timezone
from app.trailing_stop import TrailingPolicy, update_stop
from app.partial_exit import PartialExitPolicy, partial_exit_quantity
from app.execution_costs import ExecutionCostModel


def test_buy_trailing_only_moves_up():
    assert update_stop('BUY',100,95,106,95,TrailingPolicy()) == 103.5
    assert update_stop('BUY',100,95,104,103,TrailingPolicy()) == 103


def test_sell_trailing_only_moves_down():
    assert update_stop('SELL',100,105,94,105,TrailingPolicy()) == 96.5
    assert update_stop('SELL',100,105,96,96,TrailingPolicy()) == 96


def test_partial_exit_quantity():
    policy=PartialExitPolicy(trigger_r=1.0,close_fraction=0.5)
    assert partial_exit_quantity(100,100,95,105,'BUY',policy)==50
    assert partial_exit_quantity(100,100,95,104,'BUY',policy)==0


def test_execution_costs_direction_and_round_trip():
    costs=ExecutionCostModel(commission_bps=10,slippage_bps=5,fixed_fee=2)
    assert costs.fill_price('BUY',100)==100.05
    assert costs.fill_price('SELL',100)==99.95
    assert costs.commission(100,10)==3.0
    assert costs.round_trip_cost(100,110,10)==5.1


def test_execution_costs_reject_negative_values():
    try:
        ExecutionCostModel(commission_bps=-1)
        assert False
    except ValueError:
        pass


def test_trailing_rejects_invalid_side():
    try:
        update_stop('HOLD',100,95,110,95)
        assert False
    except ValueError:
        pass
