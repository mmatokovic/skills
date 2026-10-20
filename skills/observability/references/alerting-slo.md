# Alerting and SLOs

## Alert principles

1. **Actionable** — if the person paged has nothing to do, it is not an alert.
2. **Symptoms, not causes** — page on error rate and latency; show CPU, pool usage and queue depth on dashboards.
3. **Tied to an SLO** where one exists — burn-rate alerts replace most threshold alerts.
4. **Few** — every non-actionable page trains people to ignore the next one.

| Severity | Meaning | Route |
|---|---|---|
| page / critical | users affected now | on-call, any hour |
| ticket / warning | will hurt if left; fix in working hours | team channel or Jira |
| info | — | dashboard, not an alert |

## Anatomy of a good alert (Prometheus rule)

```yaml
- alert: PolicyApiHighErrorRate
  expr: |
    sum(rate(http_server_requests_seconds_count{application="policy-api",status=~"5.."}[5m]))
      / sum(rate(http_server_requests_seconds_count{application="policy-api"}[5m])) > 0.01
  for: 10m
  labels:
    severity: page
    team: integration
  annotations:
    summary: "policy-api 5xx ratio {{ $value | humanizePercentage }} > 1% for 10m"
    description: "Clients of policy-api are getting server errors."
    runbook_url: "<link to runbook>"
```

- `for:` stops a single spike from paging. 5–15 min for pages, longer for tickets.
- `summary` states service, value, threshold and duration.
- Labels route the alert; annotations explain it.
- Low-traffic services: a ratio over 3 requests is noise — add `and sum(rate(...[5m])) > <min rps>`.

## Anti-patterns

| Don't | Do |
|---|---|
| alert on every `ERROR` log line | alert on the error *rate* |
| "Error rate high" | "5.2% > 1% for 10m on /policies" |
| `cpu > 70` on autoscaled or JVM workloads | latency or SLO burn |
| page on both cause and symptom | page on symptom, inhibit the cause alert |
| page the whole team | route to one on-call |
| alert without a runbook | `runbook_url` on every page |
| no `for:` | `for: 5m` or more |

## Alert review checklist

- Has it fired in the last 90 days? If never, is the threshold real? If often, did each firing need action?
- Does the runbook exist and still match the system?
- Would a user notice the condition? If not, demote to ticket or dashboard.

## SLO definitions

- **SLI** — a measured ratio: good events / valid events.
- **SLO** — the target for the SLI over a window, e.g. 99.9% over 30 days.
- **SLA** — a contract with consequences; set it looser than the SLO.

Common SLIs:

| Type | SLI |
|---|---|
| Availability | non-5xx responses / all responses |
| Latency | responses under 500 ms / all responses |
| Freshness (batch, pollers) | runs finished on time / scheduled runs |

Exclude what is not the service's fault (4xx from bad client input, health checks).

## Error budget

```
error budget       = 1 − SLO
budget in time     = (1 − SLO) × window       99.9% / 30 d → 43.2 min
budget in requests = (1 − SLO) × requests     99.9% / 10M  → 10,000 failures
burn rate          = observed error ratio ÷ (1 − SLO)
time to exhaust    = window ÷ burn rate       burn 5 on 30 d → 6 days
```

| SLO | Budget per 30 days |
|---|---|
| 99% | 7.2 h |
| 99.5% | 3.6 h |
| 99.9% | 43.2 min |
| 99.95% | 21.6 min |
| 99.99% | 4.3 min |

**Policy** (agree it with the team before you need it): budget healthy → ship normally; budget under ~25% → prioritise reliability work, extra review on risky changes; budget spent → only fixes and rollbacks until it recovers.

## Burn-rate alerts (multi-window)

From the Google SRE Workbook, for a 30-day SLO. Fire only when **both** the long and the short window exceed the burn rate — the long window proves it is significant, the short one proves it is still happening.

| Severity | Long window | Short window | Burn rate | Budget spent when it fires |
|---|---|---|---|---|
| page | 1 h | 5 min | 14.4 | 2% |
| page | 6 h | 30 min | 6 | 5% |
| ticket | 3 d | 6 h | 1 | 10% |

```yaml
# 99.9% SLO → allowed error ratio 0.001
- alert: PolicyApiErrorBudgetFastBurn
  expr: |
    (
      sum(rate(http_server_requests_seconds_count{application="policy-api",status=~"5.."}[1h]))
        / sum(rate(http_server_requests_seconds_count{application="policy-api"}[1h])) > (14.4 * 0.001)
    ) and (
      sum(rate(http_server_requests_seconds_count{application="policy-api",status=~"5.."}[5m]))
        / sum(rate(http_server_requests_seconds_count{application="policy-api"}[5m])) > (14.4 * 0.001)
    )
  labels:
    severity: page
  annotations:
    summary: "policy-api is burning its 30-day error budget 14x too fast"
    runbook_url: "<link to runbook>"
```

For many services, precompute the ratios as recording rules (`slo:error_ratio:rate1h`, `…rate5m`) and alert on those.

## Pitfalls

- Targeting 100% — no budget means no room to deploy.
- SLO set from aspiration instead of measured history.
- Too many SLOs per service — two or three is enough.
- Counting health-check traffic, which dilutes real errors.
