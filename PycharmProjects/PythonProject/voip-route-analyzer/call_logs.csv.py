"""
call_logs_csv.py
----------------
Synthetic VoIP Call Log Generator for NOC scenarios.

This script generates realistic call_logs.csv files with multiple scenarios:
- Good route
- FAS suspicious route
- Bad carrier route (high PDD + failures)

Usage:
    python call_logs_csv.py

Output:
    call_logs.csv
"""

import csv
import random
from datetime import datetime, timedelta

OUTPUT_FILE = "call_logs.csv"

ROUTES = [
    ("UK_1", "United Kingdom", "good"),
    ("DE_1", "Germany", "fas"),
    ("FR_1", "France", "bad"),
]

SIP_CODES = {
    "ANSWERED": "200",
    "FAILED": "503",
    "NO_ANSWER": "408",
    "BUSY": "486",
}


def random_timestamp():
    base = datetime.now()
    delta = timedelta(seconds=random.randint(0, 3600))
    return (base - delta).isoformat()


def generate_good_call(route, destination):
    status = random.choices(["ANSWERED", "NO_ANSWER"], weights=[0.8, 0.2])[0]
    duration = random.randint(30, 180) if status == "ANSWERED" else 0
    pdd = round(random.uniform(2.0, 3.5), 2)

    return {
        "call_id": random.randint(1000, 9999),
        "timestamp": random_timestamp(),
        "route": route,
        "destination": destination,
        "status": status,
        "duration_seconds": duration,
        "pdd_seconds": pdd,
        "rbt_status": "OK",
        "sip_code": SIP_CODES[status],
    }


def generate_fas_call(route, destination):
    status = random.choice(["ANSWERED", "FAILED"])

    if status == "ANSWERED":
        duration = random.randint(1, 3)  # suspicious short calls
    else:
        duration = 0

    pdd = round(random.uniform(1.5, 2.5), 2)

    return {
        "call_id": random.randint(1000, 9999),
        "timestamp": random_timestamp(),
        "route": route,
        "destination": destination,
        "status": status,
        "duration_seconds": duration,
        "pdd_seconds": pdd,
        "rbt_status": "OK",
        "sip_code": SIP_CODES[status],
    }


def generate_bad_call(route, destination):
    status = random.choice(["FAILED", "NO_ANSWER", "ANSWERED"])

    if status == "ANSWERED":
        duration = random.randint(20, 60)
    else:
        duration = 0

    pdd = round(random.uniform(5.5, 8.0), 2)  # high PDD
    rbt = random.choice(["OK", "MISSING"])

    return {
        "call_id": random.randint(1000, 9999),
        "timestamp": random_timestamp(),
        "route": route,
        "destination": destination,
        "status": status,
        "duration_seconds": duration,
        "pdd_seconds": pdd,
        "rbt_status": rbt,
        "sip_code": SIP_CODES[status],
    }


def generate_calls(num_calls_per_route=100):
    all_calls = []

    for route, destination, scenario in ROUTES:
        for _ in range(num_calls_per_route):
            if scenario == "good":
                call = generate_good_call(route, destination)
            elif scenario == "fas":
                call = generate_fas_call(route, destination)
            else:
                call = generate_bad_call(route, destination)

            all_calls.append(call)

    return all_calls


def save_to_csv(calls, filename=OUTPUT_FILE):
    keys = calls[0].keys()

    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=keys)
        writer.writeheader()
        writer.writerows(calls)

    print(f"Generated {len(calls)} calls → {filename}")


if __name__ == "__main__":
    calls = generate_calls(num_calls_per_route=100)
    save_to_csv(calls)
