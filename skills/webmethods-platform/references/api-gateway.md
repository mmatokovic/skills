# API Gateway on OpenShift

Covers **§20** — Helm deployment, clustering, routes, passwords, and configuration import.

> Clustering (§20.11) is **TEST and PROD only**; DEV, UAT and PREPROD run a single pod.

---

## 20. API Gateway on OpenShift

### 20.1 What this is

API Gateway 11.1 runs **on OpenShift, not on the Windows IS servers** — deployed with Helm into one namespace per environment.

| Item | Value |
|---|---|
| Cluster | `api.openshiftdev.crosig.group:6443` (routes on `apps.openshiftdev.crosig.group`) |
| Namespace convention | `wm-{env}` — `wm-dev`, `wm-test` |
| Helm release name | **`apigw`** — must be exactly this (see §20.5) |
| DEV | `wm-dev`, deployed 2026-07-02 (IN-3961) — **single unclustered pod**, still Helm revision 1 |
| TEST | `wm-test`, deployed 2026-08-07 (IN-4061) — **two clustered pods** (§20.11), revision 6 since snapshots (§20.15) |
| Chart source | `kops` repo, `apigateway/helm` — locally `C:\repo-utils\kops\apigateway\helm`. One chart, `values-dev.yaml` + `values-test.yaml` (§20.14) |

Both images are `ibmwebmethods.azurecr.io/apigateway-minimal:11.1`. Verified on the running Deployments 2026-08-14 — see the correction in §20.2.

Note this is a *different* namespace convention from evaluate.js (§11), which uses `int-{env}` on the same cluster.

### 20.2 The repo is not the source of truth

> **Rule: read the running cluster, not the repo.** The chart in `kops` was itself reconstructed from the live DEV release using the technique in §20.3, because no committed copy matched what was actually deployed.

The rule is not historical. **The DEV values file carried `image.repository: apigateway` for over a year**, while `helm get values apigw -n wm-dev` and the running Deployment both said **`apigateway-minimal`**. Nobody noticed because nothing ever re-applied that file — DEV is still on Helm revision 1 from its original install. Corrected 2026-08-14. Two lessons that generalise well beyond this one field:

- **A values file that has never been re-applied is not evidence of anything.** Check the release revision first: revision 1 means the file on disk has never once had to be correct.
- **`helm get values` is the cheapest possible check** and settles these arguments in a single command. Run it before trusting any values file, including one from `kops`.

So when standing up a new environment, or when a deployment's provenance is unclear, start from `helm get values` on the previous environment (§20.3) and treat the committed file as a hint to be confirmed.

### 20.3 Recovering ground truth from a running Helm release

Reusable whenever a deployment's provenance is unclear. All read-only.

```powershell
helm list -n wm-dev                                  # release name, chart, version, revision
helm get values apigw -n wm-dev -o yaml              # exact config supplied at install
helm get values apigw -n wm-dev --all                # the above plus every chart default
helm get manifest apigw -n wm-dev                    # fully rendered resources
```

> `helm list -A` needs cluster-scope secret read, which normal users don't have. Always scope with `-n`.

Helm also stores **the chart itself** inside the release secret, which is how the real chart was recovered:

```powershell
$b64 = oc get secret sh.helm.release.v1.apigw.v1 -n wm-dev -o jsonpath="{.data.release}"
$gz  = [Convert]::FromBase64String([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64)))
$ms  = New-Object IO.MemoryStream(,$gz)
$gs  = New-Object IO.Compression.GzipStream($ms,[IO.Compression.CompressionMode]::Decompress)
$o   = (New-Object IO.StreamReader($gs)).ReadToEnd() | ConvertFrom-Json
$o.chart.metadata                    # name, version, appVersion, dependencies
$o.chart.templates                   # each: .name plus base64 .data
```

Comparing those templates against the published chart is what revealed the single local modification described next.

### 20.4 The chart actually in use

IBM's official chart, with two deliberate local changes:

| | |
|---|---|
| Base | `webmethods/apigateway` **3.12.1** from `https://ibm.github.io/webmethods-helm-charts/charts` |
| Dependencies | `common 1.0.4`, `prometheus-elasticsearch-exporter 6.6.0` |
| Change 1 | `appVersion` `10.15` → **`11.1`**, `version` → `0.1.0` |
| Change 2 | `templates/elasticsearch.yaml` patched — adds `volumeClaimDeletePolicy` and `defaultNodeSet.extraConfig` support |

22 of the 23 templates are byte-identical to the published 3.12.1.

