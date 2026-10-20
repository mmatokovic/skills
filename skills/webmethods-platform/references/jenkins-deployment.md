# Package deployment and Jenkins / WmDeployer

Covers **§14–§15** — deployment ordering, WmDeployer setup, and the Jenkinsfile standardization.

---

## 14. Package Deployment & Testing (via Jenkins/WmDeployer)

Once WmDeployer is set up for the environment (§15.1), deploy and test in this order — **the ordering matters**, since UM must be installed before certain packages/pollers or their Jenkins builds/functionality will fail:

- **Packages** — all webMethods packages should be deployed to Integration Servers via Jenkins build.
  > **Do not deploy packages that use Universal Messaging** (e.g. `CCG`, `EEnforcement`) **if UM is not installed yet** — their builds will fail.
- **Schedulers** — all schedulers present on the old (10.11) environment should be re-added on 11.1.
- **File pollers** — should be added automatically during the Jenkins build; verify all expected ones are actually present, and add manually if any are missing.
- **DB pollers** — must be set up **after** Universal Messaging is installed, otherwise they will not work.
- **Testing** — use the team's shared Postman collections to test basic functionality and the different service types, confirming no major regressions.

> **Status:** TEST is complete — UM installed on both nodes (IN-4043, IN-4044) and packages deployed and tested (IN-4041), all `Implemented` as of 2026-08-07. The ordering constraint above is therefore satisfied history for TEST, but it still binds for **UAT, PREPROD and PROD**: install UM before deploying UM-dependent packages or setting up DB pollers.

---


## 15. Jenkins / WmDeployer Configuration

### 15.1 Configure WmDeployer for the new environment

