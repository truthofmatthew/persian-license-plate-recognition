"""Signed webhook delivery. Receivers verify X-PLPR-Signature = "sha256=" + HMAC-SHA256(secret, raw body)."""
import hashlib
import hmac
import json
import logging
import time

import httpx

log = logging.getLogger("plpr.webhooks")


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def deliver(url: str, secret: str, event: str, data: dict, retries: int = 3, backoff: float = 1.0,
            transport: httpx.BaseTransport | None = None) -> bool:
    """POST once, then retry up to `retries` times with exponential backoff. Runs as a background task."""
    body = json.dumps({"event": event, "data": data}, ensure_ascii=False, default=str).encode()
    headers = {"Content-Type": "application/json", "X-PLPR-Event": event, "X-PLPR-Signature": sign(secret, body)}
    with httpx.Client(timeout=10, transport=transport) as client:
        for attempt in range(retries + 1):
            try:
                if client.post(url, content=body, headers=headers).is_success:
                    return True
            except httpx.HTTPError as e:
                log.info("webhook %s attempt %d failed: %s", url, attempt + 1, e)
            if attempt < retries:
                time.sleep(backoff * 2 ** attempt)
    log.warning("webhook %s gave up after %d attempts", url, retries + 1)
    return False
