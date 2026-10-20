---
name: webmethods-platform
description: >-
  Use when working with the Crosig webMethods platform — Integration Server,
  Universal Messaging, API Gateway, Terracotta/BigMemory clustering, DBCC and
  Oracle schemas, JDBC pools, Filebeat/Kibana log shipping, or the evaluate.js
  JSONata service. Covers installing and configuring a new environment, the
  11.1 upgrade, clustering, and troubleshooting: DBCC schema errors (ORA-00942,
  ORA-00904, ORA-01950), installer hangs, slow IS shutdown, UM realm and
  failover problems, API Gateway Helm deployment on OpenShift, Elasticsearch
  snapshots and gateway backup, Ignite clustering faults, promotion management
  between API Gateway environments, and package deployment via
  Jenkins/WmDeployer. Also covers the local per-developer workstation install —
  a local install, Designer, or a second webMethods version on one machine. Use
  whenever an
  environment name (DEV, TEST, UAT/lab/edu, PREPROD/stage/tune, PROD) appears
  alongside webMethods, IS, UM, apigw, or wm-* work.
---

# Crosig webMethods platform

Operational knowledge for the webMethods 11.1 platform: Integration Server, Universal Messaging, API Gateway, and the surrounding tooling.

**Establish two things before doing anything else:** which environment, and whether it is clustered. Roughly half of this documentation applies only to clustered environments.

## Environments

| Environment | Also called | IS | UM | API GW | Windows servers |
|---|---|---|---|---|---|
| DEV | — | 1 node | 1 node | 1 pod | own |
| TEST | — | **2 nodes, clustered** | **2 nodes, clustered** | **2 pods, clustered** | own |
| UAT | lab, edu | 1 node | 1 node | 1 pod | **shared with PREPROD** |
| PREPROD | stage, tune | 1 node | 1 node | 1 pod | **shared with UAT** |
| PROD | — | **2 nodes, clustered** | **2 nodes, clustered** | **2 pods, clustered** | own |

UAT and PREPROD share one Windows server for IS and one for UM; every other installation has its own. That forces port, memory and service-naming decisions — see the decisions block in `references/installation.md`.

**A developer's local install is not in this matrix** and is not an environment we deploy to. It is set up differently on purpose — `references/local-development.md` (§21). Nothing in that file changes how the environments above are built.

### Per-environment endpoints

Two distinct front doors, in two distinct zones. The **API access URL** is the DMZ entry point consumers call; the **integration load balancer** sits in the Green Zone and fronts the IS nodes for API Gateway's backend calls. Copy these verbatim rather than deriving them:

| Environment | API access URL (DMZ) | Integration LB (Green Zone) |
|---|---|---|
| DEV | `apicosit.crosig.hr` | `ilsit.crosig.group` |
| TEST | `apicotest.crosig.hr` | `iltest.crosig.group:6561` |
| UAT (lab) | `apicolab.crosig.hr` | `illab.crosig.group` |
| PREPROD | `apicopreprod.crosig.hr` | `ilpreprod.crosig.group` |
| PROD | `apico.crosig.hr` | `il.crosig.group:8561` |

Three things to know:

- **TEST and PROD carry an explicit LB port and the other three do not.** `iltest.crosig.group:6561` and `il.crosig.group:8561` — dropping the port is a silent failure, not a resolvable default. These are also the two clustered environments.
- **The environment segment doesn't track the environment name**, but it *is* consistent across both families: DEV is `sit` (`apicosit` / `ilsit`, never `dev`), UAT is `lab` (matching its *lab* alias, not `uat`), and PROD has no segment at all (`apico` / `il`). Get the segment right once and both hostnames follow.
- **Different domains.** External-facing URLs are `.crosig.hr` (API access, token URL); internal load balancers are `.crosig.group`. Mixing them up produces a name that resolves nowhere.

**The UM NHP port is also per-environment** — DEV listens on `9005`, TEST on `9000`. Neither is a platform default; check the target environment (`netstat -ano | findstr <port>` on the UM host) rather than carrying a value across. See `references/universal-messaging.md` §13.9.

Two things are **shared, not per-environment**: non-prod RH-SSO — `rh-sso-test3` via `authcotest.crosig.hr`, see `references/api-gateway.md` §20.12 — and the logging stack (`crselastic` / `crsintegra`, `references/logging.md`).

