import time
import random
import json
import urllib.request

URL = "http://localhost:3100/loki/api/v1/push"

services = ["frontend", "checkout", "payment", "orders"]

messages = {
    "INFO": [
        "Request processed successfully",
        "Order created successfully",
        "Transaction completed"
    ],
    "WARN": [
        "Response time exceeded",
        "Connection pool nearly full",
        "Retrying request"
    ],
    "ERROR": [
        "Payment gateway timeout",
        "Database connection failed",
        "Internal server error"
    ]
}

while True:
    service = random.choice(services)

    level = random.choices(
        ["INFO", "WARN", "ERROR"],
        weights=[70, 20, 10]
    )[0]

    message = random.choice(messages[level])

    payload = {
        "streams": [
            {
                "stream": {
                    "job": "shop",
                    "service": service,
                    "level": level,
                    "env": "lab"
                },
                "values": [
                    [str(time.time_ns()), message]
                ]
            }
        ]
    }

    request = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(request) as response:
            print(response.status, service, level, message)
    except Exception as e:
        print("Error:", e)

    time.sleep(1)
