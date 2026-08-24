import pytest
from app.order_lifecycle import OrderLifecycle, OrderStatus


def fill(book, order_id, symbol, side, qty, price, fill_id=None):
    if order_id not in book.orders:
        book.create(order_id, symbol, side, qty)
    return book.apply_fill(order_id, qty, price, fill_id)


def test_long_partial_close_realized_pnl():
    book = OrderLifecycle()
    fill(book, "buy", "NIFTY", "BUY", 10, 100, "b1")
    fill(book, "sell", "NIFTY", "SELL", 4, 110, "s1")
    assert book.positions["NIFTY"].quantity == 6
    assert book.positions["NIFTY"].entry_price == pytest.approx(100)
    assert book.realized_pnl_by_symbol["NIFTY"] == pytest.approx(40)


def test_short_partial_close_realized_pnl():
    book = OrderLifecycle()
    fill(book, "sell", "BANKNIFTY", "SELL", 10, 200, "s1")
    fill(book, "buy", "BANKNIFTY", "BUY", 4, 180, "b1")
    assert book.positions["BANKNIFTY"].quantity == 6
    assert book.positions["BANKNIFTY"].side == "SELL"
    assert book.realized_pnl_by_symbol["BANKNIFTY"] == pytest.approx(80)


def test_long_to_short_reversal_realized_pnl():
    book = OrderLifecycle()
    fill(book, "buy", "NIFTY", "BUY", 10, 100, "b1")
    fill(book, "sell", "NIFTY", "SELL", 15, 110, "s1")
    assert book.realized_pnl_by_symbol["NIFTY"] == pytest.approx(100)
    assert book.positions["NIFTY"].side == "SELL"
    assert book.positions["NIFTY"].quantity == 5
    assert book.positions["NIFTY"].entry_price == pytest.approx(110)


def test_short_to_long_reversal_realized_pnl():
    book = OrderLifecycle()
    fill(book, "sell", "NIFTY", "SELL", 10, 200, "s1")
    fill(book, "buy", "NIFTY", "BUY", 15, 180, "b1")
    assert book.realized_pnl_by_symbol["NIFTY"] == pytest.approx(200)
    assert book.positions["NIFTY"].side == "BUY"
    assert book.positions["NIFTY"].quantity == 5
    assert book.positions["NIFTY"].entry_price == pytest.approx(180)


def test_duplicate_close_fill_does_not_change_pnl():
    book = OrderLifecycle()
    fill(book, "buy", "NIFTY", "BUY", 10, 100, "b1")
    fill(book, "sell", "NIFTY", "SELL", 4, 110, "s1")
    fill(book, "sell", "NIFTY", "SELL", 4, 110, "s1")
    assert book.positions["NIFTY"].quantity == 6
    assert book.realized_pnl_by_symbol["NIFTY"] == pytest.approx(40)


def test_same_symbol_position_adds_weighted_entry_price():
    book = OrderLifecycle()
    fill(book, "b1", "NIFTY", "BUY", 10, 100, "f1")
    fill(book, "b2", "NIFTY", "BUY", 10, 110, "f2")
    assert book.positions["NIFTY"].quantity == 20
    assert book.positions["NIFTY"].entry_price == pytest.approx(105)
