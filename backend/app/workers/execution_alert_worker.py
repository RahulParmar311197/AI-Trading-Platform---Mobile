from __future__ import annotations

import logging
import os
import signal
import time

from app.app_factory import create_resources

logger = logging.getLogger("execution-alert-worker")
_stop = False


def _handle_signal(signum, frame) -> None:
    global _stop
    _stop = True
    logger.info("shutdown requested", extra={"signal": signum})


def main() -> int:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    interval = max(0.1, float(os.getenv("EXECUTION_ALERT_WORKER_INTERVAL", "2")))
    batch_size = max(1, min(100, int(os.getenv("EXECUTION_ALERT_WORKER_BATCH", "25"))))
    resources = create_resources(
        execution_health_token=os.getenv("EXECUTION_HEALTH_TOKEN", "test-token")
    )
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    logger.info("execution alert worker started", extra={"interval": interval, "batch_size": batch_size})
    while not _stop:
        try:
            results = resources.execution_alert_worker.run_once(batch_size)
            delivered = sum(1 for result in results if result.delivered)
            if results:
                logger.info("alert worker tick", extra={"processed": len(results), "delivered": delivered, "failed": len(results) - delivered})
        except Exception:
            logger.exception("alert worker tick failed")
        time.sleep(interval)
    logger.info("execution alert worker stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