**Change 2 is not cosmetic.** Without it, `elasticsearch.defaultNodeSet.extraConfig` is ignored — which silently drops `path.repo: /mnt/backup`, the setting that makes the snapshot volume usable.

**A third change was added later:** `templates/routes.yaml` gains an `rt` block, and `values.yaml` a matching `routes.rt` default. Upstream implements only `ui` and `admin` (§20.10). Both files carry `LOCAL ADDITION` comments.

> **Three local modifications now have to survive any chart upgrade.** Before pulling a newer IBM chart, diff its `templates/elasticsearch.yaml` and `templates/routes.yaml` against these and re-apply anything IBM hasn't adopted.

> **IBM has not published an 11.1 chart.** The newest published version (3.12.1) is still appVersion 10.15, which is why the appVersion is bumped locally. Re-check whether IBM has published a newer chart before repeating this for another environment.

### 20.5 What changes per environment

Everything else is copied from the previous environment's live values.

| Setting | Notes |
|---|---|
| `extraContainers[].env` → `NAMESPACE` | the target namespace, e.g. `wm-test` — used by fluentd to tag logs |
| `routes.ui.hostName` | `apigw-ui.{env}.apps.openshiftdev.crosig.group` |
| `routes.admin.hostName` | `apigw-admin.{env}.apps.openshiftdev.crosig.group` |
| `routes.rt.hostName` | `apigw.{env}.apps.openshiftdev.crosig.group` — see §20.10 |
| `prometheus-elasticsearch-exporter.podSecurityContext.runAsUser` | **namespace-specific** — see below |
| `secrets.generateAdminSecret` / `generateElasticSecrets` | `true` on a fresh namespace; `false` once the secrets exist |
| `replicaCount` / `autoscaling.enabled` | `2` / `false` for a clustered environment — see §20.11 |
| `image.pullPolicy` | `Always` while the tag is mutable — see §20.11 |

**The `runAsUser` value is the one guaranteed to fail if copied.** OpenShift allocates each namespace its own UID range, so DEV's value is invalid in TEST. Read the real range and use the first number:

```powershell
oc get namespace wm-test -o jsonpath="{.metadata.annotations.openshift\.io/sa\.scc\.uid-range}"
```

TEST returned `1001680000/10000` → `runAsUser: 1001680000`. DEV's is `1001676969`.

**The release name must be `apigw`.** Resource names derive from it (`apigw-apigateway-admin-password`, `apigw-apigateway-es-http`), and the purge cronjob and exporter reference those names.

### 20.6 Two things the chart does not create

Both must exist **before** `helm install`, or the deployment stalls:

- **`regcred`** — the pull secret for `ibmwebmethods.azurecr.io`. Copy it from the lower environment rather than handling the token (§20.7 step 3).
- **`es-snapshots` PVC** — mounted into the Elasticsearch node set at `/mnt/backup`, but `extraPVCs` is empty so the chart won't create it. Elasticsearch will not schedule without it. DEV/TEST spec: `ReadWriteMany`, `nfs-client`, `50Gi`.

### 20.7 Deployment sequence

Full copy-paste procedure is in the Confluence page (§20.13). Summary:

1. `oc new-project wm-{env}`
2. Read the UID range, set `runAsUser` in `values-{env}.yaml`
3. Copy `regcred` from the lower environment's namespace
4. `oc apply -f es-snapshots-pvc.yaml -n wm-{env}`
5. `helm dependency update .` then `helm upgrade --install apigw . -f values-{env}.yaml -n wm-{env} --force-conflicts` (§20.11)
6. Wait for the pods; the gateway startup probe allows up to 6 minutes per pod, plus ~2 minutes image pull
7. Read the generated admin password, log into the UI
8. Import APIs/applications/aliases and configure the RH-SSO connection — see §20.12

> **Always `helm template` before installing.** It renders everything locally and catches value errors without touching the cluster:
> ```powershell
> helm template apigw . -f values-test.yaml -n wm-test
> ```

> ⚠️ **`helm template` lies about passwords — use `--dry-run=server` to preview an upgrade.** `templates/secret.yaml` uses `lookup` to reuse existing secrets, falling back to `randAlphaNum 12`. `helm template` has no cluster connection, so `lookup` returns empty and **every render shows freshly randomised passwords**. So does `--dry-run` on its own, which in Helm 4 means `--dry-run=client`. Neither reflects what an upgrade would do. Only a server-side dry-run resolves the lookup:
> ```powershell
> helm upgrade apigw . -f values-test.yaml -n wm-test --dry-run=server
> ```
> Confirmed on TEST 2026-08-14: client-side showed all three passwords rotating; server-side showed them preserved, and the real upgrade preserved them. Diff the server-side render against `helm get manifest` to see the true change set before applying — that is how the snapshot change in §20.15 was shown to touch nothing that was running.

