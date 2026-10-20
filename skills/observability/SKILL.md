---
name: observability
description: >-
  Design and review logging, metrics, alerts and SLOs for services — mainly Spring Boot on OpenShift with logs in Elasticsearch/Kibana and metrics through Micrometer/Prometheus. Use when adding or reviewing structured logging, correlation IDs or MDC; writing a Kibana (KQL) query to find errors; choosing what a service should measure (golden signals, RED); writing or reviewing an alert rule; defining an SLO, error budget or burn-rate alert; or writing a runbook for an alert. Trigger phrases: "structured logging", "JSON logs", "correlation id", "MDC", "Kibana query", "KQL", "what should we monitor", "golden signals", "alert is too noisy", "write an alert", "SLO", "error budget", "burn rate", "runbook".
---

# Observability

Make a service's behaviour visible and its failures actionable: logs to explain one request, metrics to show trends, alerts that page only when users are hurt.

For *where* logs go (Filebeat config, indices, the shared Kibana), see `webmethods-platform` → `references/logging.md`. For live analysis of B2B/IL flows in Elasticsearch, use the `b2b-elastic-logs` skill if it is installed. This skill is about what to log, measure and alert on.

## Pick the starting point

| The user wants to… | Go to |
|---|---|
| add or fix logging in a service | Logging below, then `references/logging.md` |
| find something in Kibana | KQL patterns in `references/logging.md` |
| decide what to measure | Metrics below |
| write, review or de-noise an alert | Alerts below, then `references/alerting-slo.md` |
| define an SLO or error budget | SLOs below, then `references/alerting-slo.md` |
| write a runbook | `assets/runbook-template.md` |

## Logging

Rules that matter most:

1. **JSON, one event per line.** Spring Boot 3.4+ does it with no extra library: `logging.structured.format.console=ecs` (Elastic Common Schema, which Kibana understands natively).
2. **Every line carries a correlation ID.** Read it from the incoming header (`X-Correlation-Id`, `X-IL-flowID`), or generate one, put it in MDC, and pass it on to every outbound call. With Micrometer Tracing, `traceId`/`spanId` go into MDC automatically.
3. **Levels mean something.** `ERROR` = needs a human; `WARN` = unexpected but handled; `INFO` = business events and request summaries; `DEBUG` = off in production.
4. **Log an exception once**, where it is handled, with the stack trace — not at every layer that rethrows it.
5. **Never log secrets or personal data** — tokens, passwords, OIB, full card or policy holder data. Mask at the logger, not in Kibana.

Field list, Spring config and MDC filter, KQL queries: `references/logging.md`.

## Metrics

Every service exposes the **four golden signals**; for request-driven services that is **RED**:

| Signal | Micrometer metric (Prometheus name) |
|---|---|
| Rate | `http_server_requests_seconds_count` |
| Errors | same, `status=~"5.."` (or `outcome="SERVER_ERROR"`) |
| Duration | `http_server_requests_seconds_bucket` — needs `management.metrics.distribution.percentiles-histogram.http.server.requests=true` |
| Saturation | `jvm_memory_used_bytes{area="heap"}`, `hikaricp_connections_pending`, `jvm_threads_live_threads`, container CPU |

```promql
# error ratio, last 5 minutes
sum(rate(http_server_requests_seconds_count{application="x",status=~"5.."}[5m]))
  / sum(rate(http_server_requests_seconds_count{application="x"}[5m]))

# p95 latency
histogram_quantile(0.95, sum by (le) (rate(http_server_requests_seconds_bucket{application="x"}[5m])))
```

**Keep label cardinality bounded.** Never use IDs (user, policy, request) or raw URLs as labels — Micrometer's `uri` tag uses the route template for this reason. Add `management.metrics.tags.application=${spring.application.name}`.

## Alerts

- **Alert on symptoms users feel** (error rate, latency, SLO burn), not on causes (CPU 80%, pool 80% full). Causes go on dashboards.
- **Every alert is actionable** and links a runbook. If nobody would do anything, delete it.
- **Two severities:** *page* (user impact now) and *ticket* (fix during working hours). Everything else is a dashboard.
- **Use a `for:` duration** (usually 5–15 min) so short spikes do not page.
- **The message says what, how bad, and where:** "policy-api 5xx ratio 4.2% > 1% for 10m".

Patterns, anti-patterns and alert review checklist: `references/alerting-slo.md`.

## SLOs

1. Pick the SLI from what users feel: availability = good requests / all requests; latency = requests faster than X / all requests.
2. Pick a target below what you achieve today, not 100%. 99.9% over 30 days allows **43.2 minutes** of failure, or 1 in 1,000 requests.
3. **Error budget** = 1 − SLO. **Burn rate** = current error ratio ÷ budget ratio. Burn rate 1 spends the budget in exactly the SLO window.
4. Alert on burn rate over two windows, not on raw error rate — burn-rate table in `references/alerting-slo.md`.

## Reference files

| File | Read when |
|---|---|
| `references/logging.md` | writing logging config, choosing fields, querying Kibana |
| `references/alerting-slo.md` | writing or reviewing alerts, defining SLOs, burn-rate alerts |
| `assets/runbook-template.md` | writing the runbook an alert links to |

## Sources

- [Spring Boot: Structured logging](https://docs.spring.io/spring-boot/reference/features/logging.html#features.logging.structured)
- [Spring Boot: Metrics](https://docs.spring.io/spring-boot/reference/actuator/metrics.html)
- [Google SRE Workbook: Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/)
- [Kibana Query Language](https://www.elastic.co/guide/en/kibana/current/kuery-query.html)
