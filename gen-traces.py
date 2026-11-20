#!/usr/bin/env python3
"""Generate three example OTLP traces and correlated JSON logs for Lab 4.

traces-otlp.json: OTLP/JSON for an OTLP HTTP receiver at /v1/traces.
app-logs.jsonl: JSON logs including trace_id and span_id.

Trace A: slow but successful order retrieval.
Trace B: failed checkout due to carrier API 503 responses.
Trace C: healthy checkout for comparison.
"""

import json
import random
import time
from datetime import datetime, timezone

random.seed(4)
BASE = time.time() - 180  # Requests start about three minutes ago.
spans = {}
logs = []


def hexid(n):
    return "".join(random.choice("0123456789abcdef") for _ in range(n))


def at(t0, ms):
    return t0 + ms / 1000


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).astimezone().isoformat(
        timespec="milliseconds"
    )


def span(tid, t0, service, name, a, b, parent=None, kind=2, error=None, attrs=None):
    sid = hexid(16)
    s = {
        "traceId": tid,
        "spanId": sid,
        "name": name,
        "kind": kind,
        "startTimeUnixNano": str(int(at(t0, a) * 1e9)),
        "endTimeUnixNano": str(int(at(t0, b) * 1e9)),
        "attributes": [
            {"key": k, "value": {"stringValue": str(v)}}
            for k, v in (attrs or {}).items()
        ],
        "status": {"code": 2, "message": error} if error else {"code": 0},
    }
    if parent:
        s["parentSpanId"] = parent
    spans.setdefault(service, []).append(s)
    return sid


def log(tid, sid, t0, ms, level, service, msg, **kw):
    logs.append(
        {
            "ts": iso(at(t0, ms)),
            "level": level,
            "service": service,
            "trace_id": tid,
            "span_id": sid,
            "message": msg,
            **kw,
        }
    )


# Trace A: slow order retrieval (slow database query inside pricing-service).
A, t = "4bf92f3577b34da6a3ce929d0e0e4736", BASE
fe = span(
    A, t, "frontend", "GET /api/orders/{id}", 0, 2622,
    attrs={"http.route": "/api/orders/{id}", "http.response.status_code": 200},
)
od = span(A, t, "order-service", "GET /orders/{id}", 5, 2611, fe)
span(
    A, t, "postgres", "SELECT orders", 9, 27, od, kind=3,
    attrs={"db.system": "postgresql", "db.statement": "SELECT * FROM orders WHERE id=$1"},
)
cu = span(A, t, "customer-service", "GET /customers/{id}", 30, 76, od)
pr = span(A, t, "pricing-service", "POST /prices/quote", 80, 2049, od)
span(
    A, t, "redis", "GET price-cache", 83, 85, pr, kind=3,
    attrs={"db.system": "redis", "cache.hit": "false"},
)
q = span(
    A, t, "postgres", "SELECT price_rules", 88, 2041, pr, kind=3,
    attrs={
        "db.system": "postgresql",
        "db.statement": "SELECT * FROM price_rules WHERE customer_tier=$1",
        "db.rows": 48211,
    },
)
sh = span(A, t, "shipping-service", "GET /shipping/estimate", 2052, 2603, od)
span(
    A, t, "shipping-service", "GET api.fastship.com/v1/estimate", 2056, 2594, sh,
    kind=3, attrs={"peer.service": "fastship-carrier-api"},
)
log(A, od, t, 6, "INFO", "order-service", "Loading order 7731 for customer C-118")
log(A, cu, t, 74, "INFO", "customer-service", "Customer C-118 tier=GOLD")
log(A, pr, t, 86, "INFO", "pricing-service", "Price cache miss for tier GOLD")
log(
    A, q, t, 2042, "WARN", "pricing-service",
    "Slow query 1953 ms: SELECT * FROM price_rules WHERE customer_tier=? (rows=48211)",
)
log(A, fe, t, 2622, "INFO", "frontend", "GET /api/orders/7731 200 in 2622 ms")

