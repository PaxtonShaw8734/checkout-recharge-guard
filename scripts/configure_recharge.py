import argparse
import json
import os

from recharge_guard.infrai_client import InfraiClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure checkout balance recharge")
    parser.add_argument("--trigger-balance", type=float, required=True)
    parser.add_argument("--recharge-amount", type=float, required=True)
    args = parser.parse_args()

    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise SystemExit("Set INFRAI_API_KEY before running this command")

    client = InfraiClient(api_key)
    try:
        before = client.get_balance()
        configured = client.configure_autorecharge(
            trigger_balance=args.trigger_balance,
            recharge_amount=args.recharge_amount,
        )
    finally:
        client.close()

    print(json.dumps({"balance": before, "autorecharge": configured}, indent=2))


if __name__ == "__main__":
    main()
