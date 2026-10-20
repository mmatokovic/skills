# Common issues — causes, diagnostics, fixes

One section per symptom. Each lists the usual causes in order of likelihood, the commands that tell them apart, and the fix.

## Contents

1. ImagePullBackOff / ErrImagePull
2. CrashLoopBackOff
3. OOMKilled
4. Pending
5. Running but not Ready
6. Route or Service not reachable
7. PVC Pending / volume mount failure
8. Quota exceeded
9. SCC and permission errors
10. CPU throttling
11. Node problems

---

## 1. ImagePullBackOff / ErrImagePull

**Causes:** wrong image name or tag; no pull secret for a private registry; registry unreachable from the cluster; tag deleted after the deploy.

```powershell
oc describe pod <pod> -n <ns>                                  # event shows the exact image and error
oc get sa default -n <ns> -o jsonpath="{.imagePullSecrets}"     # pull secret linked?
oc get secret -n <ns> --field-selector type=kubernetes.io/dockerconfigjson
```

**Fix:** correct the image reference in the values/manifest; or create the pull secret and link it: `oc secrets link default <secret> --for=pull -n <ns>`. Pin tags — never deploy `latest`.

## 2. CrashLoopBackOff

**Causes:** app error at startup; missing env var, ConfigMap or Secret; dependency (DB, broker) unreachable; liveness probe killing a slow start; wrong command/args.

```powershell
oc logs <pod> -n <ns> --previous            # the crashed run
oc describe pod <pod> -n <ns>               # Exit Code, probe events
oc get pod <pod> -n <ns> -o jsonpath="{.spec.containers[*].env}"
```

For Spring, search the previous log for `APPLICATION FAILED TO START`, `Caused by:`, `Could not resolve placeholder`, `Connection refused`.

**Debug a container that dies too fast to exec into:** `oc debug pod/<pod> -n <ns>` starts a copy with a shell instead of the entrypoint, same env and mounts.

**Fix:** the one cause the log names. If the probe kills it during startup, add a `startupProbe` (see SKILL.md).

## 3. OOMKilled

**Causes:** memory limit too low for the JVM's total footprint; fixed `-Xmx` near or above the limit; real leak.

```powershell
oc describe pod <pod> -n <ns>                         # Last State: OOMKilled, Exit Code 137
oc get pod <pod> -n <ns> -o jsonpath="{.spec.containers[*].resources}"
oc adm top pod <pod> -n <ns> --containers
oc exec <pod> -n <ns> -- jcmd 1 VM.flags              # effective heap settings, if jcmd is in the image
```

**Fix:** `-XX:MaxRAMPercentage=75` with no `-Xmx`; set `requests.memory == limits.memory` for Java so the pod is not evicted under node pressure. If usage grows steadily until each kill, it is a leak — take a heap dump (`jcmd 1 GC.heap_dump /tmp/heap.hprof`, then `oc cp`) instead of raising the limit.

## 4. Pending

**Causes:** requests larger than any node's free capacity; namespace quota reached; PVC not bound; node selector, affinity or taint that no node satisfies.

```powershell
oc describe pod <pod> -n <ns>        # Events: FailedScheduling explains which constraint failed
oc describe quota -n <ns>
oc get pvc -n <ns>
```

**Fix:** match the constraint the event names — lower requests, free quota, fix the PVC (§7), or correct the selector.

## 5. Running but not Ready

**Causes:** readiness path or port wrong; app still starting; a dependency the readiness group checks is down.

```powershell
oc describe pod <pod> -n <ns>                                   # "Readiness probe failed: ... statuscode: 503"
oc exec <pod> -n <ns> -- curl -s localhost:8080/actuator/health/readiness
```

**Fix:** correct the probe; for Spring, check which health contributor is DOWN in the `/actuator/health` output and decide whether it belongs in the readiness group at all.

## 6. Route or Service not reachable

A Route returning **503 "Application is not available"** means the router found no ready endpoint.

```powershell
oc get route <route> -n <ns> -o jsonpath="{.spec.to.name} {.spec.port.targetPort}"
oc get svc <svc> -n <ns> -o jsonpath="{.spec.selector} {.spec.ports}"
oc get endpoints <svc> -n <ns>                                  # empty = no ready pod matches
oc get pods -n <ns> --show-labels
```

**Causes, in order:** no pod is Ready (§5); Service selector does not match pod labels; Route `targetPort` names a port the Service does not have; NetworkPolicy blocks the router. Test inside the cluster to split network from app: `oc exec <other-pod> -n <ns> -- curl -sv http://<svc>:<port>/actuator/health`.

TLS errors at the Route: check `spec.tls.termination` (`edge`, `passthrough`, `reencrypt`) matches what the pod serves.

## 7. PVC Pending / volume mount failure

```powershell
oc describe pvc <pvc> -n <ns>        # provisioning error
oc get storageclass                  # does the requested class exist, which is default
```

**Causes:** storage class missing or misspelled; access mode not supported (`ReadWriteMany` on block storage); volume `ReadWriteOnce` still attached to a pod on another node (common during rollouts — use `strategy: Recreate` for RWO volumes).

## 8. Quota exceeded

Event: `exceeded quota` or pods missing from a ReplicaSet with `FailedCreate`.

```powershell
oc describe quota -n <ns>
oc describe limitrange -n <ns>       # defaults applied to containers without requests
oc get rs -n <ns>                    # describe the newest one for FailedCreate
```

**Fix:** reduce requests, remove old ReplicaSets/pods, or ask the cluster admin to raise the quota. During a rolling update both old and new pods count — `maxSurge: 0` avoids needing extra quota.

## 9. SCC and permission errors

**OpenShift-specific.** Pods run with a random UID from the namespace's range under the `restricted-v2` SCC.

Symptoms: `unable to validate against any security context constraint`, `Permission denied` writing to a directory, an image that assumes root.

```powershell
oc get pod <pod> -n <ns> -o jsonpath="{.metadata.annotations.openshift\.io/scc}"
oc get namespace <ns> -o jsonpath="{.metadata.annotations.openshift\.io/sa\.scc\.uid-range}"
oc auth can-i <verb> <resource> -n <ns> --as=system:serviceaccount:<ns>:<sa>
```

**Fix:** make the image run as any UID (writable dirs group-owned by `0` with `g+rwX`), and remove hard-coded `runAsUser` values copied from another namespace — each namespace has its own UID range. Granting `anyuid` is a last resort and needs a cluster admin.

## 10. CPU throttling

No error — just slow startup, slow responses and long GC pauses.

```powershell
oc adm top pod <pod> -n <ns> --containers          # usage pinned at the limit = throttled
oc exec <pod> -n <ns> -- cat /sys/fs/cgroup/cpu.stat   # nr_throttled / throttled_usec rising (cgroup v2)
```

**Fix:** raise `limits.cpu` or remove the CPU limit and keep the request. A JVM sizes GC and thread pools from the CPU it sees; under 1 core it starts slowly.

## 11. Node problems

Usually needs a cluster admin; your job is to recognise it.

```powershell
oc get nodes
oc describe node <node>              # Conditions: MemoryPressure, DiskPressure, PIDPressure, Ready
oc get pods -n <ns> -o wide          # are all failing pods on the same node?
```

If every failing pod sits on one node, report the node and its conditions instead of changing the workload.