### 20.8 Passwords

On a fresh install the chart generates three secrets. Read any of them with:

```powershell
oc extract secret/apigw-apigateway-admin-password -n wm-test --to=-
```

(`apigw-apigateway-sag-user-es` and `-sag-user-kb` are the internal Elasticsearch and Kibana accounts.) The chart's install notes suggest a `base64 --decode` pipeline — that's bash and won't work in PowerShell.

> ⚠️ **Changing the Administrator password in the UI is not sufficient.** The `purge-transaction-events` cronjob authenticates as `Administrator` using the `apigw-apigateway-admin-password` secret. Its `curl` calls don't check response codes, so if the secret still holds the old password the job **reports success while silently doing nothing**, and transaction events accumulate in Elasticsearch until storage fills.
>
> After changing it in the UI, patch the secret to match:
> ```powershell
> '{"data":{"password":"<base64-of-new-password>"}}' | Out-File "$env:TEMP\patch.json" -Encoding ascii
> oc patch secret apigw-apigateway-admin-password -n wm-test --patch-file "$env:TEMP\patch.json"
> ```
> Use `--patch-file`; inline `-p '{...}'` gets its quotes stripped by PowerShell 5.1 and fails with `invalid character '\\'`. Then verify by running the cronjob on demand:
> ```powershell
> oc create job --from=cronjob/apigw-apigateway-purge-transaction-events purge-test -n wm-test
> oc logs job/purge-test -n wm-test
> ```
> A returned `jobId` means authentication worked; a `401` means the two are still out of sync.

### 20.9 Known gaps and risks

- **The runtime (`rt`) route is not created by the chart.** See §20.10 — it needs both a route *and* a listener port that only exists in API Gateway's own configuration.
- **The registry pull token may still need rotating.** A live `ibmwebmethods.azurecr.io` username and token were once committed in plaintext, across several commits, to the chart repository that preceded `kops`. Retiring that repository removes the hosted copy but does **not** rotate the credential and does not reach existing local clones. Confirm it has been rotated; `regcred` in each namespace is the only place it should live.
- **The fluentd config embeds Elasticsearch credentials in plaintext** (`logstash_internal` / password) inside the values. If a values file carrying this is committed, that credential joins the above.
- **DEV runs a single unclustered pod.** TEST is clustered (§20.11), so the two environments deliberately differ.
- **The Administrator password is `manage` on both DEV and TEST** — the API Gateway factory default. `oc extract secret/apigw-apigateway-admin-password -n wm-{env} --to=-` returns it on either. The chart *can* generate a strong one (`secrets.generateAdminSecret`), but on both environments the secret predates that and was never changed. Changing it means changing the secret too, not just the UI — see the warning in §20.8.
- **DEV has objects Helm does not manage.** Its `rt` route and an `apigw-apigateway-es-http` route both exist in the cluster but not in the release manifest, and its Elasticsearch snapshot setup is hand-made (§20.15). The `es-http` route publishes Elasticsearch on a public hostname over plain HTTP — the chart sets `selfSignedCertificate.disabled: true`. TEST has neither route.
- **DEV has `autoscaling.enabled: true` with `replicaCount: 1`.** The chart ships no HorizontalPodAutoscaler, so this only suppresses `replicas` on the Deployment and Kubernetes defaults it to 1. Harmless while DEV wants one pod, but raising `replicaCount` there would silently do nothing. TEST has it correctly `false` (§20.11).

### 20.10 The runtime (`rt`) endpoint needs two separate things

Serving actual API traffic requires **both** an OpenShift route **and** a listener port inside API Gateway. They are configured in different places, and neither is created by the Helm chart.

#### Part 1 — the route

**Upstream `templates/routes.yaml` implements only `ui` and `admin`** — there is no `rt` block and no values key that would add one, even though the chart's `ingresses` section does support `ui`/`rt`/`admin`. The Route template is OpenShift-specific and was evidently added later and left incomplete. Ingresses aren't a usable substitute here: the chart defaults them to `className: nginx`, while OpenShift routes traffic through HAProxy.

On DEV the third route was therefore created **by hand** — it carries no `app.kubernetes.io/managed-by` label and exists nowhere in version control:

