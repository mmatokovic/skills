# Incident response

## Severity

| Level | Meaning | Response |
|---|---|---|
| SEV-1 | Production outage, data loss or security breach | everyone needed, now; updates every 15–30 min |
| SEV-2 | Major degradation, many users or a key partner affected | on-call now; updates every 30–60 min |
| SEV-3 | Partial impairment, workaround exists | business hours |
| SEV-4 | Cosmetic or minimal impact | backlog |

## Phases

1. **Detect** — confirm the alert or report is real; set severity.
2. **Triage** — scope (one pod, service, namespace, cluster, external dependency) and impact.
3. **Mitigate** — stop user impact first. If the start correlates with a deploy, roll it back (`helm rollback` / `oc rollout undo`) before searching for the root cause. Scaling up or failing over is also mitigation.
4. **Investigate** — root cause, with the workflow in SKILL.md. Save evidence (`oc logs --previous`, `describe`, events) before pods are replaced.
5. **Resolve and verify** — fix, then watch for 15–30 minutes.
6. **Review** — write the post-incident review within a few days.

## What changed?

Most incidents follow a change. Check these first:

```powershell
helm history <release> -n <ns>
oc rollout history deploy/<name> -n <ns>
oc get events -n <ns> --sort-by=.lastTimestamp
oc get pods -n <ns> -o custom-columns="NAME:.metadata.name,START:.status.startTime,IMAGE:.spec.containers[*].image"
```

Also: Jenkins builds in the time window, config or secret changes, certificate expiry, cluster upgrades, upstream/partner changes.

## Communication

- One incident lead coordinates; others investigate.
- Each update gives: current impact, what is being done, next update time.
- Record a timeline as you go (time, action, result) — the review is built from it.

## Post-incident review template

```markdown
# Incident: <title> — <date>

**Severity:** SEV-x   **Duration:** <start> – <end> (<minutes>)   **Lead:** <name>

## Impact
Who and what was affected, for how long, how many requests or transactions failed.

## Timeline
| Time | Event |
|---|---|
| hh:mm | detected by … |
| hh:mm | mitigated by … |

## Root cause
What failed and why. Include the triggering change.

## What went well / what didn't

## Action items
| Action | Owner | Due | Ticket |
|---|---|---|---|
```

Keep the review blameless: describe systems and decisions, not people.
