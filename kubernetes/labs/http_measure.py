#!/usr/bin/env python3
"""Measure the supplied HTTP service. No cluster mutation and no file output."""
import argparse
import concurrent.futures
import http.client
import json
import math
import threading
import time
from urllib.parse import urlsplit

MAX_BODY = 65536

def nearest_rank(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]

def run_round(url, concurrency, seconds, timeout, max_requests):
    target = urlsplit(url)
    if target.scheme != "http" or not target.hostname or target.username or target.password:
        raise ValueError("use an explicit http URL without credentials")
    if target.fragment:
        raise ValueError("URL fragments are not sent to HTTP servers")
    port = target.port or 80
    path = target.path or "/"
    if target.query:
        path += "?" + target.query
    start = threading.Event()
    clock = [0.0]
    per_worker = max_requests // concurrency
    def worker():
        samples = []
        errors = {}
        response_bytes = 0
        attempts = 0
        connection = http.client.HTTPConnection(target.hostname, port, timeout=timeout)
        start.wait()
        try:
            while attempts < per_worker and time.monotonic() < clock[0] + seconds:
                attempts += 1
                began = time.monotonic()
                try:
                    connection.request("GET", path)
                    response = connection.getresponse()
                    body = response.read(MAX_BODY + 1)
                    if len(body) > MAX_BODY:
                        raise ValueError("body exceeds 64 KiB")
                    if response.status != 200:
                        raise ValueError("HTTP " + str(response.status))
                    data = json.loads(body)
                    if not isinstance(data, dict) or data.get("service") != "ledger-api":
                        raise ValueError("unexpected JSON service")
                    samples.append((time.monotonic() - began) * 1000)
                    response_bytes += len(body)
                except (OSError, ValueError, http.client.HTTPException) as error:
                    name = type(error).__name__ + ": " + str(error)
                    errors[name] = errors.get(name, 0) + 1
                    connection.close()
                    connection = http.client.HTTPConnection(target.hostname, port, timeout=timeout)
        finally:
            connection.close()
        return attempts, samples, errors, response_bytes
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = []
        try:
            for _ in range(concurrency):
                futures.append(pool.submit(worker))
        finally:
            clock[0] = time.monotonic()
            start.set()
        results = [future.result() for future in futures]
        elapsed = time.monotonic() - clock[0]
    attempts, samples, errors, response_bytes = 0, [], {}, 0
    for count, timings, failed, size in results:
        attempts += count
        samples.extend(timings)
        response_bytes += size
        for name, count in failed.items():
            errors[name] = errors.get(name, 0) + count
    return {
        "url": url, "concurrency": concurrency,
        "requested_seconds": seconds, "elapsed_seconds": elapsed,
        "attempted": attempts, "successful": len(samples),
        "failed": sum(errors.values()), "errors": errors,
        "successful_requests_per_second": len(samples) / elapsed,
        "successful_body_bytes": response_bytes,
        "successful_latency_ms_nearest_rank": {
            "p50": nearest_rank(samples, 0.50),
            "p95": nearest_rank(samples, 0.95),
            "p99": nearest_rank(samples, 0.99),
        },
        "stopped_at_request_budget": attempts >= per_worker * concurrency,
        "limits": "closed-loop client; success-only quantiles; no CPU, storage, cluster-capacity or error-latency inference",
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--warmup", type=float, default=5)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=2)
    parser.add_argument("--max-requests", type=int, default=20000)
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 64:
        parser.error("concurrency must be between 1 and 64")
    if not all(math.isfinite(x) and 0 < x <= 300 for x in (args.seconds, args.timeout)):
        parser.error("seconds and timeout must be finite, positive and at most 300")
    if not math.isfinite(args.warmup) or not 0 <= args.warmup <= 300:
        parser.error("warmup must be finite and between 0 and 300")
    if not 1 <= args.rounds <= 20 or not args.concurrency <= args.max_requests <= 1000000:
        parser.error("rounds must be 1..20; request budget must be concurrency..1000000")
    try:
        if args.warmup:
            warm = run_round(args.url, args.concurrency, args.warmup, args.timeout, args.max_requests)
            print(json.dumps({"phase": "warmup", "result": warm}, sort_keys=True), flush=True)
            if warm["failed"] or not warm["successful"]:
                return 2
        for number in range(1, args.rounds + 1):
            result = run_round(args.url, args.concurrency, args.seconds, args.timeout, args.max_requests)
            print(json.dumps({"phase": "measurement", "round": number, "result": result}, sort_keys=True), flush=True)
            if result["failed"] or not result["successful"]:
                return 2
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + "\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
