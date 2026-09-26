import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from .infrai_client import InfraiClient, InfraiError
from .models import RechargeDecision, RechargeEvent, decide_recharge_action

app = FastAPI(title="Checkout recharge guard")


def _notification_text(event: RechargeEvent, decision: RechargeDecision) -> str:
    return (
        f"Recharge event: {event.event_id}\n"
        f"Order: {event.order_id}\n"
        f"Customer: {event.customer_id}\n"
        f"Amount: {event.recharge_amount}\n"
        f"Balance after: {event.balance_after}\n"
        f"Risk score: {event.risk_score:.2f}\n"
        f"Action: {decision.action}\n"
        f"Occurred at: {event.occurred_at.isoformat()}"
    )


def _append_audit_record(record: dict[str, Any]) -> None:
    audit_path = Path(os.environ.get("AUDIT_LOG_PATH", "recharge-audit.jsonl"))
    with audit_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True, default=str) + "\n")


@app.post("/recharge-fired", response_model=RechargeDecision)
def recharge_fired(event: RechargeEvent) -> RechargeDecision:
    decision = decide_recharge_action(event)
    message_id: str | None = None

    if decision.notification_required:
        api_key = os.environ.get("INFRAI_API_KEY")
        recipient = os.environ.get("RECHARGE_ALERT_TO")
        if not api_key or not recipient:
            raise HTTPException(
                status_code=503,
                detail="INFRAI_API_KEY and RECHARGE_ALERT_TO are required",
            )
        client = InfraiClient(api_key)
        try:
            sent = client.send_email(
                to=recipient,
                subject=f"Recharge recorded for order {event.order_id}",
                text=_notification_text(event, decision),
            )
            message_id = str(sent["message_id"])
        except InfraiError as error:
            client_status = error.status_code if 400 <= error.status_code < 500 else 502
            raise HTTPException(
                status_code=client_status,
                detail={"code": error.code, "details": error.details},
            ) from error
        finally:
            client.close()

    _append_audit_record(
        {
            "event": event.model_dump(mode="json"),
            "decision": decision.model_dump(mode="json"),
            "notification_message_id": message_id,
        }
    )
    return decision
