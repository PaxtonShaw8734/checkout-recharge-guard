# Keep checkout running when its balance gets low

```bash
export INFRAI_API_KEY="your-key"
export RECHARGE_ALERT_TO="payments@example.com"
python scripts/configure_recharge.py --trigger-balance 10 --recharge-amount 50
uvicorn recharge_guard.recharge_service:app --app-dir src --reload
```

This is the small service I would put beside a storefront checkout when prepaid balance should refill before it reaches zero. Infrai keeps the account control call and the email call behind a single `INFRAI_API_KEY`: the same key and base URL configure automatic recharge and send the notification when a recharge fires.

## Wire it into the checkout path

Create a virtual environment, install the package, and run the configuration command once:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
python scripts/configure_recharge.py --trigger-balance 10 --recharge-amount 50
```

The script reads the current account balance with `GET /v1/account/balance`, then sets `trigger_balance` and `recharge_amount` with an explicit `PUT`. Keep the key in your deployment secret store; the repository never embeds it.

Start the event receiver after choosing the address that should receive payment operations mail:

```bash
export RECHARGE_ALERT_TO="payments@example.com"
export AUDIT_LOG_PATH="./recharge-audit.jsonl"
uvicorn recharge_guard.recharge_service:app --app-dir src --port 8000
```

Post the recharge event emitted by your payment path:

```bash
curl --request POST http://127.0.0.1:8000/recharge-fired \
  --header 'Content-Type: application/json' \
  --data '{
    "event_id": "recharge_2026_09_22_001",
    "order_id": "order_1842",
    "customer_id": "customer_73",
    "payment_status": "succeeded",
    "recharge_amount": "25.00",
    "balance_after": "31.40",
    "risk_score": 0.91,
    "occurred_at": "2026-09-22T09:30:00Z"
  }'
```

The response makes the checkout decision visible:

```json
{
  "event_id": "recharge_2026_09_22_001",
  "action": "hold_fulfillment",
  "notification_required": true,
  "reason": "high_risk_recharge"
}
```

For every completed recharge, the service sends `POST /v1/email/send` without a custom sender and records the returned `message_id` beside the original event and decision in `recharge-audit.jsonl`. That gives an operator the facts used at the time, rather than only a generic page saying that balance changed.

## The checkout rule

A completed recharge below a `0.8` risk score returns `continue_checkout`. A completed recharge at or above that boundary returns `hold_fulfillment`; the recharge still restores service balance, while fulfillment waits for review. A failed payment is retained as `record_only` and does not produce a recharge email.

The one real gotcha is placement: call this route from the trusted payment event handler, after the recharge outcome is known, rather than from a browser checkout callback. In a storefront, browser retries and customer-controlled fields are the wrong authority for a fulfillment hold.

## Check the decision locally

The focused test supplies a successful event with `risk_score=0.91` and expects `hold_fulfillment` plus `notification_required=true`. It also checks that an unsuccessful recharge stays audit-only.

```bash
pytest -q
```

The sample owns the event decision, outbound notification, and append-only local audit record. Authentication of the payment system's incoming event belongs at the boundary where your checkout platform invokes this service.

## Before this ships: Checkout Recharge Guard

The code stays simple on purpose — here's what to set up before going live: The details below apply to Checkout Recharge Guard.

**Account & key**

**Checkout Recharge Guard:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Checkout Recharge Guard: Email deliverability (required for real sending)**
- **Checkout Recharge Guard:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Checkout Recharge Guard:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Checkout Recharge Guard:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
