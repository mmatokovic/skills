---
name: openshift-troubleshooter
description: >-
  Diagnose and fix failing workloads on OpenShift / Kubernetes with `oc` (or `kubectl`) — Spring Boot services, API Gateway pods, and anything else deployed with Helm or a Deployment. Use when a pod is in CrashLoopBackOff, ImagePullBackOff, Pending, OOMKilled, not Ready, or restarting; when a Route or Service returns 503 / "Application is not available"; when a rollout or Helm upgrade hangs or fails; when a PVC stays Pending; when a namespace hits its quota or an SCC / permission error; and when running a production incident on the cluster. Trigger phrases: "pod keeps restarting", "CrashLoopBackOff", "OOMKilled", "pod pending", "route returns 503", "readiness probe failed", "helm upgrade failed", "rollout stuck", "oc logs", "what's wrong with this namespace".
---

# OpenShift Troubleshooter

Find out why a workload on OpenShift is not running or not serving, fix the cause, and confirm the fix. Work from symptom to root cause with read-only commands first; change nothing until you can name the cause.

Commands use `oc`. Every `oc get/describe/logs/exec` has an identical `kubectl` form. Examples are PowerShell-safe (no `grep`/`awk`); use `Select-String` or `-o jsonpath` to filter.

For the API Gateway deployment itself (chart values, routes, `runAsUser`, slow rollouts), read `webmethods-platform` → `references/api-gateway.md` first — it records the known quirks.

## Safety rules

- **Confirm the cluster and namespace before every command:** `oc whoami --show-server` and `oc project -q`. Pass `-n <ns>` explicitly instead of relying on the current project.
- **Read-only until the cause is named.** `get`, `describe`, `logs`, `events` and `exec` (without writes) change nothing.
- **Ask before** `delete`, `rollout restart`, `scale`, `patch`, `edit`, `helm rollback/uninstall`, or any change in a PROD namespace. Deleting a pod destroys the evidence of a crash; capture `logs --previous` and `describe` first.
- **Never print secrets** to the conversation. `oc get secret -o yaml` shows base64, which is not encryption.

## Workflow

### 1. Gather context

What is the symptom, since when, what changed (deploy, config, image, cluster upgrade), and what is the scope — one pod, one deployment, a namespace, or the whole cluster?

### 2. Triage the namespace

```powershell
oc get pods -n <ns> -o wide                         # status, restarts, node
oc get events -n <ns> --sort-by=.lastTimestamp      # last word is newest
oc get deploy,sts,svc,route,pvc -n <ns>
oc adm top pods -n <ns>                             # needs cluster metrics
```

### 3. Drill into the failing pod

```powershell
oc describe pod <pod> -n <ns>                       # State, Last State, Exit Code, Events
oc logs <pod> -n <ns> -c <container>                # current container
oc logs <pod> -n <ns> -c <container> --previous     # the run that crashed — usually the useful one
oc get pod <pod> -n <ns> -o jsonpath="{.status.containerStatuses[*].lastState}"
```

The **Last State → Reason and Exit Code** in `describe` is the single most useful line. Map it:

| Pod status / exit code | Usually means | Check |
|---|---|---|
| `ImagePullBackOff`, `ErrImagePull` | wrong image/tag, missing pull secret, registry unreachable | event message; `oc get sa default -n <ns> -o yaml` for `imagePullSecrets` |
| `CrashLoopBackOff`, exit **1** | app failed at startup | `logs --previous`: Spring `APPLICATION FAILED TO START`, missing env/config, DB unreachable |
| exit **137**, reason `OOMKilled` | container hit its memory **limit** | limit vs. JVM heap — see Java below |
| exit **137**, not OOMKilled | killed by liveness probe or eviction | events for `Liveness probe failed` / `Evicted` |
| exit **143** | SIGTERM; graceful shutdown took too long or was killed by a rollout | `terminationGracePeriodSeconds`; preStop |
| `Pending` | no node fits: requests too high, quota, PVC unbound, node selector/taints | `describe pod` → Events `FailedScheduling` |
| `Running` but `0/1 READY` | readiness probe failing | events `Readiness probe failed`; probe path/port; startup time |
| `CreateContainerConfigError` | referenced ConfigMap/Secret/key missing | event message names the missing key |
| Route → 503 "Application is not available" | Service has no ready endpoints, or selector/port mismatch | `oc get endpoints <svc> -n <ns>` — empty means no ready pod matches |

Details, causes and fixes per symptom: `references/common-issues.md`.

### 4. Fix

Change one thing, the one that matches the named cause. Prefer fixing the source (Helm values, Deployment manifest, Jenkins pipeline) over a live `oc edit`, which the next deploy will overwrite.

### 5. Verify

```powershell
oc rollout status deploy/<name> -n <ns> --timeout=600s
oc get pods -n <ns> -w
```

A rollout timeout is not proof of failure — check the pods before concluding. Watch restarts for 10–15 minutes after the fix and check the app's own health (`/actuator/health` for Spring).

## Java / Spring Boot specifics

Most failures here are JVM sizing or probe timing:

- **OOMKilled with a healthy heap**: the container limit counts heap + metaspace + threads + direct buffers. Set heap as a share of the limit, not as a fixed `-Xmx`: `-XX:MaxRAMPercentage=75`. Leave ≥25% of the limit for non-heap.
- **`java.lang.OutOfMemoryError` in the log but no OOMKilled**: the heap filled, not the container. That is an app problem (leak, too-large result set) — raising the limit only delays it.
- **Restarts during startup**: liveness fires before Spring finishes starting. Add a `startupProbe` on `/actuator/health/liveness` instead of raising `initialDelaySeconds`.
- **Probes**: liveness → `/actuator/health/liveness`, readiness → `/actuator/health/readiness`. Never put a DB check in liveness — a DB outage would then restart every pod.
- **CPU throttling** makes startup and GC slow without any error. Low `limits.cpu` (< 1 core) on a JVM is the usual cause; see `references/common-issues.md`.

## Helm releases

```powershell
helm list -n <ns> -a                     # -a shows failed and pending releases
helm history <release> -n <ns>
helm get values <release> -n <ns>        # what was actually applied
helm upgrade <release> <chart> -n <ns> -f values.yaml --dry-run --debug   # render before applying
```

Stuck `pending-upgrade`, immutable-field errors, values not taking effect, and rollback: `references/helm.md`.

## Production incidents

Set severity, stop the bleeding (roll back the last change if it correlates), then find the root cause. Communication cadence, severity levels and the post-incident template: `references/incident-response.md`.

## Reference files

| File | Read when |
|---|---|
| `references/common-issues.md` | a symptom from the table above needs causes, diagnostics and fixes |
| `references/helm.md` | a Helm install, upgrade or rollback fails or hangs |
| `references/incident-response.md` | running or writing up a production incident |

## Sources

- [Kubernetes: Debug Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/)
- [OpenShift CLI (oc) reference](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/cli_tools/openshift-cli-oc)
- [Spring Boot: Kubernetes probes](https://docs.spring.io/spring-boot/reference/actuator/endpoints.html#actuator.endpoints.kubernetes-probes)
