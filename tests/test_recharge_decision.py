from datetime import UTC, datetime
from decimal import Decimal

from recharge_guard.models import RechargeEvent, decide_recharge_action


def make_event(*, risk_score: float, status: str = "succeeded") -> RechargeEvent:
    return RechargeEvent(
        event_id="recharge_2026_09_22_001",
        order_id="order_1842",
        customer_id="customer_73",
        payment_status=status,
        recharge_amount=Decimal("25.00"),
        balance_after=Decimal("31.40"),
        risk_score=risk_score,
        occurred_at=datetime(2026, 9, 22, 9, 30, tzinfo=UTC),
    )


def test_high_risk_recharge_holds_fulfillment_and_notifies() -> None:
    decision = decide_recharge_action(make_event(risk_score=0.91))

    assert decision.action == "hold_fulfillment"
    assert decision.notification_required is True
    assert decision.reason == "high_risk_recharge"


def test_failed_recharge_is_recorded_without_notification() -> None:
    decision = decide_recharge_action(
        make_event(risk_score=0.12, status="failed")
    )

    assert decision.action == "record_only"
    assert decision.notification_required is False
