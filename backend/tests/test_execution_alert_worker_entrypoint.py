import os


def test_worker_entrypoint_uses_environment_configuration():
    assert os.getenv("EXECUTION_ALERT_WORKER_INTERVAL", "2")
    assert os.getenv("EXECUTION_ALERT_WORKER_BATCH", "25")
