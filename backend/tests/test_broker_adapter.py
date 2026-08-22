from app.broker_adapter import BrokerOrder, PaperBrokerAdapter


def test_paper_adapter_submits_and_cancels():
    broker=PaperBrokerAdapter()
    result=broker.submit_order(BrokerOrder('NIFTY','BUY',10))
    assert result['status']=='FILLED'
    oid=result['broker_order_id']
    cancelled=broker.cancel_order(oid)
    assert cancelled['status']=='CANCELLED'


def test_paper_adapter_rejects_invalid_quantity():
    broker=PaperBrokerAdapter()
    try:
        broker.submit_order(BrokerOrder('NIFTY','BUY',0))
        assert False
    except ValueError:
        pass