# Trace B: failed checkout (external carrier API returns 503 three times).
B, t = "0af7651916cd43dd8448eb211c80319c", BASE + 42
fe = span(
    B, t, "frontend", "POST /api/checkout", 0, 1241, error="HTTP 502",
    attrs={"http.route": "/api/checkout", "http.response.status_code": 502},
)
ck = span(B, t, "checkout", "POST /checkout", 4, 1236, fe, error="shipping label not created")
iv = span(B, t, "inventory", "POST /inventory/reserve", 9, 47, ck)
span(
    B, t, "postgres", "UPDATE stock", 12, 43, iv, kind=3,
    attrs={"db.system": "postgresql"},
)
sl = span(
    B, t, "shipping-service", "POST /shipping/labels", 51, 1231, ck,
    error="carrier unavailable after 3 attempts",
)
for n, (a, b) in enumerate([(55, 398), (410, 802), (814, 1224)], 1):
    c = span(
        B, t, "shipping-service", "POST api.fastship.com/v1/labels",
        a, b, sl, kind=3, error="HTTP 503 Service Unavailable",
        attrs={"peer.service": "fastship-carrier-api", "retry.attempt": n},
    )
    log(
        B, c, t, b, "WARN", "shipping-service",
        f"Carrier fastship returned 503 (attempt {n}/3)",
    )
log(B, ck, t, 6, "INFO", "checkout", "Checkout started for order 9902 customer C-207")
log(B, iv, t, 46, "INFO", "inventory", "Reserved 2 items for order 9902")
log(
    B, sl, t, 1230, "ERROR", "shipping-service",
    "Label creation failed: carrier fastship unavailable after 3 attempts",
    exception="com.niit.shipping.CarrierUnavailableException",
)
log(
    B, ck, t, 1235, "ERROR", "checkout",
    "Checkout failed for order 9902: shipping label not created", http_status=502,
)
log(B, fe, t, 1241, "WARN", "frontend", "POST /api/checkout 502 in 1241 ms")

# Trace C: healthy checkout for comparison.
C, t = "5b8efff798038103d269b633813fc60c", BASE + 95
fe = span(
    C, t, "frontend", "POST /api/checkout", 0, 318,
    attrs={"http.route": "/api/checkout", "http.response.status_code": 201},
)
ck = span(C, t, "checkout", "POST /checkout", 3, 314, fe)
iv = span(C, t, "inventory", "POST /inventory/reserve", 8, 41, ck)
span(
    C, t, "postgres", "UPDATE stock", 11, 38, iv, kind=3,
    attrs={"db.system": "postgresql"},
)
sl = span(C, t, "shipping-service", "POST /shipping/labels", 45, 182, ck)
span(
    C, t, "shipping-service", "POST api.fastship.com/v1/labels", 48, 179, sl,
    kind=3, attrs={"peer.service": "fastship-carrier-api"},
)
span(C, t, "payment", "POST /payments/charge", 186, 309, ck)
log(C, ck, t, 312, "INFO", "checkout", "Checkout completed for order 9905 in 311 ms")

# Background noise: other requests during the same time window.
for i in range(120):
    tid, t = hexid(32), BASE + i * 1.5
    svc = random.choice(
        ["frontend", "order-service", "pricing-service", "checkout", "inventory"]
    )
    log(
        tid, hexid(16), t, 0, "INFO", svc,
        random.choice(["Request completed", "Cache hit", "Health check OK", "Request received"]),
    )

body = {
    "resourceSpans": [
        {
            "resource": {
                "attributes": [{"key": "service.name", "value": {"stringValue": s}}]
            },
            "scopeSpans": [{"scope": {"name": "lab4"}, "spans": ss}],
        }
        for s, ss in spans.items()
    ]
}

with open("traces-otlp.json", "w", encoding="utf-8") as f:
    json.dump(body, f)

logs.sort(key=lambda r: r["ts"])
with open("app-logs.jsonl", "w", encoding="utf-8") as f:
    for r in logs:
        f.write(json.dumps(r) + "\n")

print(
    f"traces-otlp.json: {sum(len(v) for v in spans.values())} spans in 3 traces | "
    f"app-logs.jsonl: {len(logs)} lines"
)
