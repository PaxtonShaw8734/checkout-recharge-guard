from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class RechargeEvent(BaseModel):
    event_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    payment_status: Literal["succeeded", "failed"]
    recharge_amount: Decimal = Field(gt=0)
    balance_after: Decimal = Field(ge=0)
    risk_score: float = Field(ge=0, le=1)
    occurred_at: datetime


class RechargeDecision(BaseModel):
    event_id: str
    action: Literal["continue_checkout", "hold_fulfillment", "record_only"]
    notification_required: bool
    reason: str


def decide_recharge_action(event: RechargeEvent) -> RechargeDecision:
    if event.payment_status != "succeeded":
        return RechargeDecision(
            event_id=event.event_id,
            action="record_only",
            notification_required=False,
            reason="recharge_not_completed",
        )
    if event.risk_score >= 0.8:
        return RechargeDecision(
            event_id=event.event_id,
            action="hold_fulfillment",
            notification_required=True,
            reason="high_risk_recharge",
        )
    return RechargeDecision(
        event_id=event.event_id,
        action="continue_checkout",
        notification_required=True,
        reason="recharge_completed",
    )