| Route | Host | Service | targetPort |
|---|---|---|---|
| `apigw` | `apigw.dev.apps.openshiftdev.crosig.group` | `apigw-apigateway-rt` | `rtport` (5556) |
| `apigw-admin` | `apigw-admin.dev...` | `apigw-apigateway-admin` | `adminport` (5555) |
| `apigw-ui` | `apigw-ui.dev...` | `apigw-apigateway-ui` | `uiport` (9072) |
| `apigw-apigateway-es-http` | `apigw-apigateway-es-http-wm-dev...` | `apigw-apigateway-es-http` | `http` |

> Note DEV also exposes **Elasticsearch itself** on a route. Worth questioning rather than copying — it puts the datastore on the network directly.

**The chart fixes this** rather than working around it. `templates/routes.yaml` gained an `rt` block mirroring `ui`/`admin` (guarded with `and` so older values files still render), and the chart's `values.yaml` gained a `routes.rt` default. All three routes are now declared the same way:

```yaml
routes:
  rt:
    enabled: true
    name: apigw
    hostName: apigw.test.apps.openshiftdev.crosig.group
    portName: rtport
```

Confirm all three show `managed-by=Helm`:

```powershell
oc get route -n wm-test -o custom-columns="NAME:.metadata.name,HOST:.spec.host,SERVICE:.spec.to.name,MANAGEDBY:.metadata.labels.app\.kubernetes\.io/managed-by"
```

> If an environment already has a hand-made `apigw` route, delete it before upgrading — Helm refuses to adopt a resource it doesn't own.

#### Part 2 — the listener port (the non-obvious half)

A route alone gives **HTTP 503**. The gateway must also have a listener on 5556, and that is **API Gateway configuration stored in Elasticsearch** — not a chart setting, not a container port.

A fresh install has only two listeners; DEV, with configuration in place, has three:

| | Configured listeners |
|---|---|
| Fresh install (TEST at deploy time) | `HTTPListener@5555`, `HTTPSListener@5543` |
| DEV | `HTTPListener@5555`, `HTTPSListener@5543`, **`HTTPListener@5556`** |

Diagnosing this: the service will show healthy endpoints on `:5556` because pod readiness is probed on **5555**, so the endpoint list is not evidence the runtime port is up. Check inside the pod instead — `15B4` is hex for 5556:

```powershell
oc exec <pod> -c apigateway -n wm-test -- grep -c 15B4 /proc/net/tcp   # 0 = not listening
```

And list what the gateway believes it has:

```powershell
curl -u Administrator:<pw> http://apigw-admin.{env}.apps.openshiftdev.crosig.group/rest/apigateway/ports
```

**The listener must be created manually** in the API Gateway administration UI — it does *not* arrive with the configuration import. Confirmed on TEST on 2026-08-07: after creating the 5556 port in the UI, the runtime route immediately returned HTTP 200.

Create it once, not per pod. Port configuration lives in the shared Elasticsearch, so in a clustered environment both pods pick it up without a restart — verified by `grep -c 15B4 /proc/net/tcp` returning `1` on both.

A 503 on the runtime route before the listener exists is expected, not a fault. **Verify the route only after creating the port.**

### 20.11 Clustering (two or more gateway pods)

TEST runs **two clustered pods**, matching the topology used for IS (esb3/esb4) and UM (um3/um4) and the team agreement that TEST mirrors the intended PROD build. DEV remains a single unclustered pod.

API Gateway clusters via **Apache Ignite**, which shares live runtime state between pods — admin sessions, rate-limit and quota counters, and caches. APIs, policies and applications live in Elasticsearch and are shared regardless. Without Ignite, N pods behave as N independent gateways behind one address: sessions drop when you're routed to a different pod, and a "100 requests/min" policy actually permits 100 × N.

#### The two settings

```yaml
replicaCount: 2
autoscaling:
  enabled: false
```

`cluster.aware` is **computed**, not set directly:

```
aware = (replicaCount > 1) OR apigw.clusterAware
```

so raising `replicaCount` is what switches clustering on. It is evaluated once at install time and baked into the pod config.

> **`autoscaling.enabled` must be `false`.** This chart ships **no HorizontalPodAutoscaler template** — `enabled: true` autoscales nothing. All it does is suppress the `replicas` field on the Deployment, which Kubernetes then defaults to 1. With it left `true`, `replicaCount` is ignored for pod count (though still used for the `aware` calculation), and you silently get one pod.

