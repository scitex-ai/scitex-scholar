# Native release qualification

Scholar releases require ordinary protected-main promotion before `vX.Y.Z`
tagging. The release workflow resolves the immutable tag, checks its project
version and protected-main ancestry, and retains the existing PyPI environment
and OIDC publisher. It never merges a branch or grants publication from tests.

The shared Infrastructure-owned `leaf-release-sif` caller must register Scholar's
actual immutable image/runtime and eight critical helper hashes before eligibility.
An unregistered candidate fails closed; passing ordinary PR tests is insufficient.

The native executor verifies the complete E846 image and Apptainer bytes, removes
inherited credentials/runtime injection, and uses exclusive owned temporary roots.
`release-context.sh` is the byte-identical lifecycle control qualified for IO
(SHA256 `130f42eb7efbb511b0bcea962a84468e818e14ec3cf7498c2c45b9d145c430cc`).
Its retained ownership, process-group cancellation and cleanup bounds apply here.

Before package installation or product import, an explicit unavailable Store and
owned empty password file exclude ambient PostgreSQL routing. Each full test leg
then requires a fresh private PostgreSQL 16.15 cluster through the public Dev test
provider. The complete suite inherits only that verified Unix-socket target;
server tools, actual SQL data-directory/system identity, TCP-disabled status and
postmaster cleanup are checked. Missing tools or a failed context are errors.

Each Python 3.11/3.12/3.13 leg installs the complete declared `[all,dev]` closure
once, runs `pip check`, prepares verified job-owned Node 20.20.2 for real JavaScript
controls, and runs all tests with coverage. The registered worker cap is four,
clamped further to actual affinity/cgroup allocation. There is no reduced-extra,
interpreter, host-store, test-selection or bare-runner fallback.

The build produces a real wheel and source distribution and normally resolves
that wheel with its declared all/dev dependencies in a fresh environment. A thin
leaf adapter obtains the exact nine-file public Infrastructure `release_core`
closure, verifies every hash before import, and delegates archive/RECORD/Hatch and
whole-Git-source ownership checks to that public port. No leaf copies those
algorithms. The adapter owns only tag/main/actor admission and artifact transport.
It revalidates bytes and source immediately before the existing OIDC action.

Run archive fixtures outside VCS-ignored ancestor directories. In particular,
Hatch can disable ignore patterns when a project lives beneath `.cache`; that can
hide a genuinely omitted runtime asset. The production regression is Scholar's
retired duplicate SVG: source tracked it but the normal wheel omitted it through
`**/*.svg`. The SDK now owns the official favicon; the leaf override and duplicate
file are removed instead of excluding a missing artifact from identity checks.

Owned qualification commands (not release/publication commands):

```bash
bash .github/ci/exec-in-sif.sh run-in-sif.sh 3.11
bash .github/ci/exec-in-sif.sh run-in-sif.sh 3.12
bash .github/ci/exec-in-sif.sh run-in-sif.sh 3.13
bash .github/ci/exec-in-sif.sh build-in-sif.sh 3.12
```

These require the registered whole-image/runtime paths and hashes,
`GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT`, `RELEASE_TAG`, `RELEASE_COMMIT`, an owned
`RUNNER_TEMP`, and `CI_XDIST_WORKERS=4`. Use a clean frozen source checkout with no
stale `dist/`. The commands create only owned test resources and do not publish.
