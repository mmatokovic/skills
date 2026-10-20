# Database — DBCC and JDBC pools

Covers **§6–§7** — Oracle schemas, the Database Component Configurator, and functional aliases.

> **TEST and PROD only.** Single-node environments (DEV, UAT, PREPROD) stay on embedded Derby, need no DBA-provisioned schemas, and skip DBCC and pool configuration completely. External Oracle is required only because clustering demands it (§5.4).

---

## 6. Database Component Configuration (DBCC)

### 6.1 Root cause of most DBCC problems: wrong install-time selection

See §2.2 step 4 — selecting only the **"Embedded Database Scripts"** package (instead of also/instead selecting the full **"Database Scripts"** package) is the install-time mistake that caused nearly every issue below. For future installs, check both, or specifically the non-Embedded one, to get complete DDL content on the first try.

Symptoms observed from having only the Embedded package installed:
- `ComponentTracker`, `DistributedLocking` — worked fine (their Oracle scripts happen to ship in the base GA package regardless).
- `CrossReference` — had a `derby`-only folder for its one version (`8.2.2`), no `oracle` subfolder at all.
- `ISInternal` — had all 53 historical version/migration folders present, but the base `9.0.1` folder was missing its `oracle` subfolder (and no other folder had one either).
- `ISCoreAudit` — folder **completely absent** from `common\db\IntegrationServer\`, not just missing an `oracle` subfolder. The DBCC UI didn't even list it as a selectable component because its folder didn't exist on disk at all.

A separate transient issue (`SSLHandshakeException` on the "Install fixes from Empower" step) was initially suspected as the cause, but was ruled out: a fully successful, error-free install (fixes applied cleanly) **still** had all the same missing DBCC content — this is an install-time product-selection issue, not a fix-installation issue.

**Workaround used** (when re-running the installer isn't immediately practical): copy the missing folders from another existing install at a compatible (often much older) schema version — DBCC's script folders are versioned by **DB schema version**, not IS product version, so e.g. `CrossReference`'s `8.2.2` folder or `ISInternal`'s `9.0.1` baseline are identical across IS releases. When copying `ISInternal`, copy the *entire* folder tree (all migration-range subfolders), not just the base version folder — see §6.4 for why.

> ⚠️ **This workaround has a trap that cost weeks on TEST — read §6.5 before using it.** Copying from an older donor install caps your schema at *that install's* highest version, silently and with no error. The right fix is to harvest scripts from a **same-version** install (§6.5), not from whatever copy happens to be available.

### 6.2 Running DBCC

- **Run only once, on one node**, against each new Oracle schema — it's creating tables in the shared Oracle schema, not anything local to a node.
- Location: `C:\SoftwareAG\{env}\111\common\db\bin\dbConfiguratorUI.bat`
- Use **Component** mode (not Product) to select granular items:
  - For the schema behind the `ISInternal`/`Xref` pool, select: **ComponentTracker**, **CrossReference**, **DistributedLocking**, **ISInternal**.
  - For the schema behind the `ISCoreAudit` pool, select: **ISCoreAudit**.
  - Multi-select with **Ctrl+click** on each item individually — Shift+click range-select was observed to silently fail (only the last-clicked item actually ran).
- Enter the JDBC connection details and the new DBA-provided credentials for each schema — **make sure custom tablespace names are correct** (see below) → Execute.
- Confirm the per-table success report, then restart IS on both nodes.

### 6.3 Tablespace naming & credentials gotchas

- Leave **"Create tablespaces and database user"** unchecked if the DBA already created the user/schema — that checkbox is for DBCC provisioning the schema itself and needs DBA-level admin credentials.
- **Check "Use custom tablespace names"** and enter the *actual* tablespace name(s) the DBA granted quota on. DBCC's hardcoded default (`WEBMDATA`) will not match a custom-named tablespace (e.g. `WEBMDATA_NEW`), producing:
  ```
  ORA-01950: no privileges on tablespace 'WEBMDATA'
  ```
  Find the real tablespace name via `SELECT * FROM USER_TS_QUOTAS;` (run while connected as that user) if not already known from the DBA's provisioning script.
- A component failing with `OS Authentication was requested, but is not supported by this Oracle Server` usually means that specific component needs elevated/administrator DB credentials that weren't supplied — confirm the component is actually required before chasing DBA-level credentials for it (e.g. the `Storage` component was deferred as non-essential to clustering).

### 6.4 The `migrate` action — critical for a schema that isn't at "latest"

If a component's table already exists but was created from only a baseline folder (e.g. `ISInternal` created from just `9.0.1`), the running IS server will throw column-level errors once it tries to use features added by later schema migrations:

```
ORA-00904: "LAST_UPDATED": invalid identifier          <- Scheduler
ORA-00904: "SCOPE_URL_TEMPLATES": invalid identifier    <- OAuth
ORA-00942: table or view does not exist                 <- Alert/Notifier tables (also part of ISInternal's later migrations)
```

Fix: in DBCC, set **Type: `migrate`** (not `create`) for that component, Version: `latest`. This walks the full migration chain from whatever version the table is currently at, up through every intervening fix-level script, to the latest available on disk. Confirm success via the server.log line:
```
[SCHED] level: v10.11.fix3
```
(or whatever level was reached) and the absence of further `ORA-00904`/`ORA-00942` errors on restart.

> Note: fixing `ISInternal` this way also resolved the Alert-framework and OAuth errors simultaneously — those tables/columns are part of `ISInternal`'s own schema evolution, not a separate DBCC component.

> ⚠️ **`latest` means latest *on disk*, not latest for your IS version.** The `[SCHED] level: v10.11.fix3` line above is a real example: the migrate genuinely succeeded, but 10.11.fix3 was simply the top of a copied script tree on an 11.1 install. A successful `migrate`/`latest` is **not** evidence the schema matches the product. See §6.5.

### 6.5 The version-ceiling trap — a copied script tree caps your schema at the donor's version

*Discovered on TEST in August 2026, after clustering (§5) went live. Resolved.*

#### Symptom

Every Jenkins package deployment produced **pairs** of `ORA-00942: table or view does not exist` stack traces in `server.log` — one for a lock, one for the matching unlock:

```
wm.server.access.aclAssign            <- Deployer assigning ACLs to the package's nodes
  NSLockManager.lockNode
    RepoLockManager.lock
      KVStoreDBISInternal.put         <- persist the namespace lock into ISInternal
        ORA-00942: table or view does not exist
```

Very easy to dismiss as noise, for three reasons:
- the package install itself still reported `[SUCCESS] ispackage.<name>: ... installed and activated`
- the lines are logged as `[ISS.0095.0042I]`, an **Informational** audit-truncation notice (*"The ERRSTACKTRACE field in a WMERROR audit record was truncated"*) rather than an error record
- WmDeployer calls `aclAssign` once per namespace node, so the sheer volume reads as log spam rather than one fault

#### Why it only appeared after clustering

`server.cnf` carries `watt.server.ns.lockingMode=full`. Combined with `watt.server.cluster.aware=true`, namespace locks are **persisted to the ISInternal database** so both nodes can see them, instead of being held in memory. DEV is single-node and not cluster-aware, so this code path never executes there. The defect existed from install day but stayed invisible until §5 landed.

#### Root cause

The §6.1 workaround — copying script folders from another install — carries a constraint that isn't obvious: **`migrate` / `latest` only walks as far as the highest version folder present on disk.** "Latest" means latest *available*, not latest *for your product*. Copy a tree from a 10.11-era install onto an 11.1 server and the schema silently stops at 10.11 — no error, no warning, and DBCC reports success.

Ceilings actually found on TEST:

| Component | Was at | 11.1 GA provides | Notes |
|---|---|---|---|
| `ISInternal` | 10.11.fix3 | 11.1 | cause of the deploy errors |
| `ISCoreAudit` | 10.5.fix4 | 10.5.fix5 | donor was an even older install |
| `DistributedLocking` | 7.1 | 10.11.fix1 | cluster infrastructure |
| `CrossReference` | 8.2.2 | 8.2.2 | genuinely complete — single-version component |
| `DocumentHistory` | **absent entirely** | present | never created; backs exactly-once processing |
| `ComponentTracker` | complete | — | lives under `common\db\DCC\`, *not* `common\db\IntegrationServer\` |

The two donors differed (10.11-era for ISInternal, 10.5-era for ISCoreAudit), so **ceilings are per-component, not uniform** — survey every component rather than extrapolating from one.

#### Diagnosing it

All components at once — the fastest way to spot a ceiling:

```powershell
Get-ChildItem "C:\SoftwareAG\{env}\111\common\db\IntegrationServer" -Directory | ForEach-Object { $v=@(Get-ChildItem (Join-Path $_.FullName 'scripts') -Directory -EA SilentlyContinue); $o=@($v | Where-Object { Test-Path (Join-Path $_.FullName 'oracle') }); [PSCustomObject]@{ Component=$_.Name; Versions=$v.Count; WithOracle=$o.Count } } | Format-Table -AutoSize
```

Then per component, to find the actual top version:

```powershell
Get-ChildItem "C:\SoftwareAG\{env}\111\common\db\IntegrationServer\{Component}\scripts" -Directory | ForEach-Object { [PSCustomObject]@{ Version = $_.Name; Oracle = (Test-Path (Join-Path $_.FullName 'oracle')); Sql = @(Get-ChildItem (Join-Path $_.FullName 'oracle') -Filter *.sql -ErrorAction SilentlyContinue).Count } } | Format-Table -AutoSize
```

Three traps when reading the output:

- **Don't sort version folders lexicographically and take the tail.** `Sort-Object Name | Select-Object -Last 5` returns the `9.x` folders, because `"1" < "9"` sorts every `10.x`/`11.x` entry *first*. List all of them.
- **A folder existing doesn't mean it has content.** An Embedded-only install has the full 11.1 folder skeleton with `derby` subfolders and no `oracle` — which is why the survey checks for the `oracle` subfolder, not just the version folder.
- **Terminal version folders legitimately have no `oracle` subfolder** (e.g. `10.1.fix4`, `9.5.1.fix2`), as do alternate paths the chain routes around. A couple of `False` rows is normal; what matters is the highest *range* folder with content.

> **Re-running `migrate` before fixing the disk content is a no-op.** DBCC compares the schema against what's on disk, finds them equal, reports success, and changes nothing.

#### The fix — harvest scripts from a throwaway same-version install

1. **Fresh** install to a disposable location, e.g. `C:\SoftwareAG\harvest`. Never use "modify existing install" (§8.1). Select the **Database Configuration** branch, ensuring the non-Embedded **"Integration Server and Microservices Runtime Database Scripts"**. Taking the whole branch is fine and safer than picking wrong.
2. **Verify the harvest has Oracle content at the versions you need before copying anything.** If it's all `Oracle = False`, the Embedded package got selected again.
3. Back up TEST's tree, then merge-copy:
   ```powershell
   Copy-Item "C:\SoftwareAG\{env}\111\common\db\IntegrationServer" "C:\Temp\db-scripts-backup" -Recurse -Force; Copy-Item "C:\SoftwareAG\harvest\common\db\IntegrationServer\*" "C:\SoftwareAG\{env}\111\common\db\IntegrationServer" -Recurse -Force
   ```
   `-Force` overwrites matching files and adds new folders; nothing is deleted. Copy the **whole subtree** rather than named folders — you can't reliably enumerate what's missing.
4. Do **not** copy the other product folders a whole-branch selection brings along (`Monitor`, `MywebMethodsServer`, `Optimize`, `ProcessEngine`), nor `bin`/`lib`/`DCC`, which are already correct.
5. Copy to **both nodes**. Divergent script trees between cluster nodes are exactly what let this hide.
6. Run DBCC **once**, from one node, Component mode (§6.2–6.3 still apply — custom tablespace names, Ctrl+click multi-select):
   - against the **ISInternal** schema: `ISInternal` migrate/latest, `DistributedLocking` migrate/latest, `DocumentHistory` create/latest
   - against the **ISCoreAudit** schema: `ISCoreAudit` migrate/latest
7. Restart both nodes, then delete the harvest install.

#### Outcome

**Confirmed fixed** — Jenkins package deployments now complete with no `ORA-00942` in `server.log`.

> **One rung deliberately left short.** The harvest install was 11.1 GA, which reaches schema version `11.1`. A Core Fix13 install additionally carries a `11.1-11.1.fix1` script folder, so a fully-matched schema would be at `11.1.fix1`. Closing that gap only requires applying the fix to the harvest install before copying — the harvest carries its own `SAGUpdateManager`, so no external help is needed. Judged not an issue on TEST and skipped. **Worth doing properly on PREPROD/PROD**, and worth knowing about if an obscure schema error shows up on TEST later.

---


## 7. JDBC Pool / Functional Alias Configuration

Naming convention (per the official runbook):

| Functional Alias | Pool Alias (`{env}_...`) | Database User |
|---|---|---|
| `ISInternal`, `Xref` | `{env}_Internal` | `WM_111_IS_{env}_ISINTERNAL` |
| `ISCoreAudit` | `{env}_Audit` | `WM_111_IS_{env}_ISCOREAUDIT` |
| `ISDashboardStats` | *(leave as)* Embedded Database Pool | n/a — internal dashboard stats, not part of the clustering/HA schema set |

Steps, identical on **both nodes** (pool/alias mapping is per-instance, not shared like the DBCC step):

1. **Settings → JDBC Pools → Pools** — create a Pool Alias Definition, copying all configuration from the old environment, only mapping to the new DB users above.
2. **Settings → JDBC Pools → Functional Aliases** — map `ISInternal` and `Xref` to `{env}_Internal`; map `ISCoreAudit` to `{env}_Audit`.
3. Restart IS on both nodes.
4. Recheck **Settings → Clustering** — should now list both nodes as cluster hosts.

The original blocking error confirming this requirement is quoted in §5.4.

