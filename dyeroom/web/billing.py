"""Paying for film: a roll of frames bought once, or a monthly or yearly plan, through Paddle.

Paddle is the merchant of record. It runs the checkout on the page (Paddle.js), charges
VAT and sales tax, sends receipts, handles refunds and pays out. This server never sees card
details: it learns what was bought from Paddle's webhooks, checks their signature, and keeps
the account in step. Customers manage plans and receipts in Paddle's customer portal.

Configuration (environment):
  DYEROOM_BILLING                 paddle, or test (purchases succeed at once, for local work)
  DYEROOM_PADDLE_ENV              sandbox (default) or production
  DYEROOM_PADDLE_CLIENT_TOKEN     client-side token, for the checkout on the page
  DYEROOM_PADDLE_API_KEY          API key, for customer portal links
  DYEROOM_PADDLE_WEBHOOK_SECRET   the notification destination's secret key
  DYEROOM_PADDLE_PRICE_ROLL / _MONTHLY / _YEARLY   Paddle price ids (pri_...)
  DYEROOM_PRICE_ROLL / _MONTHLY / _YEARLY          the prices as the page shows them

In Paddle, send transaction.completed, the subscription events (created, updated,
activated, canceled, past_due, paused, resumed) and adjustment.created / adjustment.updated
(refunds and chargebacks) to  <public url>/api/billing/webhook.

A refunded roll takes its unused frames back off the account. A refunded plan payment is
left to the owner (an alert says so): cancel the subscription in Paddle if it should end.
"""
import hashlib
import hmac
import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

from . import alerts
from .accounts import PLAN_CAP

PROVIDER = os.environ.get("DYEROOM_BILLING", "").strip().lower() or None
SANDBOX = os.environ.get("DYEROOM_PADDLE_ENV", "sandbox").strip().lower() != "production"
CLIENT_TOKEN = os.environ.get("DYEROOM_PADDLE_CLIENT_TOKEN", "")
API_KEY = os.environ.get("DYEROOM_PADDLE_API_KEY", "")
WEBHOOK_SECRET = os.environ.get("DYEROOM_PADDLE_WEBHOOK_SECRET", "")
ROLL_FRAMES = 36

PLANS = {
    "roll": {"name": "Roll of 36", "kind": "roll", "price": os.environ.get("DYEROOM_PRICE_ROLL", "€5"),
             "note": "36 photographs. The frames never expire.", "extra": ""},
    "monthly": {"name": "Monthly", "kind": "plan", "price": os.environ.get("DYEROOM_PRICE_MONTHLY", "€5 a month"),
                "note": f"Up to {PLAN_CAP:,} photographs a month. Cancel any time.", "extra": ""},
    "yearly": {"name": "Yearly", "kind": "plan", "price": os.environ.get("DYEROOM_PRICE_YEARLY", "€45 a year"),
               "note": f"Up to {PLAN_CAP:,} photographs a month, for a year.", "extra": "Three months free"},
}
PRICE_IDS = {plan: os.environ.get(f"DYEROOM_PADDLE_PRICE_{plan.upper()}", "") for plan in PLANS}


def config():
    """What the page needs to sell film."""
    if PROVIDER not in ("paddle", "test"):
        return None
    plans = [{"id": key, **plan, "price_id": PRICE_IDS[key]} for key, plan in PLANS.items()
             if PROVIDER == "test" or PRICE_IDS[key]]
    return {"provider": PROVIDER, "environment": "sandbox" if SANDBOX else "production",
            "token": CLIENT_TOKEN if PROVIDER == "paddle" else None, "plans": plans, "plan_cap": PLAN_CAP}


# --- webhooks ------------------------------------------------------------------------------

def verify_signature(raw, header, secret, now=None, tolerance=300):
    """Paddle-Signature: ts=<unix time>;h1=<hex HMAC-SHA256 of "<ts>:<raw body>">.
    More than one h1 appears while a secret is being rotated."""
    if not secret or not header:
        return False
    parts = [p.split("=", 1) for p in header.split(";") if "=" in p]
    stamps = [v for k, v in parts if k == "ts"]
    signatures = [v for k, v in parts if k == "h1"]
    if len(stamps) != 1 or not signatures or not stamps[0].isdigit():
        return False
    if abs((now or time.time()) - int(stamps[0])) > tolerance:
        return False
    expected = hmac.new(secret.encode(), stamps[0].encode() + b":" + raw, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, s) for s in signatures)


def _time(text):
    """Seconds since the epoch from Paddle's RFC 3339 times."""
    if not text:
        return None
    text = re.sub(r"(\.\d{6})\d+", r"\1", text.replace("Z", "+00:00"))
    return datetime.fromisoformat(text).timestamp()


