"""
Tool: send_alert
Author: Anio Joseph
"""

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("apertus-agent.alert")


def send_alert(invoice_id: str, reason: str) -> dict[str, Any]:
    """Send an alert to the accountant."""
    timestamp = datetime.now(timezone.utc).isoformat()
    message = f"[ALERT] Invoice {invoice_id}: {reason}"
    logger.warning(message)

    return {
        "alert_sent": True,
        "invoice_id": invoice_id,
        "reason": reason,
        "timestamp": timestamp,
        "channel": "log (demo)",
    }
