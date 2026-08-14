# Fenster — History & Learnings

## Project Context
- **Project:** Payments Dispute Resolution (agentic evidence-assembly accelerator)
- **Lead developer:** Jorge Balderas
- **Stack:** AZD · Bicep · GitHub Actions · Azure Functions · Azure AI Services · Event Grid
- **Repo:** https://github.com/yortch/payment-disputes

## Key Learnings

### CI/CD Foundation (2026-07-07)
- **Node.js + npm ci:** Setup Node 20 with `npm ci` (not install) in `src/web` before pytest to prevent TS2307 errors during Vite build
- **Test gating:** Install `requirements-dev.txt` (not ad-hoc packages) to ensure jsonschema available; bare `pytest` with no stderr suppression to catch collection errors
- **Python version:** Pin Python 3.11 via `actions/setup-python@v5` in CI before AZD Deploy

### Infrastructure Patterns (2026-07-06–07)
- **Static Web App:** Use raw `Microsoft.Web/staticSites@2023-12-01` (Free SKU) for offline safety; requires Standard SKU for linkedBackends
- **Bicep conventions:** AZD service matching via `azd-service-name` tag; abbreviations without trailing dash (e.g., `"staticWebApp": "stapp"`)
- **SWA routing:** Add `/api/*` to navigationFallback.exclude to preserve API proxy; Client-side routing requires index.html fallback
- **Linked backends:** Feed `functionAppResourceId` output to SWA `linkedBackends` child resource for control-plane proxy (unaffected by data-plane privacy)

### Durable Functions SDK (2026-07-06)
- **Decorator kwargs:** Use `context_name=` and `client_name=` (NOT `context_parameter`/`client_parameter`) to avoid module import TypeError

### Cosmos Integration (2026-07-07–08)
- **Postdeploy hooks:** Use cross-platform POSIX/Windows sub-keys; set `continueOnError: false` for real failures; deferred imports allow env var override
- **Upsert idempotency:** Cosmos `upsert_item()` by id prevents duplicates on re-run
- **App settings:** `CASE_STORE` app setting needed for Functions to select Cosmos backend; env var reconciliation via `COSMOS_* OR AZURE_COSMOS_*` lookup
- **Explicit seed step in CD:** Dedicated step after AZD Deploy with visible output beats silent postdeploy hooks
- **Seed soft-fail:** Exit 0 cleanly if Cosmos not provisioned (local envs)

### Azure Policy & Network Compliance (2026-07-08)
- **Policy constraint:** The subscription has audit/audit-if-not-exists on publicNetworkAccess (not Modify). Explicit `publicNetworkAccess: 'Enabled'` in Bicep is primary defense
- **Private networking (deferred to Phase 2):** Requires VNet + Private Endpoints + private DNS zones. FC1 requires Flex VNet integration (`Microsoft.App/environments`). Deployment package uses blob data plane → needs PE. Option: self-hosted runner in VNet OR explicit `az functionapp deploy` step (control-plane, unaffected)
- **ACR analysis:** Container/ACR path (ACA) has zero policy coverage but removes deployment-blob dependency. Deferred — not justified for Phase 1
- **SWA unaffected:** linkedBackend proxy is control-plane only — no storage/Cosmos privacy impact

### Repo Hygiene (2026-07-08)
- **CI paths-ignore:** Add `paths-ignore: ['.squad/**', '**/*.md']` to both `push` and `pull_request` triggers in `ci.yml` so squad state files and markdown-only changes never trigger CI
- **Node-24 action versions:** Minimum Node-24-native major versions are `actions/checkout@v5`, `actions/setup-node@v5`, `actions/setup-python@v6`; `azure/login@v2` and `azure/setup-azd@v2` are already Node-24-safe
- **product-vision.md consolidation:** File was a strict subset of `prd.md`; deleted via `git rm`; removed dangling link from README.md Supporting Documentation table; added CHANGELOG entry under [Unreleased]

### Multi-SWA / Portal Wiring (2026-07-08)
- **Parametrize `azd-service-name` tag:** When reusing a Bicep module for a second AZD service (e.g. a second Static Web App), add a `param azdServiceName string = 'web'` (default preserves existing behavior) instead of duplicating the module file — keeps linkedBackend/SKU logic in one place
- **Multi-service azd deploy:** `azd deploy --no-prompt` deploys ALL services declared in `azure.yaml` in a single command — adding a new `staticwebapp` service needs zero changes to `cd.yml`, only `azure.yaml` + the corresponding infra module instantiation
- **Locked node_modules on Windows during local build verification:** Leftover `vite`/`esbuild` dev-server processes (started in earlier sessions) can hold an `EPERM` lock on `node_modules` binaries during `npm ci`; find the offending PID via `Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Select CommandLine` and `Stop-Process -Id <pid> -Force` before retrying
- **Two Standard-tier SWAs = double the SWA cost:** Each Standard SWA instance has its own monthly base cost; flag this explicitly in a decision note when adding a second Standard SWA rather than assuming it's obviously fine