def _price_id(item):
    return item.get("price_id") or (item.get("price") or {}).get("id")


def _user_id(data, store):
    custom = data.get("custom_data") or {}
    user = store.user(custom["user_id"]) if isinstance(custom.get("user_id"), str) else None
    if user is None and data.get("customer_id"):
        user = store.user_by_customer(data["customer_id"])
    return user["id"] if user else None


def handle(event, store, stats=None):
    """Apply one webhook event to the accounts. Safe to receive twice."""
    event_id, kind, data = event.get("event_id"), event.get("event_type", ""), event.get("data") or {}
    if not event_id or store.event_seen(event_id):
        return "already handled"
    user_id = _user_id(data, store)
    result = "ignored"
    if kind == "transaction.completed":
        if user_id and data.get("customer_id"):
            store.set_customer(user_id, data["customer_id"])
        frames = sum(ROLL_FRAMES * int(item.get("quantity") or 1) for item in data.get("items") or []
                     if PRICE_IDS["roll"] and _price_id(item) == PRICE_IDS["roll"])
        if frames and user_id:
            result = f"{frames} frames" if store.grant(user_id, frames, "roll", data["id"]) else "already granted"
            if stats and result != "already granted":
                stats.event("funnel 4: bought a roll")
        elif frames:
            alerts.send("billing", f"Paid roll {data.get('id')} has no account to go to (customer "
                                   f"{data.get('customer_id')}): grant it by hand", stats)
            result = "no account"
    elif kind.startswith("subscription."):
        if user_id:
            if data.get("customer_id"):
                store.set_customer(user_id, data["customer_id"])
            prices = {_price_id(item) for item in data.get("items") or []}
            plan = next((p for p in ("yearly", "monthly") if PRICE_IDS[p] and PRICE_IDS[p] in prices), None)
            period = data.get("current_billing_period") or {}
            change = data.get("scheduled_change") or {}
            ends = _time(change.get("effective_at")) if change.get("action") == "cancel" else None
            if stats and kind == "subscription.created":
                stats.event("funnel 4: started a plan")
            store.put_subscription(data["id"], user_id, data.get("status", "canceled"), plan,
                                   _time(period.get("starts_at")), _time(period.get("ends_at")), ends,
                                   event.get("occurred_at") or data.get("updated_at") or "")
            result = f"plan {data.get('status')}"
        else:
            alerts.send("billing", f"Subscription {data.get('id')} belongs to no account here (customer "
                                   f"{data.get('customer_id')})", stats)
            result = "no account"
    elif kind in ("adjustment.created", "adjustment.updated"):
        if data.get("action") in ("refund", "chargeback") and data.get("status") == "approved":
            if data.get("type") == "partial":
                alerts.send("refund", f"Partial {data['action']} {data.get('id')} on {data.get('transaction_id')}: "
                                      "take back frames by hand if it was a roll", stats)
                result = "partial: by hand"
            else:
                taken = store.take_back_roll(data.get("transaction_id"), data.get("id"))
                if taken is None and data.get("subscription_id"):
                    alerts.send("refund", f"A plan payment was refunded ({data.get('transaction_id')}, "
                                          f"{data.get('subscription_id')}): cancel the plan in Paddle if it should end",
                                stats)
                result = "not a roll" if taken is None else f"{taken} frames taken back"
    store.mark_event(event_id)
    return result


def portal_url(customer_id, subscription_ids=()):
    """A short-lived link to Paddle's customer portal: plans, payment method, receipts."""
    base = "https://sandbox-api.paddle.com" if SANDBOX else "https://api.paddle.com"
    body = json.dumps({"subscription_ids": [s for s in subscription_ids if s.startswith("sub_")][:25]}).encode()
    request = urllib.request.Request(f"{base}/customers/{customer_id}/portal-sessions", data=body, method="POST",
                                     headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)["data"]["urls"]["general"]["overview"]


# --- test mode: purchases succeed at once ------------------------------------------------------

def test_buy(store, user_id, plan):
    if plan == "roll":
        store.grant(user_id, ROLL_FRAMES, "roll", f"test-{uuid.uuid4().hex}")
    elif plan in ("monthly", "yearly"):
        now = time.time()
        days = 365 if plan == "yearly" else 30
        store.put_subscription(f"test-{user_id}", user_id, "active", plan, now, now + days * 86400, None,
                               datetime.now(timezone.utc).isoformat())
    else:
        raise KeyError(plan)


def test_end(store, user_id):
    store.put_subscription(f"test-{user_id}", user_id, "canceled", None, None, None, None,
                           datetime.now(timezone.utc).isoformat())
