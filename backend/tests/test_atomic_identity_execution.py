from app.transactional_execution_repository import OrderIdentity, TransactionalExecutionRepository


def test_identity_and_fill_commit_together(tmp_path):
    repo=TransactionalExecutionRepository(str(tmp_path/'execution.db'))
    order=repo.create_order('NIFTY','BUY',5,broker_account_id=1,broker_route='upstox')
    identity=OrderIdentity(order,'upstox','broker-1')
    assert repo.bind_identity_and_apply_event(identity,'fill-1','FILLED',broker_account_id=1,broker_route='upstox',price=1000,quantity=5) is True
    assert repo.get_identity_by_broker('upstox','broker-1').client_order_id==order
    assert repo.snapshot().positions[(1,'upstox','NIFTY')]==5.0
    repo.close()


def test_failed_event_rolls_back_identity(tmp_path):
    repo=TransactionalExecutionRepository(str(tmp_path/'execution.db'))
    order=repo.create_order('NIFTY','BUY',5,broker_account_id=1,broker_route='upstox')
    identity=OrderIdentity(order,'upstox','broker-2')
    try:
        repo.bind_identity_and_apply_event(identity,'bad-fill','FILLED',broker_account_id=1,broker_route='upstox',quantity=99)
    except ValueError:
        pass
    else:
        raise AssertionError('oversized fill should fail')
    assert repo.get_identity_by_broker('upstox','broker-2') is None
    assert repo.snapshot().positions == {}
    repo.close()