Everything Ignite needs is already in the chart's defaults — discovery port `10100`, communication port `10400`, the `-rt` service for peer lookup, and a service account bound to `cluster-discovery-rolebinding` so Ignite can query the Kubernetes API for sibling pods. Only the switch above is needed.

`actionOnStartupError: standalone` is the safe fallback, equivalent to the IS setting in §5.1 — a pod that can't join starts standalone rather than failing.

#### ⚠️ Mutable image tags break clustering

**The first clustered attempt failed**, and the cause is worth remembering:

```
Topology snapshot [ver=1, servers=1 ... ver=2.18.0#20260423]     <- pod A
Topology snapshot [ver=1, servers=1 ... ver=2.17.0#20250209]     <- pod B
```

Each pod formed its own single-node grid. The logs showed the pods reaching each other but rejecting the join:

```
Unknown connection detected (is some other software connecting to this Ignite port,
or is this an incompatible Ignite node? ...) [rmtAddr=/10.131.0.40]
```

Root cause: `11.1` is a **mutable tag**, and `imagePullPolicy` was `IfNotPresent`. The two pods landed on different worker nodes, each of which had cached a *different build* of that same tag — confirmed by their image digests:

| Pod | Node | Digest | Ignite |
|---|---|---|---|
| A | worker02 | `sha256:11972ad2…` | 2.18.0 |
| B | worker01 | `sha256:11f26885…` | 2.17.0 |

Ignite refuses to form a topology across mismatched versions. DEV never surfaced this because a single pod has nothing to disagree with — and DEV runs the *older* `sha256:11f26885…` build to this day.

**Fix applied:**

```yaml
image:
  pullPolicy: Always
```

Both pods then pull the current `11.1` at start and land on the same digest. Verify with:

```powershell
oc get pods -n wm-test -l app.kubernetes.io/name=apigateway -o jsonpath="{range .items[*]}{.metadata.name}{'  '}{range .status.containerStatuses[?(@.name=='apigateway')]}{.imageID}{end}{'\n'}{end}"
```

