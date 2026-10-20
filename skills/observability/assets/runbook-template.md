# Runbook: <AlertName>

| | |
|---|---|
| **Severity** | page / ticket |
| **Service** | <service, namespace> |
| **Owner** | <team> |
| **Fires when** | <exact condition, e.g. 5xx ratio > 1% for 10m> |
| **User impact** | <what users or partners experience> |

## 1. Confirm

- Dashboard: <link>
- Kibana: `service.name : "<service>" and log.level : "ERROR"` — <saved search link>
- Is it still happening? Is it one endpoint or all?

## 2. What changed?

```powershell
helm history <release> -n <ns>
oc rollout history deploy/<name> -n <ns>
oc get events -n <ns> --sort-by=.lastTimestamp
```

Recent Jenkins builds, config/secret changes, certificate expiry, upstream system status.

## 3. Known causes

| Cause | How to recognise | Fix |
|---|---|---|
| <bad deploy> | errors started at deploy time | `helm rollback <release> <rev> -n <ns>` |
| <DB unavailable> | `SQLException` / `hikaricp_connections_pending` rising | <contact / failover> |
| <upstream down> | `Connection refused` / timeouts to <host> | <contact / circuit breaker> |

## 4. Mitigate

Fastest safe action that stops user impact — rollback, scale, failover, disable feature. Note the time and action in the incident channel.

## 5. Escalate

| After | To |
|---|---|
| <15 min> unresolved | <team lead / platform team> |
| data loss or security suspected | <security contact> immediately |

## 6. Afterwards

Post-incident review if severity was page. Update this runbook with anything that was missing.
