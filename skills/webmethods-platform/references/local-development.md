# Local developer installation

Covers **§21** — installing webMethods on a **developer workstation**.

> This is a local per-developer setup, **not an environment we deploy to**. Several choices here are deliberately different from the server installs. Nothing in this file changes how DEV, TEST, UAT, PREPROD or PROD are built — for those, `installation.md` (§2–§3), `database.md` (§6–§7) and `new-environment.md` (§18) remain authoritative and are unaffected.

---

## 21. Local developer installation

Installer: **IBM webMethods Installer** (IBM-branded wizard — `Proxy → Credentials → Release → Directory → Products → Languages → Updates → Configure → Install`).

Click-by-click procedure, published: [How To Install Integration Server Locally (Developer Workstation)](https://crosig.atlassian.net/wiki/spaces/ID/pages/6143574017/How+To+Install+Integration+Server+Locally+Developer+Workstation). Go there for the steps; this file carries the reasoning and the things the procedure does not say — why the local choices differ from a server build, what a workstation cannot do, and the exceptions that bite.

**The one rule that governs local setup: nothing here has a convention, but nothing may collide.** Install directory, Start Menu group and ports are all the developer's choice. If the machine already has a webMethods installation, each of those must differ from it; if it doesn't, the defaults are fine. Do not look for a house standard in this file — there isn't one, deliberately.

### 21.1 How local differs from a server install, and why

| | Server (DEV → PROD) | Local workstation |
|---|---|---|
| Purpose | runtime we deploy to | developer's own sandbox |
| Database scripts | **non-Embedded** "IS and MSR Database Scripts" (§2.2 step 4) | **Embedded** Database Scripts — Derby only |
| Designer | not installed | **installed** — the point of the local setup |
| Universal Messaging | own install (§13) | not installed |
| My webMethods Server | per environment | Diagnostic Tools only |
| Clustering / Terracotta | TEST and PROD | never |
| Directory, group, ports | fixed scheme (§2.2 steps 3, 5) | developer's choice — §21.2, §21.4 |

> **The Embedded database-scripts pick is intentional here.** `database.md` §6 and `SKILL.md` require the *non-Embedded* variant, and that rule stands unchanged **for deployed environments** — selecting Embedded-only was the root cause of nearly every DBCC problem on TEST. A workstation runs Derby and never runs DBCC against Oracle, so Embedded is the correct local choice. Do not carry this local selection onto a server, and do not read this section as a revision of §6.

### 21.2 Install directory and Start Menu group

Neither has a convention. The developer picks both — it is their own machine and nothing downstream depends on either.

| | Only installation | Second (or later) installation |
|---|---|---|
| Install directory | default `C:\SoftwareAG` is fine | must differ — e.g. `C:\SoftwareAG11` |
| Start Menu group | default is fine | must differ — e.g. `SoftwareAG 11` |

`C:\SoftwareAG11` and `SoftwareAG 11` are what one developer used. They are examples, not a standard — any distinct names work, and the two need not match each other.

> Server installs *do* have a scheme — `C:\SoftwareAG\{environment}\{version}` with the group renamed to `Software AG {environment}` (§2.2 step 3). It is not required locally, and local names should not be read back into the server convention.

### 21.3 Products selected

**Three checkboxes are enough: Integration Server, Designer, and Adapters → webMethods Adapter 10.3 for JDBC.** Everything else below is pulled in as a dependency of those three — the full list is a reference for verifying what landed, not a list to tick by hand.

Recorded verbatim so a second developer can reproduce the same workstation.

**Integration Server and runtime**
- Integration Server → Server 11.1
- Infrastructure → Integration Server → Adapter Runtime 11.1, Flat File 10.7, Integration Core 11.1
- IS/MSR Libraries → External RDBMS Support 11.1
- IS/MSR Packages → Monitor 11.1
- Adapters → webMethods Adapter **10.3** for JDBC
- Database Configuration → IS and MSR **Embedded** Database Scripts 11.1 (see §21.1)

**Designer** — Eclipse 4.25, plus:
- Services → Service Development, Local Version Control Integration, Integration Test Suite, SAP Integration 10.1
- Business Processes → Process Development, Process Task Development
- Composite Applications → Task Development, UI Development
- CloudStreams Development
- Shared Plug-ins → BigMemory Max Integration 4.4 SP1, Branding and Naming (+ Common Plugins, DataDirect Drivers), Broker Integration, Database Drivers, Glue 8.0, Installer Integration, JCR Integration, Landscape Asset Repository, License Validator, Metadata, Modeling, Optimize Integration, Universal Messaging Integration

**Infrastructure** — Common C/C++ Runtime; Java Package Core **17.0**; Platform Manager 11.1 with Adapter, IS Server and IS Monitor plug-ins; Shared Platform 11.1 and its bundles (including Deployer and Asset Build Environment); Web Services Stack Core Files; the Libraries branch (Shared, BigMemory Max 4.4 SP1, Broker, Composite Applications Runtime, Database Component Configurator Core, Database Driver, Glue 8.0, Installer, Integration Test Suite, Migration Framework, MWS, Optimize, UM) and Third-Party Libraries (Glassfish, Base Security, Data Modeling, DBMS, Spring, Logging for Java, Multi-Purpose for Java, Swagger, Apache, Ant, Java Service Wrapper, Web Service, Web Servlet, JAXB, XML Parser); License (Agreement, Library for Java, Verifier)

**Also** — Metering → Metering Agent 11.1; My webMethods Server → Diagnostic Tools 11.1; Designer Plug-ins → Composite Applications → My webMethods Server Support 11.1

> **Not every component is 11.1** and the version numbers are not typos: JDBC Adapter **10.3**, Flat File **10.7**, SAP Integration **10.1**, Eclipse **4.25**, Glue **8.0**, BigMemory Max **4.4 SP1**, Java **17.0**.

### 21.4 Instance configuration and ports

**One version installed → keep the default ports.** There is nothing to avoid.

**Multiple webMethods versions on one machine → each install needs its own ports.** They cannot share, and the collision is not reported gracefully.

**There is no port convention — pick any free ports.** The values below are what one install happened to take. They are not a formula, and the next install should not try to continue a pattern (primary and secure went up while the diagnostic went down; that means nothing).

| Port | Default | One install's second-version values |
|---|---|---|
| Primary | `5555` | `5556` |
| Secure | `5543` | `5544` |
| Diagnostic | `9999` | `9998` |

Check a candidate port is free before typing it into the installer:

```powershell
netstat -ano | findstr :5556
```

No output means free. Write down what each install took — nothing in the product will tell you later which version owns which port.

Rest of the Configure step, left at the defaults:

- Instance name: `default`
- **Register Windows service/UNIX daemon for automatic startup**: checked
- Host or IP address: **blank** — uses the machine's default network interface
- **Install packages on this instance now**: checked

> Unlike a clustered server node, there is no reason to set the Windows service to Manual locally (§2.2 step 5) — that instruction exists for cluster members only.

### 21.5 Licence — there is no licence file

**No licence file is needed and none is applied.** There is nothing to obtain before installing and nothing to copy afterwards. A developer who goes looking for one is looking for something that no longer exists.

`Metering → Metering Agent 11.1` and the `License` components (Agreement, Library for Java, Verifier) are part of the selection in §21.3 and install as normal — they are not a licence file to place.

> The only licence keys anywhere in this documentation are **Terracotta's** — `terracotta-license.key`, `clustering.md` §4.1. Those belong to clustered TEST and PROD. A local install has no Terracotta, so searching this skill for "licence" is a false lead locally.

### 21.6 What a local install cannot do

Consequences of the product selection — limitations by design, not faults:

- **No Universal Messaging server.** Only the UM libraries, Designer plug-in and bundles are installed. Packages that use UM — `CCG`, `EEnforcement` — and **DB pollers** will not run locally, and their builds fail without UM (`jenkins-deployment.md` §14).
- **No My webMethods Server**, only Diagnostic Tools. Task and UI Development are installed, so composite applications can be *developed* locally but not deployed locally.
- **No clustering.** No Terracotta, single node, always.
- **No DBCC or Oracle work.** Derby only — §21.1.

### 21.7 Configuration after install

**Everything a workstation needs copied comes from the DEV server** — host `crsintdev2esb1`, instance `default`, under `C:\SoftwareAG\DEV\111`. DEV is single-node and unclustered, which makes it the closest match to a workstation. There is no earlier local install to migrate from, so DEV is the source for every copy step below.

Not part of a local setup: File Adapter access control, memory tuning via `custom_wrapper.conf`, external SFTP server aliases, clustering, the `intsvcdev` service account, Log File Archiver, JSONata on OpenShift, Universal Messaging, Filebeat/Kibana, Jenkins/WmDeployer and the `asw2` VPN port ticket. Server config migration is its own procedure — `installation.md` §3 — and is unaffected by anything here.

#### 21.7.1 Custom jar files

Copy the third-party jars from DEV to the local instance:

```
from  \\crsintdev2esb1  →  C:\SoftwareAG\DEV\111\IntegrationServer\instances\default\lib\jars\custom
to    <local install>\IntegrationServer\instances\default\lib\jars\custom
```

Take the whole `custom` folder contents. No individual jar needs naming: **DEV is the reference** — whatever is in its `custom` folder is what a workstation needs. Copy everything rather than picking; a jar left behind surfaces later as a class-not-found at service run time, not as an install error.

#### 21.7.2 Global variables

A workstation needs **only `globalVariables.cnf`** from DEV's `config` directory, copied unchanged:

```
from  C:\SoftwareAG\DEV\111\IntegrationServer\instances\default\config\globalVariables.cnf
to    <local install>\IntegrationServer\instances\default\config\globalVariables.cnf
```

The rest of that directory stays local. **Do not copy the ACL and user files** — `acls.cnf`, `acllist.cnf`, `aclmap_sm.cnf`, `aclread.cnf`, `aclwrite.cnf`, `users.cnf` — they carry the server's ACLs and user accounts, which a workstation has no use for.

The variables arrive holding DEV's values, and that is intended — a local instance resolving them the way DEV does is the point of copying the file as-is.

#### 21.7.3 JDBC adapters

Two copies from DEV — the `COConfig` package, and the driver jars the adapter loads:

```
from  C:\SoftwareAG\DEV\111\IntegrationServer\instances\default\packages\COConfig
to    <local install>\IntegrationServer\instances\default\packages\COConfig

from  C:\SoftwareAG\DEV\111\IntegrationServer\instances\default\packages\WmJDBCAdapter\code\jars\{mssql,oracle,as400}
to    <local install>\IntegrationServer\instances\default\packages\WmJDBCAdapter\code\jars
```

All three driver folders — `mssql`, `oracle` and `as400` — go across, matching DEV.

#### 21.7.4 Server logging — optional, recommended

Not required for a working local instance, but worth doing: it keeps the log readable and stops it growing unmanageably.

**Administration Dashboard → Logs → Logging configuration → Server Logger → Edit Server Logger →** expand **Integration Server**:

| Setting | Value | Why |
|---|---|---|
| `0088 SOAP` | **error** | SOAP messages carry base64-encoded files — left at default the log fills with payloads |
| `0166 REST` | **error** | same, for REST requests |
| Date and time **Format** | `yyyy-MM-dd HH:mm:ss.SSS z` | default has no milliseconds; without them local traces are hard to order |

**Save Changes** when done.

#### 21.7.5 SSL certificates

Copy the certificate files from DEV:

```
from  C:\SoftwareAG\DEV\111\IntegrationServer\instances\default\config\security\keystore
to    <local install>\IntegrationServer\instances\default\config\security\keystore
```

Copying the files is not enough — the certificates then have to be **added by hand in the UI**: **Security → Keystore**, one entry per certificate. An instance with the files present but nothing registered behaves as though it has no certificates at all.

#### 21.7.6 Extended settings

**Settings → Extended**. Set these four keys; **a restart is required** before any of them take effect.

| Key | Local value | Product default |
|---|---|---|
| `watt.server.url.alias.partialMatching` | `true` | `false` |
| `watt.security.ssl.client.ignoreEmptyAuthoritiesList` | `true` | `false` |
| `watt.server.date.suppressPatternError` | `true` | `false` |
| `watt.server.json.encodeDateAs` | `yyyy-MM-dd'T'HH:mm:ss.SSSXXX` | — |

Two keys the servers set are deliberately left at default locally:

- **`watt.server.threadPool`** — servers raise it to 400 per node on TEST and PROD, 300 on PREPROD, for production load a workstation never sees.
- **`watt.server.serverlogRotateSize`** — servers cap it at `350MB`. A developer never generates enough log volume for rotation size to matter.

Do not copy either value across from a server.

#### 21.7.7 Activating the JDBC adapters

**Every JDBC adapter comes up suspended** on a fresh instance — that is the default state, not a fault, and no adapter will connect until it is activated by hand.

For each adapter connection:

1. Enter its **password** and **save changes** — the password does not come across with the copied configuration, so this is per connection, every time.
2. Then click **Enable** on the connection.

The order matters: enabling before the password is saved leaves the connection failing to connect.

**The credentials are DEV's.** A local instance connects to the **DEV databases**, so the passwords to enter are the DEV ones — available in both **KeePass** and **Bitwarden**.

> That also means local work runs against real DEV data. A service run from a workstation reads and writes the same databases DEV does; it is not an isolated sandbox below the database line.

### 21.8 Designer

Do this **before linking any packages** (§21.9). Designer has to be talking to the local instance first.

All of it lives in one place: **Window → Preferences → webMethods → Integration Servers**.

#### 21.8.1 The local Integration Server

Designer ships with an Integration Server entry named **`Default`**, pointing at `localhost:5555` with no credentials — so out of the box it shows a connection error rather than connecting.

**Window → Preferences → webMethods → Integration Servers →** select **`Default`** → **Edit**:

| Field | Value |
|---|---|
| Name | `Default` |
| Host | `localhost` |
| Port | the instance's **primary port** — `5555` unless it was changed at install (§21.4) |
| User | `Administrator` |
| Password | the Administrator password the developer set during installation |
| Connect immediately | checked |
| Connect at startup | checked |
| Secure connection | unchecked — this is the primary HTTP port, not the secure one |

Two fields do the work: **the port, if the install used a non-default one, and the password.** The shipped entry has neither right, and the port is the one that silently mismatches when a workstation runs more than one version.

The Administrator password is **chosen by the developer during installation** — it is not a shared or default value, and nothing but that developer's own record of it will do.

Click **Verify Server** before **OK** — it confirms the connection while the dialog is still open, instead of leaving a broken entry to discover later. Then **Apply and Close**.

#### 21.8.2 Remote environment connections

On the same preferences page, **Add** an entry per environment, so every server is reachable from one Designer without reconfiguring:

| Name | Host | Port | Version |
|---|---|---|---|
| `Default` | `localhost` | the local primary port (§21.8.1) | 11.1 |
| `dev` | `crsintdev2esb1` | `5555` | 11.1 |
| `test1` | `crsintdev2esb3` | `5555` | 11.1 |
| `test2` | `crsintdev2esb4` | `5555` | 11.1 |
| `lab` | `crsintdevpl1` | `5555` | **10.11 — old servers** |
| `preprod1` | `crsintdevesb1` | `27555` | **10.11 — old servers** |
| `preprod2` | `crsintdevesb2` | `27555` | **10.11 — old servers** |
| `prod1` | `crsintesb1` | `28555` | **10.11 — old servers** |
| `prod2` | `crsintesb2` | `28555` | **10.11 — old servers** |

> **Only DEV and TEST are on 11.1.** `lab`, `preprod1/2` and `prod1/2` still point at the **pre-upgrade 10.11 environments** on the old servers. **This list is a snapshot and goes stale as the upgrade proceeds** — when an environment moves to 11.1 it lands on a new server, so its host and port here have to be replaced. A developer working through one of those connections is working on 10.11, not on the platform the rest of this documentation describes.

Notes that matter when typing these in:

- **The odd ports belong to the old environments.** `27555` for preprod and `28555` for prod are 10.11 server values, not a scheme to extend; the 11.1 environments are all on `5555`. Copy them as they are.
- **`Default` keeps the *Default* radio button.** It decides which server new work targets, and it should stay on the local instance, not on an environment.
- **Clustered environments appear as two entries each** — `test1`/`test2` and `prod1`/`prod2` — one per node, because Designer connects to a node, not to a load balancer.

> These are live servers, `prod1` and `prod2` included. A change made through one of these connections happens on that environment immediately — there is nothing local about it.

### 21.9 Packages — junctions into their git working copies

**Every package is its own git repository, and local packages are not copies — they are directory junctions into the developer's clone.** That is what makes local development work: an edit made in Designer lands directly in the working copy, so git sees it immediately and it can be committed and pushed from the repo. Nothing is exported, copied back, or kept in sync by hand.

This replaces the server-side package flow entirely — no `replicate\inbound`, no *Install Inbound Release*.

#### Cloning the package repositories

Linking needs a **full clone with a working tree** of every package repository. Do this once, before the first link. Already have clones? Steps 4–5 bring them up to date.

**1. Pick the clone root.** There is no default path — `C:\repo` in the examples is one developer's layout and nothing depends on it. Use **the same folder `branch-compare` uses for the `webmethods` estate**, so one set of clones serves both skills:

- if `%USERPROFILE%\.branch-compare.json` already has `roots.webmethods`, use that folder;
- otherwise choose one and record it there, so `branch-compare` picks it up later without asking:

```json
{ "roots": { "webmethods": "D:\\work\\il" } }
```

Keep any other estates already in `roots` (e.g. `spring`) — add the key, don't replace the file.

**2. Check SSH access.** Clone over SSH. The developer's SSH key must be added to their Bitbucket account, and this must answer with their username:

```
ssh -T git@bitbucket.org
```

Use the plain `git@bitbucket.org:crosig/<repo>.git` form — never a personal `<user>@bitbucket.org` URL copied from someone else.

**3. Get the repository list.** The list is **`branch-compare/assets/estates/webmethods.json`** — the single source, maintained from the Bitbucket project **int-webmethods-project (INWP)**. Do not copy it anywhere else.

- **`repos`** — clone these.
- **`skipped`** — never clone. Dead or non-package repositories that only remain in INWP.
- **`barcode`** — never clone, even if it appears under `repos`; it is not linked either (see the exception table below).

**4. Clone what is missing.** For every repository on the list that has no folder in the clone root:

```
cd <clone root>
git clone git@bitbucket.org:crosig/<repo>.git
cd <repo>
git checkout dev
```

**Check out `dev`.** Designer edits land directly in the working copy, so the working copy must be on `dev`. A repository without `origin/dev` stays on its default branch — note it and raise it with the team; do not leave it silently.

**Full clone, not `-Thin`.** `branch-compare -Thin` clones metadata only (`--no-checkout`), which leaves no `src\<package>` folders and therefore nothing to link. A thin root must be re-cloned in full before linking. The whole set is roughly 2 GB.

**5. Fetch what is already there.** For every repository that already has a folder:

```
git -C <clone root>\<repo> fetch origin --prune
```

Fetch only — leave the checked-out branch and any local changes alone.

**6. Repair clones killed by a timeout.** A `git clone` interrupted by a timeout can leave a `.git` that looks valid but has no refs and no fetch refspec — `git branch -a` shows nothing. Repair it in place instead of re-cloning:

```
git config remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
git fetch origin --prune
git checkout dev
```

> **Claude can do the cloning — there is no need to run ~90 clones by hand.** Give it the clone root, or let it read `roots.webmethods` from `%USERPROFILE%\.branch-compare.json`. It reads the list from `webmethods.json`, leaves out `skipped` and `barcode`, clones what is missing and checks out `dev`, fetches what is already there, repairs timed-out clones, and reports four lists: cloned, fetched, repaired, and repositories with no `dev` branch. It then continues with the linking below.

#### Linking the packages

**How many to link is the developer's call.** Only the packages you actually work on need linking. The recommendation is to **link everything during setup anyway** — it is one pass through the list now instead of stopping to link a package each time work touches a new one later.

> **Claude can do the linking — there is no need to type ~100 `mklink` commands by hand.** Give it the clone root and the install path; it enumerates the repositories, picks the version per the rules below, creates every junction and verifies the result. Junctions need no elevation (see the `/j` note), which is why this runs in an ordinary session. Ask it to confirm two things per link: that `manifest.v3` is visible through the junction — a link to the wrong folder level resolves but exposes no package — and that `git rev-parse --show-toplevel` from inside the link returns the repository, which is what proves a Designer edit lands in the working copy.

Use `cmd` — `mklink` is a `cmd` built-in and does not exist in PowerShell. Change into the instance's `packages` directory and create one **junction** per package:

```
cd C:\SoftwareAG11\IntegrationServer\instances\default\packages

mklink /j COAccountingV003 C:\repo\accounting-il\v3\src\COAccountingV003
```

Adjust the first path to wherever that developer installed (§21.2).

> **Use `/j`, not `/d`.** `/j` creates a junction and **needs no Administrator rights**; `/d` creates a symbolic link and fails without them. For a link between two local paths the two behave identically — Integration Server loads the package, Designer edits reach the working copy, and git treats it as an ordinary directory either way. `/d`'s only advantages are relative and network targets, neither of which applies here. `dir /al` shows a correct link as `<JUNCTION>` with its target in brackets.

The link target follows the same shape for every package:

```
<clone root>\<repository>\<latest version>\src\<package folder>
```

- the **latest version** folder in the repository — `v3` above
- then **`src`**
- then the **package folder inside `src`**, under whatever name it carries there — which is also the name to give the link, so Integration Server sees the package under its real name

#### Exceptions — where "latest version" is the wrong rule

Six repositories do not follow it. Link exactly these versions:

| Repository | Link | Ignore |
|---|---|---|
| utils | **all three versions** — `COUtils`, `COUtilsV2`, `COUtilsV003` | — |
| canonical data models | **all three versions** — `COCDM`, `COCDMV002`, `COCDMV003` | — |
| inscope | **v3 only** | `v4` and `v21` — deliberately not linked |
| payment | **v3 and v4** | — |
| vehicle | **v3 and v4** | — |
| barcode | **not linked at all** | the whole repository |

Where several versions are linked, each one is a separate `mklink` against its own version folder. The version is part of the package folder name inside `src`, so the links do not collide.

`inscope` is the one to be careful with: `v4` and `v21` exist in the repository and look like the obvious choice. Linking them is wrong — take `v3`.

#### Making linked packages visible to Integration Server

A newly linked package is not picked up on its own. Either route works:

| | How | Best for |
|---|---|---|
| Restart IS | restart the instance; linked packages are picked up on startup | **several packages at once** — one restart covers all of them |
| Activate in the UI | **Packages → Management → Activate Inactive Packages**, then activate each package | **a single package** — quicker than a restart |

Both end in the same place, so it is only a question of how many links were just made. A link that is correct but whose package has not been activated looks exactly like a link that did not work.

### 21.10 Business analysts — the short version

A business analyst needs Designer to **see what is on the remote servers**. They get the same install as a developer, including a working local Integration Server — they simply never work in it.

**Install exactly as in §21.2–§21.6, then set up Designer as in §21.8.** Two sections drop out:

| §21 section | Analyst setup |
|---|---|
| §21.7 configuration | **skipped** — nothing is copied from DEV. It exists so local packages can run, and no packages will run here |
| §21.9 cloning | **skipped** — no repositories on disk |
| §21.9 package junctions | **skipped** — nothing to link |

Everything else is unchanged, `Administrator` credentials included.

Click-by-click procedure, published: [How To Install Integration Server Locally (BA Workstation)](https://crosig.atlassian.net/wiki/spaces/ID/pages/6143737857/How+To+Install+Integration+Server+Locally+BA+Workstation) — the developer page with the configuration and package sections removed.
