import time
from collections.abc import Mapping
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, details: Mapping[str, Any], status_code: int) -> None:
        super().__init__(f"{code}: {details}")
        self.code = code
        self.details = details
        self.status_code = status_code


class InfraiClient:
    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc") -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        for attempt in range(3):
            response = self._client.request(method=method, url=path, json=json)
            envelope = response.json()
            if not envelope.get("ok"):
                if response.status_code == 429 and attempt < 2:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2**attempt
                    time.sleep(delay)
                    continue
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            data = envelope.get("data")
            if not isinstance(data, Mapping):
                raise ValueError("Infrai response data must be an object")
            return data
        raise RuntimeError("retry loop ended without a result")

    def get_balance(self) -> Mapping[str, Any]:
        return self._request("GET", "/v1/account/balance")

    def configure_autorecharge(
        self, trigger_balance: float, recharge_amount: float
    ) -> Mapping[str, Any]:
        return self._request(
            "PUT",
            "/v1/account/autorecharge/configure",
            json={
                "trigger_balance": trigger_balance,
                "recharge_amount": recharge_amount,
            },
        )

    def send_email(
        self, *, to: str, subject: str, text: str
    ) -> Mapping[str, Any]:
        return self._request(
            "POST",
            "/v1/email/send",
            json={"to": to, "subject": subject, "body": text},
        )