> **Better fix before PROD: pin an immutable tag** (e.g. `11.1.0.x` — the chart's own `customcerts` sample references `apigateway-minimal:11.1.0.11`). `Always` closes the node-cache gap but still leaves a narrow window if the registry tag is republished between two pods starting. Note the chart hardcodes `"{{ .Values.image.repository }}:{{ .Values.image.tag }}"`, so pinning by **digest** is not possible without patching the template.

#### Verifying the cluster formed

```powershell
oc logs <pod> -c apigateway -n wm-test | Select-String "Topology snapshot" | Select-Object -Last 1
```

Success looks like `servers=2` with **both** nodes listed and the **same** Ignite version:

```
Topology snapshot [ver=4, servers=2, clients=0, state=ACTIVE, CPUs=16, offheap=3.2GB, heap=2.0GB,
  aliveNodes=[TcpDiscoveryNode [consistentId=10.128.3.145:10100, ver=2.18.0#20260423],
              TcpDiscoveryNode [consistentId=10.131.0.44:10100, ver=2.18.0#20260423]]]
```

`servers=1` on each pod means split-brain — check the image digests first.

#### ⚠️ Helm 4: `helm upgrade` conflicts with the ECK operator

The initial `helm install` succeeds, but **every subsequent `helm upgrade` fails**:

```
Error: UPGRADE FAILED: conflict occurred while applying object wm-test/apigw-apigateway
elasticsearch.k8s.elastic.co/v1, Kind=Elasticsearch: Apply failed with 1 conflict:
conflict with "elastic-operator" using elasticsearch.k8s.elastic.co/v1: .spec.nodeSets
```

Helm 4 defaults to **server-side apply**; the ECK operator has since taken field ownership of `.spec.nodeSets` on the Elasticsearch object. Helm 3 used client-side apply and never hit this — DEV was deployed with Helm 3, which is why it isn't documented anywhere.

Add `--force-conflicts` to every upgrade:

```powershell
helm upgrade --install apigw . -f values-test.yaml -n wm-test --force-conflicts
```

This was safe in practice — Elasticsearch was not restarted or reconciled, because the values being reapplied are identical to those at install. Confirm the ES pod's age is unchanged after upgrading.

#### Rollout timing

A rolling restart of two gateway pods takes **longer than `oc rollout status`'s default patience**. The image is ~2 GB and, with `pullPolicy: Always`, is pulled on every pod start (~2 minutes), on top of a gateway startup probe that allows up to 6 minutes. Budget 10–15 minutes and use an explicit timeout:

```powershell
oc rollout status deployment/apigw-apigateway -n wm-test --timeout=900s
```

A timeout message is not a failure — check `oc get pods` before concluding anything.

### 20.12 Configuration import and UI setup

A freshly deployed gateway is empty — §20.1–20.11 get the platform running, but every API, policy and integration still has to be brought across. Content arrives by three different mechanisms, and **the order matters**.

#### What comes from where

| Item | Mechanism | Per-environment edits needed |
|---|---|---|
| RH-SSO / Keycloak connection | export/import, or set up by hand | non-prod: none — see below |
| Global policies | export from the lower environment | **none** — identical across all environments |
| Aliases | export from the lower environment | **yes, every single one** |
| APIs, applications, OAuth scopes | **promotion management** | none |
| Runtime listener `HTTPListener@5556` | **manual in the UI** (§20.10) | n/a |

#### Order of work

1. RH-SSO / Keycloak connection
2. Global policies
3. Aliases — import, then edit each one for this environment
4. Create the promotion management stage **on the lower environment**
5. Promote APIs, applications and OAuth scopes — **excluding aliases**
6. Create the 5556 listener (§20.10)

Steps 3 and 5 are in that order for a reason — see the warning below.

#### RH-SSO / Keycloak connection

API Gateway authenticates against RH-SSO (Keycloak). Import it from another environment or configure it by hand.

| Environment | Source |
|---|---|
| DEV, TEST, UAT, PREPROD | **Identical across all non-prod environments** — import from any existing non-prod environment rather than rebuilding it. |
| PROD | Points at the **production** Keycloak, so the non-prod configuration does not apply. Export it from the **old (10.x) PROD** environment instead. |

The non-prod realm API Gateway targets is **`rh-sso-test3`** on the OpenShift dev cluster, reached via `authcotest.crosig.hr` (confirmed August 2026). An `rh-sso-test2` project exists on the same cluster and is **not** the one to use.

#### Global policies

Export from the lower environment and import as-is. These are the same across every environment, so no post-import editing is required.

#### Aliases

Aliases can be exported from the lower environment, but **every alias must then be edited** for the target environment. They are mostly endpoints plus usernames and passwords, all of which differ per environment.

> ⚠️ An imported-but-unedited alias points the new gateway straight at the lower environment's backends. Edit them all before enabling anything.

#### Promotion management

Promotion is configured **on the lower environment**, pointing at the higher one. So DEV holds the stage that promotes into TEST, TEST holds the stage that promotes into UAT, and so on.

**Manage → Promotion management → Add stage**

| Field | Value |
|---|---|
| Stage name | `APIGW {ENV}` — the **target** environment |
| URL | the target environment's **admin route** |

Worked example, as created on DEV for the TEST rollout:

```
Stage name : APIGW TEST
URL        : http://apigw-admin.test.apps.openshiftdev.crosig.group
```

Then use that stage to promote **APIs, applications and OAuth scopes** from the lower environment. OAuth scopes promoting this way was confirmed on the TEST rollout (2026-08-07).

> The step-by-step procedure for running an individual promotion — asset selection, dependent APIs, naming convention and the overwrite set — is **§20.16**.

> ⚠️ **Do not overwrite aliases when promoting.** Aliases were corrected for this environment in step 3; a promotion that includes them will push the *source* environment's values back over your edits, silently repointing the gateway at the lower environment's backends. Exclude aliases from every promotion, not just the first.

**Promote everything in one go — and ignore the timeout.** All APIs can be selected and promoted together. After a while the UI will report a **timeout error**, but this is only the browser giving up on the request: the promotion keeps running server-side and all APIs do arrive. Wait it out and verify the target environment rather than retrying — a retry is unnecessary and risks acting on a half-finished promotion.

#### Not covered by any import

- **The runtime listener port** (`HTTPListener@5556`) must be created manually in the administration UI — see §20.10. Confirmed on TEST: it does not arrive with the configuration import.

### 20.13 Confluence

Step-by-step install guide, published: [How to install API Gateway on OpenShift](https://crosig.atlassian.net/wiki/spaces/ID/pages/6103105538/How+to+install+API+Gateway+on+OpenShift). Eight parts — prerequisites and CLI tools, building the values file from the previous environment's live Helm release, namespace preparation, deploy, clustering, the `rt` endpoint, changing the Administrator password, and configuration import. Go there for the copy-paste commands and screenshots; this file carries the diagnostics and the reasoning behind them.

Promotion management, click-by-click: [How to use promotion management](https://crosig.atlassian.net/wiki/spaces/ID/pages/6133678081/How+to+use+promotion+management) — the golden rules, the per-step screenshots and the naming convention. Summarised in §20.16.

Per-environment topology, including hostnames, ports and load balancers: [Architecture Overview](https://crosig.atlassian.net/wiki/spaces/ID/pages/6045302793/Architecture+Overview).

### 20.14 Chart layout: one chart, one values file per environment

Consolidated 2026-08-14. `C:\repo-utils\kops\apigateway\helm` holds a single chart serving both environments:

| File | Contents |
|---|---|
| `values.yaml` | **pristine upstream defaults — never environment config** |
| `values-dev.yaml` | everything wm-dev needs, self-contained |
| `values-test.yaml` | everything wm-test needs, self-contained |

```powershell
helm upgrade apigw . -f values-dev.yaml  --install -n wm-dev  --force-conflicts
helm upgrade apigw . -f values-test.yaml --install -n wm-test --force-conflicts
```

This replaced an older invocation that stacked three files (`-f values.yaml -f house-keeping-job/values.yaml -f fluentd-sidecar/values.yaml`), with environment settings edited directly into `values.yaml`. Both environment files were verified byte-for-byte against `helm get values` for their live release before the change was committed.

**`diff values-dev.yaml values-test.yaml` is now the authoritative statement of how the environments differ** — twelve settings, all listed in §20.5 and §20.11. That diff is the first thing to read when standing up a new environment.

Four traps in this layout:

- **`jobs` is a list, so a second `-f` replaces it rather than appending.** Passing `house-keeping-job/` and `es-snapshot-job/` as separate `-f` files means the last one wins and the earlier job silently disappears. Both jobs are therefore folded into each `values-{env}.yaml`, with `es-snapshot-job/es-snapshot-job.yaml` kept only as the canonical copy to paste into a new environment.
- **`Chart.lock` and `charts/` are gitignored** by `kops/.gitignore`. A fresh clone has neither, so `helm dependency build` fails — use **`helm dependency update`**.
- **Job scripts must use a literal block (`|-`), not folded (`>-`).** In a folded scalar YAML preserves the newlines of more-indented lines, so a `curl` written across several indented lines arrives at `sh -c` as several separate commands and fails. Keep each `curl` on one line.
- **`fluentd-sidecar/Dockerfile` is the only recipe for the image both environments actually run** (`container-registry.crosig.group/integration/fluentd:latest`). It adds `fluent-plugin-elasticsearch` and the `elasticsearch` gem on top of the stock fluentd image, which ships neither — without them the sidecar can only write to stdout. Do not replace it with an upstream sample.

### 20.15 Elasticsearch snapshots

Elasticsearch holds the gateway's **entire** state — APIs, applications, policies, aliases. The pods are stateless, so an ES snapshot is the only thing between a lost volume and a lost gateway.

Three layers have to line up, and "snapshots are configured" usually means only the first:

| Layer | Where |
|---|---|
| Volume + `path.repo` | `elasticsearch.defaultNodeSet.extraConfig` and the `es-snapshots` PVC (§20.6) |
| Registered repository | `PUT _snapshot/apigw-config-snapshots` |
| Schedule (SLM policy) | `PUT _slm/policy/apigw-config-daily` |

Elasticsearch rejects any repository whose location is not under `path.repo`, which is why layer 1 must come first.

#### ⚠️ A green snapshot can contain nothing

DEV's policy targets `gateway_tenant_assets`, **an index that does not exist on any environment** — the gateway's assets sit behind the alias `gateway_default_assets`. Combined with `ignore_unavailable: true`, Elasticsearch skips the missing index and reports success. DEV had produced 43 consecutive `SUCCESS` snapshots containing zero indices and zero shards before this was noticed on 2026-08-14.

**`SUCCESS` alone means nothing. Check the shard counts:**

```powershell
oc exec -n wm-{env} apigw-apigateway-es-default-0 -- curl -s -u "elastic:$pw" `
  "http://localhost:9200/_cat/snapshots/apigw-config-snapshots?h=id,status,indices,successful_shards&v"
```

`SUCCESS 1 1` is a real backup. **`SUCCESS 0 0` is an empty one.** Run this on any environment claiming to have snapshots, including after any change to the policy.

#### Current state

| | DEV | TEST |
|---|---|---|
| Managed by | hand, outside Helm | `es-setup-snapshot` hook in `values-test.yaml` |
| Indices | `gateway_tenant_assets` — **does not exist** | `gateway_default_assets` — the real alias |
| `ignore_unavailable` | `true` — masks the failure | `false` — fails loudly |
| Result | `SUCCESS 0 0`, empty | `SUCCESS 1 1`, verified 2026-08-14 |

DEV was deliberately left alone. Do not copy its policy into a new environment; copy TEST's.

#### Setting it up on a new environment

The job is in `es-snapshot-job/es-snapshot-job.yaml` — paste its entry into the target's `values-{env}.yaml` `jobs` list (it cannot be passed as its own `-f`, see §20.14). It is a `post-install,post-upgrade` hook making two idempotent PUTs, so it re-runs harmlessly on every upgrade. Settings that matter:

- `"type": "fs"`, `"location": "/mnt/backup/apigw-config-snapshots"` — **not** `azure`; the volume is the NFS `es-snapshots` PVC
- `ES_HOST: http://apigw-apigateway-es-http` — the job runs in its own pod, so `localhost` reaches nothing
- `"indices": ["gateway_default_assets"]`, `"ignore_unavailable": false`
- schedule `0 0 2 * * ?`, retention 30 days / keep 5–30

Nothing else is needed if the `es-snapshots` PVC already exists (§20.6) — the mount is `0777`, so Elasticsearch creates the repository subdirectory itself.

Then prove it, rather than waiting for 02:00 and trusting an unfired schedule:

```powershell
oc exec -n wm-test apigw-apigateway-es-default-0 -- curl -s -XPOST -u "elastic:$pw" "http://localhost:9200/_slm/policy/apigw-config-daily/_execute?pretty"
```

and re-run the `_cat/snapshots` check above.

> **ES cluster health is `yellow` on both environments** — single node, replica shards unassignable, 5 unassigned shards each. It is the normal steady state, not a fault, and snapshots succeed regardless because they only need primaries.
### 20.16 Running a promotion (day-to-day)

Confluence: [How to use promotion management](https://crosig.atlassian.net/wiki/spaces/ID/pages/6133678081/How+to+use+promotion+management) — the click-by-click version with screenshots.

§20.12 covers promotion as part of a rollout. This is how an *individual* promotion is run once the stage exists — the routine "promote this API to TEST" task.

#### Two rules that hold for every promotion

**1. Promote the API together with all its Applications and Scopes.** Even when the task reads "promote one API", an API on its own is incomplete: the Applications registered against it and its Gateway scopes have to travel with it. The reverse case is the same — adding a new Application to an existing API still means promoting the API, *all* its Applications, and the Scopes together. Leaving any of them out produces an inconsistent state on the target.

**2. On the Overwrite step use `Custom`, and never tick `Alias`.** Aliases hold the environment-specific configuration — endpoints, routing, credentials. Overwriting them pushes the source environment's values over the target's and repoints the gateway at the lower environment's backends (§20.12). Unchecked on every promotion, no exceptions.

#### The procedure

1. **Manage → Promotion management → Promotions** tab → **+ Promote** (top right).
2. **Assets and dependencies** — everything available, grouped into `APIs`, `Applications`, `Gateway scope`. Select the API, the Application(s) registered against it, *and* the scope(s) tied to them. → **Next**.
3. **Dependent APIs** — the gateway expands the selection and lists **every API the chosen Application is linked to**, not just the one you started from. Select all of them. The Application depends on all of them.
4. **Stages** — tick the target stage, e.g. `APIGW test` → `http://apigw-admin.test.apps.openshiftdev.crosig.group`.
5. **Promote** — name, description and overwrite set, below.
6. Review and start the promotion.

#### Naming convention

| Field | Format | Example |
|---|---|---|
| Name | `<ASSET> to <ENVIRONMENT>` — short and directional | `PolicyAPI to TEST` |
| Description | `yyyy-MM-dd [JIRA-TICKET] - <what is promoted and where>` — always date and ticket first | `2026-08-18 [IN-4061] - PolicyAPI + applications and scopes to TEST` |

#### Overwrite selection

Select **`Custom`** — never `None`, never `All` — then tick exactly:

| Tick | Leave unticked |
|---|---|
| APIs | **Alias** ⚠️ never |
| Policies | everything else not listed left |
| Applications | |
| Registered Application | |
| Gateway scope | |

#### After promoting

- Verify the API, its Applications and its Scopes appear on the target.
- Call the promoted API/Application through Postman against the target environment — appearing in the UI is not proof it routes.
- A UI **timeout** on a large promotion is the browser giving up, not a failure; the promotion continues server-side (§20.12). Verify the target rather than retrying.
