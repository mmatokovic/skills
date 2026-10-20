# Helm troubleshooting

Helm 3 stores each release revision as a Secret `sh.helm.release.v1.<release>.v<N>` in the release namespace.

## Inspect

```powershell
helm list -n <ns> -a                         # all states, including failed / pending-*
helm status <release> -n <ns>
helm history <release> -n <ns>               # revisions, status, description of each
helm get values <release> -n <ns>            # user-supplied values of the current revision
helm get values <release> -n <ns> --all      # merged with chart defaults
helm get manifest <release> -n <ns>          # what Helm applied
```

## Render before applying

```powershell
helm template <release> <chart> -n <ns> -f values.yaml > rendered.yaml
helm upgrade <release> <chart> -n <ns> -f values.yaml --dry-run --debug
helm lint <chart> -f values.yaml
```

Compare `rendered.yaml` with `helm get manifest` to see what an upgrade would change.

## Problems

### Release stuck in `pending-install` / `pending-upgrade` / `pending-rollback`

A previous command was interrupted (timeout, Ctrl+C, lost connection). Every new command fails with `another operation (install/upgrade/rollback) is in progress`.

1. Confirm nothing is still running: `helm history` and `oc get pods -n <ns>`.
2. Roll back to the last `deployed` revision: `helm rollback <release> <rev> -n <ns>`.
3. If rollback also refuses, ask before deleting the stuck revision's Secret (`sh.helm.release.v1.<release>.v<N>`) — it is the release history.

### Upgrade failed

```powershell
helm history <release> -n <ns>        # DESCRIPTION column holds the error
oc get events -n <ns> --sort-by=.lastTimestamp
```

With `--wait` / `--atomic`, Helm marks the release failed when pods do not become Ready in `--timeout` (default 5m). The real cause is then a pod problem — continue with `common-issues.md`. Large images can need `--timeout 15m`.

### `field is immutable`

Some fields cannot change in place — Deployment `spec.selector`, StatefulSet `volumeClaimTemplates`, Service `clusterIP`, Job `spec.template`. Revert the change, or delete and recreate that one resource (ask first; for a StatefulSet use `oc delete sts <name> --cascade=orphan` to keep the pods and PVCs).

### Values not applied

- Wrong key path or indentation — check with `helm get values --all`.
- `--reuse-values` kept the old value; `--reset-values` or pass the full values file.
- Later `-f` files and `--set` override earlier ones.
- A ConfigMap changed but pods did not restart — the chart needs a checksum annotation on the pod template, or run `oc rollout restart deploy/<name>` (ask first).

### Resource already exists / not owned by the release

`... exists and cannot be imported into the current release`: the object was created outside Helm or by another release. Either delete it (ask first) or adopt it by adding the label `app.kubernetes.io/managed-by=Helm` and the annotations `meta.helm.sh/release-name=<release>` and `meta.helm.sh/release-namespace=<ns>`.

### Hook failed

```powershell
oc get jobs,pods -n <ns> -l "helm.sh/hook"
oc logs job/<hook-job> -n <ns>
```

A hook Job left behind blocks the next run unless the chart sets `helm.sh/hook-delete-policy: before-hook-creation`.

## Rollback

```powershell
helm history <release> -n <ns>
helm rollback <release> <revision> -n <ns> --wait --timeout 10m
```

Rollback restores manifests, not data — PVC contents and database migrations stay as they are.
