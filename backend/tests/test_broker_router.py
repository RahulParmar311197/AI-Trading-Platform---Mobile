from app.broker_adapter import PaperBrokerAdapter, BrokerOrderRequest
from app.broker_router import BrokerRoute, BrokerRouter


def test_default_route_submits():
    router=BrokerRouter([BrokerRoute('paper',PaperBrokerAdapter())],'paper')
    result=router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1))
    assert result.status.value=='FILLED'


def test_disabled_route_rejected():
    router=BrokerRouter([BrokerRoute('paper',PaperBrokerAdapter(),False)],'paper')
    try:
        router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1))
        assert False
    except ValueError:
        pass
