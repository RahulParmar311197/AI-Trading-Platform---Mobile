from app.order_lifecycle import OrderLifecycle,OrderStatus

def test_full_order_lifecycle_opens_and_closes_position():
    book=OrderLifecycle(); book.create('o1','NIFTY','BUY',10); book.transition('o1',OrderStatus.SUBMITTED); book.transition('o1',OrderStatus.FILLED,10,100.0)
    assert book.orders['o1'].status==OrderStatus.FILLED; assert book.positions['NIFTY'].quantity==10
    book.create('o2','NIFTY','SELL',10); book.transition('o2',OrderStatus.FILLED,10,110.0)
    assert 'NIFTY' not in book.positions

def test_partial_fill_is_tracked():
    book=OrderLifecycle(); book.create('o1','BANKNIFTY','BUY',10); book.transition('o1',OrderStatus.PARTIALLY_FILLED,4,500.0)
    assert book.orders['o1'].filled_quantity==4; assert book.orders['o1'].status==OrderStatus.PARTIALLY_FILLED

def test_invalid_fill_rejected():
    book=OrderLifecycle(); book.create('o1','NIFTY','BUY',10)
    try: book.transition('o1',OrderStatus.FILLED,11,100.0); assert False
    except ValueError: pass