Per-environment topology diagrams live on Confluence: [Architecture Overview](https://crosig.atlassian.net/wiki/spaces/ID/pages/6045302793/Architecture+Overview).

## The two install paths

| Single node — DEV, UAT, PREPROD | Clustered — TEST, PROD |
|---|---|
| base install + config migration | base install + config migration |
| **embedded Derby — no DBA schemas, no DBCC, no JDBC pools** | DBA Oracle schemas → DBCC → JDBC pools |
| no Terracotta | Terracotta TSA + IS clustering |
| single UM realm | UM cluster, master/slave |
| API Gateway: 1 pod | API Gateway: 2 pods, Ignite clustering |
| IS Windows service: Automatic | IS Windows service: **Manual** |

External Oracle is needed *only* because clustering requires it. Converting a single-node environment to clustered later means doing the whole database workstream retroactively, against an instance that already holds scheduler and audit state in Derby.

## Rules that always apply

- At install time, select the **non-Embedded** "Integration Server and Microservices Runtime Database Scripts". Choosing only the Embedded variant caused nearly every DBCC problem on TEST.
- **A successful DBCC `migrate` does not prove the schema matches the product.** `latest` means latest *on disk*. Verify the version ceiling — `database.md` §6.5.
- **The API Gateway chart is `kops`, `apigateway/helm`** — one chart, `values-dev.yaml` and `values-test.yaml` (`api-gateway.md` §20.14). Derive a new environment's values from the previous environment's **live Helm release**, not from any file on disk.
- **A values file that has never been re-applied proves nothing.** DEV sat on Helm revision 1 for a year while its committed values file named the wrong container image. `helm get values apigw -n wm-{env}` settles it in one command — `api-gateway.md` §20.2.
- **A `SUCCESS` Elasticsearch snapshot can contain nothing.** DEV produced 43 green snapshots holding zero indices. Always check the shard counts, never the status alone — `api-gateway.md` §20.15.
- **Mutable container tags break Ignite clustering.** Pods on different nodes can get different builds of the same tag — `api-gateway.md` §20.11.
- **Endpoint aliases are environment-specific.** Imported unedited, they point the new environment at the lower environment's backends.
- **Every promotion carries the API, all its Applications and all its Scopes together** — and never ticks `Alias` on the overwrite step. `api-gateway.md` §20.16.
- **Leave JMS and webMethods triggers disabled** until an environment is live — a running trigger consumes real messages the moment it connects.
- **Install UM before** deploying UM-dependent packages (`CCG`, `EEnforcement`) or DB pollers.

## How to answer

- **Read one reference file** — the one the question routes to. Do not preload others "for context".
- **Lead with the answer**, not the background. The fix or the command first; explain only if the reasoning changes what the person should do.
- **Quote commands, paths and error strings verbatim.** These are the parts that must be exact.
- **Don't restate a documented procedure.** If the steps are on Confluence, point at the page and give only the part that answers the question.
- **State environment assumptions rather than guessing.** Most answers differ between clustered and single-node — say which you assumed, or ask if it decides the answer.
- The reference files are written as documentation, so they carry background and history. Extract the operative part; don't relay the narrative.

## Where to look

Section numbers (`§N`) are stable across all files and match the source knowledge base.

| Topic or symptom | File |
|---|---|
| Installing IS, migrating config from the old server, memory, logging config, service account, log archiver | `references/installation.md` (§2, §3, §10, §16) |
| Shared UAT/PREPROD server — ports, heap, service names | `references/installation.md` |
| Terracotta / BigMemory, `tc-config.xml`, `cluster.aware`, cache manager XMLs | `references/clustering.md` (§4–§5) |
| DBCC, Oracle schemas, `ORA-00942`, `ORA-00904`, `ORA-01950`, JDBC pools, functional aliases | `references/database.md` (§6–§7) |
| Schema version ceiling, deploy-time ORA errors after clustering | `references/database.md` §6.5 |
| Universal Messaging install, realms, UM cluster, IS↔UM connection, JMS/JNDI | `references/universal-messaging.md` (§13) |
| API Gateway, OpenShift, Helm, Ignite, routes, promotion and import | `references/api-gateway.md` (§20) |
| API Gateway chart layout, `values-{env}.yaml`, previewing an upgrade | `references/api-gateway.md` §20.14 |
| Elasticsearch snapshots, gateway backup and restore readiness | `references/api-gateway.md` §20.15 |
| Package deployment order, WmDeployer, Jenkinsfile standardization | `references/jenkins-deployment.md` (§14–§15) |
| Filebeat, Kibana, log shipping | `references/logging.md` (§12) |
| evaluate.js / JSONata service | `references/evaluate-jsonata.md` (§11) |
| Installer hangs on "Provisioning products", slow IS shutdown | `references/troubleshooting.md` (§8–§9) |
| Standing up a whole new environment, lessons from TEST | `references/new-environment.md` (§18) |
| Local developer workstation install, Designer, running two versions on one machine | `references/local-development.md` (§21) |
| Business analyst setup — same install, no configuration or package linking | `references/local-development.md` §21.10 |

## Key file locations

`{env}` is DEV / TEST / UAT / PREPROD / PROD; `{realm}` is the UM realm name.

| Purpose | Path |
|---|---|
| IS server log | `C:\SoftwareAG\{env}\111\IntegrationServer\instances\default\logs\server.log` |
| IS clustering properties | `C:\SoftwareAG\{env}\111\IntegrationServer\instances\default\config\server.cnf` |
| IS cache manager configs | `...\config\Caching\SoftwareAG-IS-{Core,ART,WMN}.xml` |
| IS memory / wrapper config | `...\instances\default\configuration\custom_wrapper.conf` |
| Terracotta topology | `C:\SoftwareAG\{env}\111\Terracotta\server\wrapper\conf\tc-config.xml` |
| Terracotta service control / log | `...\wrapper\bin\tsa-service.bat` / `...\wrapper\logs\wrapper-tsa.log` |
| Terracotta licence | `...\common\conf\terracotta-license.key` and `...\Terracotta\terracotta-license.key` |
| DBCC tool | `C:\SoftwareAG\{env}\111\common\db\bin\dbConfiguratorUI.bat` |
| DBCC scripts | `...\common\db\IntegrationServer\{Component}\scripts\{version}\{rdbms}\` |
| UM realm log | `C:\SoftwareAG\{env}\111\UniversalMessaging\server\{realm}\data\nirvana.log` |
| UM Enterprise Manager | `...\UniversalMessaging\java\{realm}\bin\nenterprisemgr` |
| Log archiver | `C:\SoftwareAG\{env}\111\tools\operations\logArchiver\` |
| Filebeat | `C:\Program Files\Elastic\Beats\9.4.4\filebeat\` |
| API Gateway chart | `C:\repo-utils\kops\apigateway\helm` — one chart plus `values-dev.yaml` / `values-test.yaml` |

## Reference documentation

All in the **Integration Development (`ID`)** Confluence space.

| Page | What it covers |
|---|---|
| [Architecture Overview](https://crosig.atlassian.net/wiki/spaces/ID/pages/6045302793/Architecture+Overview) | **Per-environment topology** — the draw.io diagrams, hostnames, ports, API access URLs and load balancers, plus which components are shared rather than per-environment. Start here to find out what an environment actually consists of. |
| [How To Install Integration Server On-Prem](https://crosig.atlassian.net/wiki/spaces/ID/pages/5082349570/How+To+Install+Integration+Server+On-Prem) | IS base install and post-install configuration migration |
| [How to install Universal Messaging On-Prem](https://crosig.atlassian.net/wiki/spaces/ID/pages/6100189192/How+to+install+Universal+Messaging+On-Prem) | UM install. Written for a single-node, migrate-based install — see `references/universal-messaging.md` §13.9 for the values it gets wrong |
| [How to install API Gateway on OpenShift](https://crosig.atlassian.net/wiki/spaces/ID/pages/6103105538/How+to+install+API+Gateway+on+OpenShift) | Eight parts: prerequisites, building values from the previous environment's live Helm release, namespace prep, deploy, clustering, the `rt` endpoint, Administrator password, configuration import |
| [How to use promotion management](https://crosig.atlassian.net/wiki/spaces/ID/pages/6133678081/How+to+use+promotion+management) | Running a promotion between API Gateway environments — asset and dependency selection, target stage, naming convention, and the `Custom` overwrite set. Screenshots per step |
| [How To Install Integration Server Locally (Developer Workstation)](https://crosig.atlassian.net/wiki/spaces/ID/pages/6143574017/How+To+Install+Integration+Server+Locally+Developer+Workstation) | The local per-developer install, click-by-click: products, ports, what to copy from DEV, Designer connections, and junctioning packages to their git clones. The reasoning behind those choices is in `references/local-development.md` §21 |
| [How To Install Integration Server Locally (BA Workstation)](https://crosig.atlassian.net/wiki/spaces/ID/pages/6143737857/How+To+Install+Integration+Server+Locally+BA+Workstation) | The analyst variant — the same install and Designer connections, with the configuration and package-linking sections left out. See `references/local-development.md` §21.10 |
| [IN-3868](https://crosig.atlassian.net/browse/IN-3868) (Jira epic) | webMethods Platform Upgrade 11.1 — one ticket set per environment |

The Confluence pages are the click-by-click procedures with screenshots. This skill carries the diagnostics, the reasoning, and the things that are not obvious from the procedure. Where the two disagree, the skill's `§13.9`-style "superseded values" notes say which to trust.
