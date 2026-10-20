# Building a new environment

Covers **§18** — the checklist for standing up a webMethods environment, plus the findings most likely to bite on the next one.

Work out first whether the environment is **single node** or **clustered** (see the matrix in `SKILL.md`) — it decides whether roughly half of this documentation applies to you.

---

## Order of work

1. **Base install** (`installation.md` §2) — during Products selection, under Database Configuration, check **"Integration Server and Microservices Runtime Database Scripts"**, the **non-Embedded** one. This single choice avoids most of the pain in `database.md` §6.
2. For a clustered environment, also select **BigMemory Max**, **Terracotta Support** and **External RDBMS Support**.
3. Set the IS Windows service startup type — **Manual** if clustered, Automatic if single node.
4. **Complete the full configuration migration** (`installation.md` §3) before anything else: custom jars, ACLs and users, SSL certificates, SFTP configs, extended settings, util packages, JDBC adapter activation.
5. **Clustered only** — request Oracle schemas from the DBA (`clustering.md` §5.5), get the real tablespace names *before* running DBCC, then Terracotta (`clustering.md` §4), IS clustering (§5), DBCC (`database.md` §6), and JDBC pools (§7).
6. **Universal Messaging** (`universal-messaging.md`) — before any UM-dependent package or DB poller.
7. **API Gateway** (`api-gateway.md`) and **evaluate.js** (`evaluate-jsonata.md`) on OpenShift.
8. **Kibana logging** (`logging.md`).
9. **Package deployment and testing** (`jenkins-deployment.md`).
10. Create the environment's own ticket set under the epic, using TEST's as the template.
11. **Update the Designer connection list** — `local-development.md` §21.8.2. Until someone changes it, every developer's Designer still points that environment's entry at its old 10.11 host and port, and connects there without complaint.

---

## Findings worth carrying forward

All of these were discovered the hard way on TEST. Each cost real time and none is discoverable from the system until it fails.

**The DBCC version ceiling** (`database.md` §6.5) — the single largest time sink of the TEST build. `migrate` / `latest` walks only as far as the highest version folder present *on disk*, reports success, and leaves the schema silently behind the product. Copying script folders from an older install caps you at that install's version. Invisible until a feature that needs a newer table runs — which, for the repo-lock table, meant the day clustering went live.

**API Gateway mutable image tags** (`api-gateway.md` §20.11) — `11.1` is not immutable. Worker nodes cached different builds, the two pods came up on different Ignite versions and refused to cluster, each forming its own single-node grid. `pullPolicy: Always` is the stopgap; pin an immutable tag before PROD.

**The API Gateway runtime listener** (`api-gateway.md` §20.10) — the `rt` route needs both an OpenShift route *and* an `HTTPListener@5556` created by hand in the admin UI. No import brings the listener. A route without it returns 503, which reads like a deployment fault and isn't.

**Derive an API Gateway environment's values from the previous environment's live Helm release, never from a committed file** (`api-gateway.md` §20.2). The chart is `kops`, `apigateway/helm` — one chart with a `values-{env}.yaml` per environment. A committed values file that nothing has re-applied can be wrong for years without anyone noticing; `helm get values` is the only source of truth.

**Endpoint aliases and JMS triggers are environment-specific** — an imported-but-unedited alias points the new environment straight at the lower environment's backends, and a running trigger consumes real messages the moment it connects. Both are silent.

**Installer modify-flow hangs** (`troubleshooting.md` §8.1) — adding a product to an existing install hung three times on TEST. A fresh install with the right selections always completed. Choose correctly at install time rather than planning to add later.
