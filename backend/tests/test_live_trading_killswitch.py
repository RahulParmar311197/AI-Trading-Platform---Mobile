import pytest
from app.live_trading_killswitch import LiveTradingKillSwitch


def test_live_is_blocked_by_default():
    gate=LiveTradingKillSwitch()
    result=gate.check(True,True,True)
    assert not result.allowed
    assert 'LIVE_KILL_SWITCH_OFF' in result.reasons


def test_wrong_confirmation_cannot_arm():
    gate=LiveTradingKillSwitch()
    with pytest.raises(ValueError): gate.arm('YES')


def test_all_gates_are_required():
    gate=LiveTradingKillSwitch(); gate.arm('ENABLE_LIVE_TRADING')
    assert gate.check(True,True,True).allowed
    assert not gate.check(True,True,False).allowed
    assert not gate.check(True,False,True).allowed
    assert not gate.check(False,True,True).allowed


def test_disarm_blocks_again():
    gate=LiveTradingKillSwitch(); gate.arm('ENABLE_LIVE_TRADING'); gate.disarm()
    assert not gate.check(True,True,True).allowed
