"""Loads fake past incidents into Hindsight. Run once: python seed_data.py"""
import os
from dotenv import load_dotenv
from hindsight_client import Hindsight

load_dotenv()
client = Hindsight(base_url=os.getenv("HINDSIGHT_URL", "https://api.hindsight.vectorize.io"),
                   api_key=os.environ["HINDSIGHT_API_KEY"])
BANK = os.getenv("BANK_ID", "incident-bank")
try:
    client.create_bank(bank_id=BANK, name="Incident Response Memory")
except Exception as e:
    print("create_bank skipped:", e)

INCIDENTS = [
 ("2026-03-04", "payments-service", "HTTP 504 timeouts, error 'connection pool exhausted (max=20)'",
  "Connection leak after deploy v2.14 (unclosed DB sessions)", "Rolled back to v2.13, then raised pool to 50", "worked"),
 ("2026-03-19", "payments-service", "Latency spike to 8s, logs show 'too many clients already' from Postgres",
  "Pool size increased but Postgres max_connections was too low", "Simply raising the app pool size", "failed"),
 ("2026-03-19", "payments-service", "Same 'too many clients' error after failed pool bump",
  "Postgres max_connections=100 shared by 6 services", "Added PgBouncer in front of Postgres", "worked"),
 ("2026-04-02", "auth-service", "Users logged out randomly, Redis 'READONLY You can't write against a read only replica'",
  "Redis failover promoted a replica; clients cached the old primary", "Restarted auth pods to refresh Redis connection", "worked"),
 ("2026-04-11", "cart-service", "Cart items disappearing, Redis 'READONLY' errors after maintenance window",
  "Redis failover again; no client reconnect logic", "Restarted pods, then added sentinel-aware client config", "worked"),
 ("2026-04-25", "search-service", "OOMKilled pods every ~40 min, heap growing steadily",
  "Unbounded in-memory cache of query results", "Increased memory limit to 4Gi", "failed"),
 ("2026-04-25", "search-service", "OOMKilled again after memory bump",
  "Unbounded cache with no TTL", "Added LRU cache (max 10k entries) with 10 min TTL", "worked"),
 ("2026-05-08", "notification-service", "Emails delayed 2+ hours, queue depth 400k",
  "Downstream SMTP provider rate limiting (429s)", "Added exponential backoff and batching", "worked"),
 ("2026-05-16", "payments-service", "504 timeouts again on Friday evening right after deploy v2.21",
  "Migration locked the transactions table during peak traffic", "Killed migration, rerun off-peak with online index build", "worked"),
 ("2026-05-30", "api-gateway", "Spike of 502s, upstream 'no healthy hosts', certificate expired warning",
  "Internal TLS cert expired on inventory-service", "Rotated cert, added expiry alert 14 days ahead", "worked"),
 ("2026-06-12", "inventory-service", "CrashLoopBackOff, log: 'x509: certificate has expired'",
  "Cert auto-renew job silently failing", "Fixed cron permissions, verified renewal end to end", "worked"),
 ("2026-06-27", "checkout-service", "Checkout errors 500 right after Friday 5pm deploy",
  "Deploy on Friday without canary; bad config flag", "Reverted flag; team rule: no Friday deploys after 3pm", "worked"),
]
for d, svc, sym, cause, fix, outcome in INCIDENTS:
    text = (f"Incident on {d} in {svc}. Symptoms: {sym}. Root cause: {cause}. "
            f"Fix attempted: {fix}. Outcome: {outcome.upper()}.")
    client.retain(bank_id=BANK, content=text, context="past incident", timestamp=f"{d}T10:00:00Z")
    print("retained:", svc, d)
print("Done. Seeded", len(INCIDENTS), "incidents.")