- In the [`wm-ci-assets`](https://bitbucket.org/crosig/wm-ci-assets) repository, edit the `{env}.properties` file with correct IS properties.
- Jenkins IS [WmDeployer](http://crsintdevesb1:15555/WmAdmin/#/integration/dashboard/overview) → Solutions → Deployer → Servers → IS & TN → **Add Remote Server Alias**.
- Select the new instances and click **Install**.

### 15.2 Configure Jenkins jobs for all packages

- Configure branch discovery.
- Build.

### 15.3 One-time setup — configuring a *new* Deployer version on Jenkins

> Already done for the current setup; only needed again when preparing for the next Deployer version (e.g. Deployer 12.1).

- Install the [`wm-ci-assets`](https://bitbucket.org/crosig/wm-ci-assets) repo on the Jenkins Windows server at `C:/SoftwareAG/utils/`.
- **Manage Jenkins → System → Global properties → Environment variables:**

  | Name | Value |
  |---|---|
  | `WM_CI_HOME` | `C:\SoftwareAG\utils\wm-ci-assets` |
  | `WM_HOME` | `C:\SoftwareAG\{env}\{version}` |

- **Global Tool Configuration → Ant → Ant installations:**

  | Name | Value |
  |---|---|
  | `ANT HOME` | `C:\SoftwareAG\{env}\{version}\common\lib\ant` |

- **Global Tool Configuration → JDK → JDK installations:**

  | Name | Value |
  |---|---|
  | `jdkWM` | `${WM_HOME}\jvm\jvm` |

---

### 15.4 Jenkinsfile standardization across all INWP repos (IN-4041)

Ahead of the 11.1 TEST rollout, every package repo's `Jenkinsfile` on its `test` branch was standardized against a single reference: **`insured-object-api-il/Jenkinsfile`**.

**What the reference changes.** Most repos had a flat Deploy stage; the reference wraps it in a named dynamic stage so the Jenkins UI shows which environment was deployed to:
```groovy
stage('Deploy') {
    steps {
        script {
            stage("Deploy to ${env.BRANCH_NAME}") {
                bat "...ant ... deploy"
            }
        }
    }
}
```
The ant command and everything it deploys are unchanged — this is a build-visibility improvement, not a behavioural one.

**The one genuinely risky part: the `VERSION` parameter.** The Jenkinsfile declares:
```groovy
choice(name: 'VERSION', choices: ['v3', 'v2', 'v1', 'v4'])
```
In Jenkins, **the first choice is the default**, and it feeds `-DversionNumber=${params.VERSION}` into the ant build/deploy. So the choices *order* is functionally significant per repo — copying one repo's Jenkinsfile verbatim to another silently changes which package version a parameterless build deploys.

**The rule adopted:** the default (first choice) must be **the newest version that actually exists in that repo**, determined from its top-level `vN` folders — with one deliberate exception, **`inscope-api-il`, pinned to `v3`** even though a `v21` folder exists.

Folder-to-package convention: folder `v3` contains package `...V003` (e.g. `accounting-il/v3/src/COAccountingV003`).

**Outcome of the sweep (July 2026):** INWP contained **110 repos**; 23 were excluded from scope (see §15.5), leaving **91 processed** — 80 pushed with a new commit, 7 already correct, 3 skipped for having no `test` branch, 1 excluded as an anomaly. Commit message used verbatim, with nothing appended:
```
[IN-4041] edit Jenkinsfile
```

**21 repos ended up with a non-`v3` default**, because their newest version isn't v3:
- **v1** — `arkod-api-il`, `claim-standard-api-il`, `contact-standard-api-il`, `light-contact-api-il`, `policy-standard-api-il`
- **v2** — `actuals-il`, `actuary-il`, `audatex-api-il`, `bisnode-il`, `contract-api-il`, `customer-synchronization-api-il`, `eenforcement-il`, `exchange-rates-api-il`, `huo-il`, `jenz-api-il`, `legal-entities-il`, `loyalty-api-il`, `treasury-api-il`
- **v4** — `payment-api-il`, `tasks-api-il`, `vehicle-api-il`

Three of these were **corrections to a pre-existing wrong default**, worth knowing about because a parameterless build previously deployed the wrong version:
| Repo | Was | Now | Why |
|---|---|---|---|
| `actuary-il` | v3 | **v2** | `v3` didn't exist in the repo at all |
| `payment-api-il` | v3 | **v4** | repo has `v2,v3,v4` |
| `vehicle-api-il` | v3 | **v4** | repo has `v1,v2,v3,v4` |

**Gotchas worth remembering if this is repeated for another environment:**

- **Don't compare Jenkinsfiles by extracting them with a shell redirect.** `git show origin/test:Jenkinsfile > file.txt` in PowerShell adds a UTF-8 BOM, making every file look like it differs on line 1. Compare blob SHAs (`git rev-parse origin/test:Jenkinsfile`) or use in-memory string comparison instead.
- **A blob SHA mismatch doesn't always mean the content differs.** Repos with line-ending normalization (`.gitattributes` / `core.autocrlf`) store an LF blob while checking out CRLF, so the stored blob differs from a CRLF reference file even when the working-tree content is identical. Compare working-tree bytes for the real answer.
- **The reference file is CRLF with no BOM and a trailing newline.** Write it with `[System.IO.File]::WriteAllText(path, text, [System.Text.UTF8Encoding]::new($false))` — `Set-Content`/`Out-File` may add a BOM or rewrite line endings.
- **`[System.IO.File]::*` ignores PowerShell's `Push-Location`.** .NET resolves relative paths against the *process* working directory, so always pass absolute paths in loops over repo directories.
- **A `git clone` killed by a timeout can leave a repo with a valid-looking `.git` but no refs and no fetch refspec.** Repair without re-cloning:
  ```powershell
  git config remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
  git fetch origin --prune
  git checkout test
  ```
- **Verify pushes independently afterwards** — re-fetch each remote and assert the `Jenkinsfile` on `origin/test` has the nested Deploy stage and the expected default, rather than trusting the push output.

### 15.5 INWP repos excluded from the Jenkinsfile sweep

23 of the 110 INWP repos were left untouched, for the three distinct reasons below. Most are candidates for review and possible retirement.

**Excluded by team decision (19)** — not IS packages, superseded, or dormant: `claims2-api-il`, `codebooks-idit-il`, `config-il`, `cti-api-il`, `delivery-report-il`, `duno-api-il`, `elastic-apm`, `integration-il`, `konzum-api-il`, `liferay-api-il`, `lists-api-il`, `live-api-il`, `message-sdr-co-api-il`, `message-sdr-laqo-api-il`, `policy-services-il`, `sample-project`, `srm-api-il`, `task-api-il` (superseded by `tasks-api-il`), `test-acl`.

**No `test` branch, so nothing to standardize (3):** `barcode-il`, `contact-api-il`, `jcs-api-il`.

**Structural anomaly (1):** `customer-confirmation-api-il` — its version folder is named **`v003`** instead of `v3` (contents `COCustomerConfirmV003`), breaking the repo-wide `vN` convention. Left untouched deliberately: it's ambiguous whether the ant build expects `v003` or `v3`, and guessing risks a wrong-version deploy.

> Note on "last updated" dates when judging whether a repo is live: ~35 INWP repos share a last-updated date of `2025-07-02` or `2025-07-03`, which is almost certainly one bulk operation rather than real activity. Judge by whether a package is actually deployed, not by that date.

