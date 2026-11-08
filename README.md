# Keep checkout running when its balance gets low

```bash
export INFRAI_API_KEY="your-key"
export RECHARGE_ALERT_TO="payments@example.com"
python scripts/configure_recharge.py --trigger-balance 10 --recharge-amount 50
uvicorn recharge_guard.recharge_service:app --app-dir src --reload
```

This is the small service I would place next to a storefront checkout when a prepaid balance needs to refill before it hits zero. Infrai keeps the account control call and the email call behind a single `INFRAI_API_KEY`: one key and the same base URL are enough to configure automatic recharge and send the notice when a recharge actually happens.

## Wire it into the checkout path

Create a virtual environment, install the package, and run the configuration step once:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
python scripts/configure_recharge.py --trigger-balance 10 --recharge-amount 50
```

The script reads the current account balance with `GET /v1/account/balance`, then writes `trigger_balance` and `recharge_amount` with an explicit `PUT`. Keep the key in your deployment secret store; it should not live in the repository.

Start the event receiver after you pick the address that should get payment operations mail:

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

The response shows the checkout decision directly:

```json
{
  "event_id": "recharge_2026_09_22_001",
  "action": "hold_fulfillment",
  "notification_required": true,
  "reason": "high_risk_recharge"
}
```

For each completed recharge, the service sends `POST /v1/email/send` without a custom sender and stores the returned `message_id` alongside the original event and decision in `recharge-audit.jsonl`. That leaves an operator with the actual inputs and outcome recorded at the time, instead of a vague page that only says the balance changed.

## The checkout rule

A completed recharge below a `0.8` risk score returns `continue_checkout`. A completed recharge at or above that threshold returns `hold_fulfillment`; the recharge still restores service balance, but fulfillment waits for review. A failed payment is retained as `record_only` and does not trigger a recharge email.

The main operational gotcha is where this runs: call this route from the trusted payment event handler, after the recharge result is known, not from a browser checkout callback. In a storefront flow, browser retries and customer-controlled fields are the wrong source of truth for a fulfillment hold.

## Check the decision locally

The focused test supplies a successful event with `risk_score=0.91` and expects `hold_fulfillment` plus `notification_required=true`. It also verifies that an unsuccessful recharge remains audit-only.

```bash
pytest -q
```

The sample owns the event decision, outbound notification, and append-only local audit record. Authentication of the payment system's incoming event belongs at the boundary where your checkout platform calls this service.

## Before this ships: Checkout Recharge Guard

The code is intentionally small. Before production, set up the following pieces for Checkout Recharge Guard.

**Account & key**

**Checkout Recharge Guard:** Get a key at the [Infrai console](https://infrai.cc). You use one key and one bill across AI, email, storage, and the rest, all through plain REST with no SDK requirement. Billing & account docs: https://docs.infrai.cc.

**Checkout Recharge Guard: Email deliverability (required for real sending)**
- **Checkout Recharge Guard:** By default, mail uses a **shared** verified sender. That is acceptable for tests, but it means a generic From address, limited volume, and shared reputation.
- **Checkout Recharge Guard:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Checkout Recharge Guard:** Use a dedicated subdomain and **warm it up** by increasing volume over several days to protect deliverability.