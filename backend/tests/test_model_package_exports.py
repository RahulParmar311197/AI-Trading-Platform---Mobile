from app.db import Base
from app.models import Order, User


def test_order_model_is_exported_from_canonical_models_package():
    assert Order.__tablename__ == "orders"
    assert Order.__table__.metadata is Base.metadata
    assert "client_order_id" in Order.__table__.c


def test_user_and_order_models_share_canonical_metadata():
    assert User.__table__.metadata is Base.metadata
    assert Base.metadata.tables["users"] is User.__table__
    assert Base.metadata.tables["orders"] is Order.__table__