### Portal SWA Linked-Backend Conflict Fix (2026-07-08)
- **Linked-backend exclusivity is a hard Azure constraint, not a config error:** A single Function App can only be linked as the backend of ONE Static Web App at a time (`Microsoft.Web/staticSites/linkedBackends`). Adding a second SWA that links the same already-linked Function App fails CD provisioning with `Conflict: Cannot link backend with a preexisting Azure Static Web Apps configuration.` **Future SWAs added to this repo must NOT attempt a linked backend against a Function App that's already linked to another SWA** — use `linkBackend: false` on the module (see `infra/modules/staticwebapp.bicep`) and have that SWA reach the API via CORS + an absolute URL instead.
- **CORS-based alternative pattern:** For a second SWA without a linked backend, set `corsAllowedOrigins` on the Function App (`infra/modules/functions.bicep`) and set `VITE_API_BASE_URL` at build time via a service-level `prebuild` hook in `azure.yaml` (writes `.env.production.local` consumed by Vite). The client code should read `import.meta.env.VITE_API_BASE_URL` with a `/api` fallback so it works either way.
- **Don't add a separate `Microsoft.Web/sites/config` sub-resource for siteConfig tweaks** when the Function App already declares `siteConfig` inline on the `sites` resource — a separate config sub-resource can conflict with/overwrite the inline block. Add new siteConfig properties (like `cors`) directly into the existing inline object.
- **azd service-level hooks default `cwd` to repo root** (directory containing `azure.yaml`), not the service's project directory; `cwd` is an explicit, settable per-hook property relative to `azure.yaml`'s location. Confirmed via azd docs (2026-07-08) — use `cwd: ./src/<service>` on hooks that need to write into a service directory (e.g. the portal's `prebuild` hook writing `.env.production.local` for Vite).

### EasyAuth-as-implicit-side-effect-of-linked-backends + azd hook lifecycle scoping (2026-07-08, stacked prod bugs)
- **`linkedBackends` implicitly enables Function App EasyAuth v2:** Creating `Microsoft.Web/staticSites/linkedBackends` auto-provisions App Service Authentication on the linked Function App (`authsettingsV2.globalValidation.requireAuthentication = true`, registers only that one SWA as an allowed `azureStaticWebApps` identity provider) — this is NOT declared anywhere in our Bicep, purely an Azure platform side effect. It 401s every caller that isn't proxied through the linked SWA, including any other SWA reaching the same Function App via CORS + absolute URL. This is the SECOND implicit Azure coupling discovered in this exact area (first was linked-backend exclusivity itself, see prior entry below). **Any Function App that will ever be linked as a SWA backend needs an explicit `authsettingsV2` sub-resource (`platform.enabled: false` + `globalValidation.requireAuthentication: false`) declared in Bicep** to keep anonymous/CORS-based access working for non-linked callers — don't rely on the platform default.
- **`prebuild`/`postbuild` azd hooks only fire for the standalone `azd build` command** — `azd deploy` and `azd up` invoke `azd package` internally, which has its own packaging flow and does NOT run build-lifecycle hooks at all. Confirmed by direct local testing: `azd build portal` ran the hook; `azd package portal` (clean state) did not, reproducing the exact "bundle missing the API URL" production symptom. **Any hook meant to affect what `azd deploy`/`azd up` actually ship must be `prepackage`/`postpackage` (or `predeploy`/`postdeploy`), never `prebuild`/`postbuild`.**
- **`cwd` is NOT a valid azd hook property — the schema field is `dir`** (confirmed against `azure.yaml.json` schema: `hook` definition has `additionalProperties: false` and only recognizes `dir`, not `cwd`). Unknown hook properties are silently ignored (no error), which masks the bug. Additionally, for a SERVICE-scoped hook, azd already defaults the working directory to that service's own project root — adding `dir: ./src/<service>` on top of that resolves to a nonexistent nested path and fails the hook outright (confirmed via `fork/exec cmd.exe: The directory name is invalid.` locally). **Service-scoped hooks that just need to write into the service's own directory need no `dir`/`cwd` override at all.**
- **Reproduction workflow for azd hook/package bugs:** `azd hooks run <name> --service <svc> --environment <env>` runs a hook in isolation (useful but can mask lifecycle-scoping bugs since it runs the hook regardless of which command would normally trigger it); `azd build <svc>` / `azd package <svc>` against a clean local checkout (delete any stale `dist/`, `.env.production.local` etc. first) is the reliable way to confirm which real azd command lifecycle actually triggers a given hook.

---

**Last updated:** 2026-07-08 (summarized by Scribe)

### Lock File & TypeScript Type Sync (2026-07-09)
- **npm ci fails when package.json/package-lock.json are out of sync:** When a PR merges dependency updates (e.g. vite/vitest patch bumps) to `package.json` without regenerating `package-lock.json`, CI fails at the "Install web dependencies" step with `npm error Missing: esbuild@X.Y.Z from lock file`. **Root cause:** npm install added new transitive `@esbuild/*` platform packages that need to be locked. **Fix:** Run `npm install` (NOT `npm ci`) locally to regenerate `package-lock.json`, then commit the updated lock file. Verify `npm ci` works cleanly afterward on a fresh `node_modules` teardown.
- **TypeScript type definitions must stay in sync with mock data / feature PRs:** When a feature PR (e.g. PR #69) adds new mock data with previously-unsupported string-literal values (e.g. evidence types `"photo"`, `"fraud_screening"`, `"device_fingerprint"`), the TypeScript types that define those literal unions must also be updated (`src/types/case.ts` EvidenceType union). Otherwise `tsc --noEmit` in the build fails despite the mock data being logically valid. **Always check type definitions when adding new literal values in mock data or expanding enum-like fields.**
- **Lock file generation can be time-consuming on Windows:** Clean `npm install` after `rm -r node_modules` can take 40+ minutes on some Windows machines, especially in shared environments. Planning CI and local development around this is important; `npm ci` is much faster once the lock file is in sync (48s in this case).

## Learnings

### CD Concurrency & RBAC Propagation (2026-07-09)
- **`azd deploy --no-prompt` (no service arg) deploys ALL `azure.yaml` services CONCURRENTLY:** On a 2-core/7GB GitHub-hosted runner, three simultaneous `npm install` processes (web + portal, one a large Vite/React app) exceed available memory and get SIGKILL'd (`signal: killed`), a classic OOM-kill — invisible in logs beyond the bare signal. **Fix:** split into sequential per-service steps — `azd deploy api --no-prompt`, then `azd deploy web --no-prompt`, then `azd deploy portal --no-prompt` — so each service gets the full runner memory budget and installs never overlap.
- **RBAC role assignments from `azd provision` are not immediately enforceable:** `infra/modules/functions.bicep`'s `deployerBlobAssignment` grants the deployer "Storage Blob Data Contributor" during provision, but Azure AD RBAC propagation can lag by several minutes. The very next `azd deploy` step (zip blob upload) can hit `InaccessibleStorageException ... 403` even though the role assignment "succeeded." **Fix:** wrap the `api` deploy step (the one doing the blob upload right after provision) in a retry loop (3 attempts, 30s backoff) rather than adding an unconditional sleep — most runs won't need the retry, but it absorbs propagation delay when it happens. Deploy `api` first specifically because it's the one immediately following `provision`.
- **Order services in CD deploy steps by which is most sensitive to provision side effects first** (here: `api` right after `provision` due to RBAC propagation), then the rest by convention (`web`, `portal`) — don't assume alphabetical/declared order in `azure.yaml` is deploy-safe order.

**Last updated:** 2026-07-09 (Fenster: Lock file & TypeScript sync fix)

### Cosmos/Storage publicNetworkAccess — Phase 0 Stopgap Deployed, Escalation Evidence Confirmed (2026-07-09)
- **Deployed `.github/workflows/network-reconcile.yml`** (Phase 0 stopgap per `.squad/decisions.md`'s "Detect-and-Heal Automation" proposal) — 15-min cron + `workflow_dispatch`, re-enables `publicNetworkAccess` on `<STORAGE_ACCOUNT_NAME>` and `<COSMOS_ACCOUNT_NAME>` if found `Disabled`, restarts the Function App on storage flips. Required adding new repo var `AZURE_FUNCTION_APP_NAME`. This is workflow-only, no-approval-needed per decisions.md's Phase 0 checklist.
- **Escalation trigger confirmed and exceeded:** decisions.md's trigger for mandatory Phase 1 (private networking) is "`publicNetworkAccess` found `Disabled` again after an `azd provision` that asserted `Enabled`." That happened. But live testing went further: manually running `az storage account update --public-network-access Enabled` and `az cosmosdb update --public-network-access ENABLED` returned success, yet polling every 30s for 5 minutes showed the property **stayed `Disabled` continuously — it never even transiently flipped to `Enabled`**. The Phase 0 workflow's own reconcile step hit the same result. **This means the setting cannot currently be forced to `Enabled` by any method tried (azd provision, direct ARM PATCH, standalone Bicep deploy, CLI update, GitHub Actions reconcile) — this is stronger evidence of active, likely near-synchronous policy enforcement than "flips back after some delay."**
- **Takeaway for future infra work on this repo:** Do not assume a successful `az ... update`/`provisioningState: Succeeded` response means the requested property value actually took effect on resources governed by organizational Azure Policy governance — always verify with a subsequent `show`/poll before treating the change as applied. Filed as `.squad/decisions/inbox/fenster-phase0-stopgap-deployed.md` with an explicit recommendation to escalate Phase 1 (private networking) as urgent; Phase 1 Bicep work itself has NOT been started and requires Jorge's explicit approval first.

**Last updated:** 2026-07-09 (Fenster: Phase 0 network-reconcile stopgap + Phase 1 escalation evidence)
### Phase 1 Private Networking Implementation (2026-07-09)
- **FC1 (Flex Consumption) VNet integration is the SAME `virtualNetworkSubnetId` /
  `vnetRouteAllEnabled` property pair as classic App Service** on `Microsoft.Web/sites` —
  it is NOT a separate `Microsoft.App/managedEnvironments` (ACA) resource, despite the
  required subnet delegation service name (`Microsoft.App/environments`) superficially
  suggesting ACA. The delegation name is the one FC1-specific wrinkle; the wiring on the
  Function App resource itself is unchanged from classic App Service VNet integration.
  Confirmed via current Microsoft Learn guidance (`functions-networking-options`, flex tab)
  2026-07-09.
- **Do NOT delegate the FC1 VNet-integration subnet to `Microsoft.Web/serverFarms`** — that
  delegation is for classic App Service Environments only and causes deployment failures for
  Flex Consumption. Always use `Microsoft.App/environments` for FC1.
- **`az deployment sub what-if` / `az deployment sub validate` are effective pre-provision
  gates for subscription-scoped `main.bicep` templates** (this repo's `main.bicep` has
  `targetScope = 'subscription'` and creates its own resource group) — pass
  `--location <region>` plus the same parameters `azd provision` would use (environmentName,
  location, principalId from `az ad signed-in-user show --query id`, principalType). Use this
  before any high-risk infra change (e.g. disabling public network access) rather than
  provisioning live and hoping for the best.
- **`az functionapp deploy --type zip --async false` is the documented control-plane path**
  for deploying to a Function App whose backing storage account has `publicNetworkAccess:
  Disabled` — it POSTs to the Kudu/SCM endpoint (public management plane) rather than writing
  directly to the storage blob data-plane, which a GitHub-hosted runner without VNet access
  cannot reach once storage is private. `azd deploy <service>` for a Function App, by contrast,
  uploads the package zip directly to blob storage from the runner and will 403 once storage is
  private — confirmed by tracing `functions.bicep`'s `deployerBlobAssignment` role grant and the
  `functionAppConfig.deployment.storage.value` blob URL, and documented in
  `.squad/decisions.md`'s "Follow-up: Keep Deploy Fully via azd" section. Static Web Apps are
  unaffected either way — SWA deployment goes through the SWA API, not storage data-plane.

**Last updated:** 2026-07-09 (Fenster: Phase 1 private networking implementation)

### Self-Hosted VNet Runner Implementation (2026-07-09)
- **FC1 has NO Kudu/SCM zip-deploy bypass — confirmed by production failure.** Phase 1's primary
  mechanism (`az functionapp deploy --type zip --async false`) 415'd in production. ARM inspection
  showed `functionAppConfig.deployment.storage` is *always* a direct `blobContainer` reference for
  Flex Consumption — unlike classic App Service, there is no control-plane path that avoids the
  storage data plane. When a resource's docs/behavior differ from classic App Service assumptions,
  verify directly against ARM (`az functionapp show --query functionAppConfig.deployment`) rather
  than assuming SCM/Kudu behavior carries over.
- **Cosmos seed step also breaks once Cosmos is private** — a stale `cd_log.txt` in the repo root
  (untracked, leftover from a prior run) revealed `seed_cosmos.py` failing with
  `CosmosHttpResponseError: Forbidden ... blocked by your Cosmos DB account firewall settings`
  when run from the GitHub-hosted runner. Any CD step that touches a data-plane endpoint on a
  privatized resource (blob, queue, table, Cosmos SQL) needs to move to the in-VNet runner, not
  just the specific step that first surfaced an error — audit ALL CD steps against ALL privatized
  resources, not just the one that happens to fail first.
- **Ephemeral per-run ACI pattern for self-hosted GitHub Actions runners**: `az container create`
  (with `myoung34/github-runner:latest`, `EPHEMERAL=true`, a per-run-unique `LABELS` value like
  `cd-run-${{ github.run_id }}-${{ github.run_attempt }}`) in one GH-hosted-runner job, matched by
  a `runs-on: [self-hosted, <label>]` job that GitHub Actions natively queues until a runner with
  that label registers, followed by an `if: always()` cleanup job that runs `az container delete`
  regardless of success/failure. This is cheaper than an always-on runner for CD pipelines that
  only trigger occasionally (e.g. `workflow_run` on push to main) — cost is proportional to actual
  run time (~$0.0006 for a 5-min 1vCPU/1.5GB ACI) instead of a constant idle cost.
- **ACI subnet delegation for `Microsoft.ContainerInstance/containerGroups` needs its own subnet**
  — do not reuse a subnet already hosting private endpoints (`privateEndpointNetworkPolicies`) or
  a different delegation (e.g. `Microsoft.App/environments` for FC1 VNet integration). Each
  delegation type needs a clean, dedicated subnet.
- **`.azure/` is gitignored** — a fresh self-hosted-runner job (new checkout) has no local azd
  environment state, so `azd env get-values` won't work there unless the whole provision job ran
  in the same job context. For CD steps that run in a *different* job than `azd provision`,
  resolve outputs via direct `az` ARM queries (e.g. `az cosmosdb list`/`show --query
  documentEndpoint`) instead of relying on azd environment state.
- **Key file paths**: `infra/modules/network.bicep` (subnets), `infra/modules/runner.bicep` (new —
  runner identity + RBAC), `infra/main.bicep` (wiring + `AZURE_RUNNER_SUBNET_ID`/
  `AZURE_RUNNER_IDENTITY_ID` outputs), `.github/workflows/cd.yml` (4-job ephemeral-runner split).

### Stale Top-Level `postdeploy` Hook Broke web/portal Deploys Post-PR #74 (2026-07-09)
- **A top-level (non-service-scoped) `hooks.postdeploy` in `azure.yaml` fires after EVERY
  `azd deploy <service>` call, not just the service it was originally added for.** When PR #74
  moved Cosmos seeding responsibility into the `deploy-api` job of `cd.yml` (self-hosted, in-VNet
  runner, explicit `PYTHONPATH=. python3 scripts/seed_cosmos.py` step), the pre-existing top-level
  `postdeploy` hook in `azure.yaml` was left in place. It kept firing after `azd deploy web` and
  `azd deploy portal` too — both of which run on the GitHub-hosted runner in `provision-and-build`
  — and broke CD run 29032121104 with `ModuleNotFoundError: No module named 'azure'` (no Python
  venv there, and Cosmos is private now anyway so it couldn't connect even with deps installed).
- **Rule for next time: when moving a hook's responsibility into an explicit CD workflow job,
  always check `azure.yaml`'s TOP-LEVEL global `hooks` block for leftover duplicates/conflicts —
  not just per-service hooks.** Global hooks are easy to forget because they're declared once at
  the top and don't visually sit next to the service they were written for; grep `azure.yaml` for
  the hook name (e.g. `seed_cosmos`) whenever refactoring where/how that responsibility is
  triggered, and delete the stale top-level entry rather than leaving it as a "harmless" no-op —
  it is not harmless once it starts running on the wrong runner.
- Fixed via PR #75 (`fix/remove-stale-postdeploy-hook`): deleted the top-level `postdeploy` block
  entirely, kept `preprovision`, updated `README.md` and `.squad/skills/azd-seed-hook/SKILL.md` to
  point at the `deploy-api` job instead of the removed hook. `cd.yml` was not touched — it was
  already correct.

### Runner Subnet NAT Gateway Fix — VNet-injected ACI has NO default outbound egress (2026-07-09)
- **Root cause:** CD run 29033981840's ephemeral ACI (`gh-runner-29033981840-1`) hung in
  `Creating`/`Waiting to run` for 12+ minutes and never registered with GitHub. `az container show`
  confirmed `ipAddress.type: Private`, `ip: 0.0.0.0` (private IP only, correct/intentional), but the
  `runner` subnet had `natGateway: null` and only default NSG rules — no explicit egress path at all.
- **Key correction to the original self-hosted-runner design (2026-07-09 decision):** the original
  assumption "the subnet relies on Azure's default outbound internet access" was WRONG for
  VNet-injected Container Instances specifically. A container group with only a private IP and no
  explicit egress path (NAT Gateway, Azure Firewall + UDR, or a Standard LB with outbound rules)
  generally CANNOT reach the internet — it just hangs indefinitely with no clear provisioning error
  (ACI doesn't surface egress failures in its state). A subnet's `privateEndpointNetworkPolicies` /
  delegation settings say nothing about outbound connectivity — don't conflate the two.
- **An earlier apparently-successful run (`start-runner` job 86167370153, ~2m20s registration) under
  the same network config is NOT evidence the no-NAT-gateway design was sound** — likely a cached
  image pull or a race, not a deterministic path. Don't use one green run to override a structural
  network-design gap.
- **Fix:** added a Standard SKU NAT Gateway + its own Standard SKU public IP in
  `infra/modules/network.bicep`, associated with the `runner` subnet ONLY (via the subnet's
  `natGateway.id` property) — `private-endpoints` and `func-integration` are untouched, they don't
  need outbound internet.
- **Cost tradeoff:** NAT Gateway + its public IP are always-on (no "stopped" state), ~$32-40/month
  base, even though the ACI itself is ephemeral. Recommended keeping it always-on rather than trying
  to make the NAT Gateway itself ephemeral (spin up/down per CD run) — added complexity isn't
  justified for a low-volume, nightly-ish CD trigger. Revisit only if a low-complexity way to
  create/delete the NAT Gateway alongside the runner container in the same `start-runner`/
  `cleanup-runner` jobs presents itself.
- **Validation pattern for subnet-level networking changes:** `az bicep build` for syntax, then
  `az deployment sub what-if --location <loc> --template-file main.bicep --parameters
  environmentName=... location=... principalId=<az ad signed-in-user show --query id -o tsv>
  principalType=User` against the real target RG confirms additive-only impact (resource counts to
  create/modify/delete) even when other pre-existing drift shows up as noise in the same what-if
  output — read the resource *type* diffs carefully, don't be alarmed by unrelated drift.

**Last updated:** 2026-07-09 (Fenster: Runner subnet NAT Gateway fix for ACI outbound egress bug)

### Azure CLI Missing on Self-Hosted Runner Image (2026-07-09)
- **Root cause:** With the self-hosted ephemeral VNet runner CD mechanism (PR #74, NAT fix in #77)
  finally working end-to-end, the `deploy-api` job's `Login to Azure (OIDC)` step (`azure/login@v2`)
  still failed with `Unable to locate executable file: az`. The `myoung34/github-runner:latest`
  base image used for the ephemeral runner does not ship the Azure CLI preinstalled, unlike
  GitHub-hosted `ubuntu-latest` runners which do.
- **Fix:** Added an `Install Azure CLI` step in `deploy-api` right after `Download Functions package
  artifact` and before `Login to Azure (OIDC)`, using the official Microsoft install script
  (`curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash`), guarded by `command -v az` so it's a
  no-op if `az` is already present. Matched the existing `sudo apt-get` privilege-elevation pattern
  already used by the job's `Ensure Python 3 is available` step, confirming `sudo` is available in
  this container. See PR #78.
- **General principle: a self-hosted runner's container/VM image does NOT inherit anything from
  GitHub-hosted runners' preinstalled toolchain.** GitHub-hosted `ubuntu-latest` images ship dozens
  of tools (az CLI, docker, various language runtimes) preinstalled; a custom self-hosted image
  (like `myoung34/github-runner:latest`, which is a minimal runner-agent wrapper, not a full
  `ubuntu-latest` clone) ships none of that by default. **Any CLI/tool a self-hosted job's steps
  invoke must be either explicitly installed as an early step in that job, or baked into a custom
  base image** — never assume parity with GitHub-hosted runners just because the workflow YAML
  looks the same. Audit every `run:` step in a self-hosted job for tool dependencies whenever the
  base image changes or a job is moved from `ubuntu-latest` to `self-hosted`.

**Last updated:** 2026-07-09 (Fenster: az CLI missing on self-hosted runner image fix)

### Docker Hub Anonymous-Pull Rate Limit Behind Shared NAT IP (2026-07-09)
- **Root cause:** After the NAT Gateway fix (#77) and az CLI fix (#78), `start-runner`'s
  `az container create` step began failing with `(RegistryErrorResponse) An error response is
  received from the docker registry 'index.docker.io'. Please retry later.` The coordinator
  confirmed via a direct test (pulling the unrelated `hello-world` image from the same `runner`
  subnet) that this reproduces with ANY Docker Hub image, not just `myoung34/github-runner` —
  proving it's a registry-level rate limit, not an image-specific problem. Docker Hub enforces
  anonymous-pull limits (100 pulls / 6h) per source IP. The NAT Gateway added in #77 to give ACI
  outbound internet access means every container pull from the `runner` subnet shares ONE public
  IP, so today's repeated CD run attempts (testing the NAT fix, then the az-CLI fix) exhausted that
  IP's shared anonymous quota well before any single workflow run would have on its own.
- **Fix:** Mirror `myoung34/github-runner:latest` to GHCR (`ghcr.io/<repo>/github-runner:latest`)
  from a new step on the GitHub-hosted `ubuntu-latest` runner (separate, non-exhausted Docker Hub
  IP pool) in every `start-runner` job run, then have `az container create` pull from GHCR with
  `--registry-login-server`/`--registry-username`/`--registry-password` authenticated via the
  built-in `GITHUB_TOKEN` (required adding `packages: write` to the job's permissions). No new
  secrets needed. See PR #79.
- **General principle: any VNet-egress design that funnels many ephemeral workloads through one NAT
  IP should assume a SHARED external rate-limit budget, not a per-workload budget.** Anonymous
  public registries (Docker Hub, and likely others) rate-limit by source IP; concentrating traffic
  behind a single NAT IP (as any NAT Gateway / single-IP egress design does) multiplies the chance
  of exhausting that budget compared to per-container-assigned public IPs. Prefer routing external
  image/dependency pulls through an authenticated registry (a mirror in GHCR/ACR, or an
  authenticated Docker Hub pull) over anonymous public pulls whenever workloads share an egress IP.

**Last updated:** 2026-07-09 (Fenster: GHCR mirror fix for Docker Hub anonymous-pull rate limit)

## Learnings

### Experiment: `SecurityControl: 'Ignore'` Tag to Bypass Azure Policy Enforcement (2026-07-09)
- **What was tried:** Jorge hypothesized that a `SecurityControl: 'Ignore'` tag might trigger a
  tag-based skip condition some internal/custom Azure Policy definitions use as a lighter-weight
  alternative to a formal Policy Exemption object — potentially letting `publicNetworkAccess:
  Enabled` and `defaultAction: Allow` survive on Cosmos/Storage without the governance policy set
  flipping them back. On branch `experiment/policy-tag-bypass`: added `SecurityControl: 'Ignore'`
  to the shared `tags` var in `infra/main.bicep` (propagates to all resources via the existing
  threaded `tags` param); set `publicNetworkAccess: 'Enabled'` +
  `isVirtualNetworkFilterEnabled: false` in `infra/modules/cosmos.bicep`; set
  `publicNetworkAccess: 'Enabled'` + `networkAcls.defaultAction: 'Allow'` in
  `infra/modules/storage.bicep`. `az bicep build` passed clean on all three files.
  **Not deployed** — opened as PR #80, explicitly left unmerged for coordinator/user review given
  the security tradeoff (this would weaken the network posture organizational Azure Policy governance otherwise enforces, IF the
  tag actually works — unverified). Full writeup in
  `.squad/decisions/inbox/fenster-policy-tag-bypass-experiment.md`.
- **Why this matters for future sessions:** if PR #80 is later closed/rejected without merging,
  remember this was tried and either (a) didn't work — in which case don't re-attempt the same
  tag without new evidence it's honored by the governance policy set, or (b) worked but was rejected
  on security-tradeoff grounds — in which case don't re-propose it without addressing that
  objection. Either way, the self-hosted-runner-in-VNet / private-networking approach (PRs
  #74/#77/#79 and related) remains the supported, already-working path for CD to reach
  Cosmos/Storage privately.

**Last updated:** 2026-07-09 (Fenster: SecurityControl:Ignore Azure Policy bypass experiment, PR #80, unmerged)

### CD Simplification: self-hosted VNet runner removed (2026-07-09)
- **Update to the note above:** PR #80's `SecurityControl: 'Ignore'` tag experiment was
  **confirmed working** via a live test directly against Azure — `publicNetworkAccess: 'Enabled'`
  held stable on Cosmos DB and the Storage Account with the tag applied, and PR #80 was merged.
  This flips the earlier conclusion: outcome (a)/(b) speculation above is resolved — the tag
  *does* work and was accepted.
- **Consequence:** the ephemeral self-hosted-runner-in-VNet mechanism (PRs #74/#77/#78/#79 —
  `start-runner` ACI in the `runner` subnet, GHCR image mirroring to dodge Docker Hub anonymous
  rate limits on the shared NAT IP, `cleanup-runner` teardown) became unnecessary the moment
  public network access could stay enabled. CD no longer needs to reach Cosmos/Storage from
  inside the VNet — a plain GitHub-hosted `ubuntu-latest` runner reaches both directly over the
  public internet, with TLS + RBAC/Entra auth still fully enforced (only the network-layer
  restriction was relaxed by the tag, not authentication).
- **What I did:** opened PR #82, "Simplify CD: remove self-hosted VNet runner (superseded by
  SecurityControl:Ignore tag)" — removed the `start-runner` and `cleanup-runner` jobs entirely,
  changed `deploy-api`'s `runs-on` back to `ubuntu-latest`, dropped its `needs: start-runner`
  dependency (now just `needs: provision-and-build`), and removed the now-dead "Install Azure
  CLI" and "Ensure Python 3 is available" steps that existed only to compensate for
  `myoung34/github-runner`'s base image (ubuntu-latest ships both preinstalled). Also removed the
  now-unused `RUNNER_LABEL`/`RUNNER_CONTAINER_NAME` env vars and updated stale comments.
  **Not merged** — per standing convention, workflow file changes require manual coordinator
  review + merge even though general auto-merge is otherwise authorized.
- **Left in place, out of scope:** `infra/modules/network.bicep` (NAT Gateway, VNet, private
  endpoints, runner subnet/identity) was NOT touched — it's now dormant/unused by CD but harmless
  to leave; removing it is a separate future cleanup decision.
- **Why this matters for future sessions:** the self-hosted-runner-in-VNet pattern from
  #74/#77/#78/#79 is now superseded/dormant, not the supported path anymore — don't resurrect it
  for CD unless the `SecurityControl: Ignore` tag approach (PR #80) is reverted or stops being
  honored by the governance policy set. If that ever happens, this simplification (PR #82) would
  need to be reverted and the ephemeral-runner mechanism reinstated.

### FC1 (Flex Consumption) deploy mechanism — `az functionapp deploy --type zip` is incompatible (2026-07-09)
- **Root cause of 415 Unsupported Media Type:** `az functionapp deploy --type zip` uses the legacy
  Kudu/SCM OneDeploy zip-push endpoint. Flex Consumption (FC1) uses
  `functionAppConfig.deployment.storage.type: blobContainer` — a blob-container-based deployment
  storage model that the Kudu endpoint **does not support**. This is an Azure CLI limitation
  specific to FC1. The 415 error happens regardless of network path, RBAC propagation timing,
  CLI version, or whether public network access is enabled or disabled.
- **RBAC propagation and networking were red herrings for this specific 415.** The extensive
  work on private networking (VNet, private endpoints, self-hosted runner, NAT Gateway, GHCR
  mirroring — PRs #74/#77/#78/#79) and the `SecurityControl: Ignore` tag / publicNetworkAccess
  fix (PR #80) were responding to a real but separate concern (network access and policy compliance).
  They improved security posture and should be kept — but they were NOT what was causing the 415.
- **Correct fix:** Use `Azure/functions-action@v1` with `remote-build: true` in GitHub Actions.
  This action uses the correct SCM API path for FC1's deployment model and authenticates via the
  existing `azure/login@v2` OIDC step — no `publish-profile` secret required.
- **General principle: when an Azure CLI command returns an HTTP 4xx against a resource whose
  configuration (e.g. `functionAppConfig.deployment`) differs from classic App Service, verify
  against ARM (`az functionapp show --query functionAppConfig.deployment`) before assuming it's
  network or auth.** FC1 has several behaviors that diverge from classic App Service; don't assume
  Kudu/SCM behavior from classic carries over.
- **Implemented in:** PR `fix/functions-action-deploy` (branch: `fix/functions-action-deploy`).
  Decision note filed at `.squad/decisions/inbox/fenster-fc1-deploy-mechanism-fix.md`.

**Last updated:** 2026-07-09 (Fenster: FC1 deploy mechanism fix — functions-action@v1 + remote-build)

### Cleanup: removed obsolete `network-reconcile.yml` stopgap (2026-07-09)
- **What changed:** Deleted `.github/workflows/network-reconcile.yml`, the old 15-minute
  Phase 0 reconcile cron that force-reset `publicNetworkAccess` to `Enabled` on Storage and
  Cosmos when policy drift was suspected.
- **Why it is now safe:** the `SecurityControl: 'Ignore'` tag-bypass from PR #80 is confirmed
  stable in production, and the full GitHub-hosted CD path finally ran green end-to-end the same
  day (Functions deploy via `Azure/functions-action@v1` plus Cosmos seed with real data). That
  means the stopgap is no longer protecting anything — it would only create needless control-plane
  churn and could reset Cosmos firewall propagation timing during future debugging.
- **Repo follow-up:** updated `.squad/decisions.md` to mark the stopgap deletion complete and note
  why the workflow was retired.

**Last updated:** 2026-07-09 (Fenster: removed obsolete network-reconcile stopgap)


### Public repo prep — security cleanup (2026-08-12)

- **Task:** Prepared security/public-repo-prep branch for public repository release.
- **Removed committed build artifact:** 20485227-3f9a-4894-b487-04c8ae2287d5-app.zip (AZD-generated deployment artifact accidentally committed). Added *.zip to root .gitignore to prevent recurrence.
- **Removed tracked .env files:** src/customer-portal/.env, src/customer-portal/.env.production.local, src/web/.env — all contained live infra values. Added .env / .env.* ignore patterns with !*.env.sample exceptions to root .gitignore.
- **Redacted internal program name and team references** across all tracked files: README.md, CHANGELOG.md, prd.md, docs/architecture.md, docs/ingestion-flow.md, docs/demo/index.html, docs/demo/narration.md, .squad/team.md, .squad/decisions.md, .squad/agents/redfoot/history.md. Replacement: "Payments Dispute Resolution" for program names, "the project team" for byline references.
- **Renamed docs/delivery/** and did a full redaction pass on all files within (README.md, DELIVERY-SUMMARY.md, all 10 assets). Renamed Delivery-Package.docx accordingly.
- **Renamed scripts:** scripts/generate-delivery-word.js and .py equivalent; updated all internal strings and output paths.
- **Rewrote cd.yml comment** at line ~73: internal governance label → "organizational Azure Policy governance".
- **Secret/credential sweep results:** All matches were false positives — Bicep parameter names referencing Key Vault, Python variable holding env var reference, skill documentation examples. No literal secrets found in src/infra/data.
- **GUID sweep finding:** a real Service Principal Client ID was found in docs/fabric-mirroring-setup.md — redacted to <YOUR-SERVICE-PRINCIPAL-CLIENT-ID>. All other GUIDs in non-seed files are Azure built-in role definition IDs (public), synthetic case/dispute IDs, or test fixtures — all benign.
- **Flag for Verbal/user review:** docs/delivery/ folder content (particularly 4-SECURITY-GOVERNANCE.md, 9-TECHNICAL-DEEP-DIVE.md, 10-TEAM-DEMO-SCRIPT.md) still reads as internal-audience delivery documentation beyond just the naming. Recommend reviewing whether the full docs/delivery/ folder should be included in the public repo or moved behind a separate branch/tag.

### Public repo prep — GUID purge phase 1 (2026-08-14)

- **Missed identifiers from earlier sweep (PR #103):** The prior sweep left two live Azure identifiers in `main` HEAD. Both are now replaced with named placeholders: the subscription ID (replaced with `<AZURE_SUBSCRIPTION_ID>`) and the Fabric workspace ID (replaced with `<FABRIC_WORKSPACE_ID>`). Refer to them by placeholder name only — never write raw GUID values in squad records.
- **Where the subscription ID was found:** purely in a docstring/comment block in `src/api/services/document_service.py` (no functional usage; confirmed comment-only before redacting), in `HANDOFF.md`, and in `.squad/decisions.md`.
- **Where the Fabric workspace ID was found:** in `CHANGELOG.md` within the Fabric mirroring attempt entry.
- **Internal program name residuals:** Seven files still contained internal program name and internal policy set name references that the prior sweep missed (all in `.squad/` agent history and decisions). All replaced with neutral equivalents ("organizational Azure Policy governance" for policy behavior, "the delivery program"/"the project team" for byline/program references, "the governance policy set" for the internal policy set name).
- **Verification:** `git grep` confirmed zero remaining hits for all five target GUIDs (subscription ID, Fabric workspace ID, tenant ID, SP client ID, SP object ID) and zero remaining internal program name matches (case-insensitive) outside seed/synthetic/test directories.
- **Test suite:** `pytest tests -k "not integration"` — 403 passed, 0 failed after the `document_service.py` edit. Comment-only change; no functional code was touched.
- **Lesson:** Even comment blocks in source files can harbor live identifiers. Future sweeps must include all Python docstrings/comment blocks, not just docs/ and .squad/. Commit messages must never contain raw GUID values or internal program names — describe what was removed generically.
