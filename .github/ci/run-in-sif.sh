#!/usr/bin/env bash
# Complete Scholar all/dev test suite inside the registered immutable image.
set -euo pipefail
version="${1:?Python version required}"
[[ "$version" =~ ^3\.(11|12|13)$ ]] && [ "$#" -eq 1 ]
python="/opt/venv-$version/bin/python"; test -x "$python"
: "${GITHUB_RUN_ID:?}" "${GITHUB_RUN_ATTEMPT:?}" "${RELEASE_TAG:?}" "${RELEASE_COMMIT:?}" "${CI_XDIST_WORKERS:?}"
[[ "$CI_XDIST_WORKERS" =~ ^[1-4]$ ]]
export LC_ALL=C.UTF-8 LANG=C.UTF-8
export PATH="/opt/venv-$version/bin:/usr/lib/postgresql/16/bin:$PATH"
SCRATCH_PREFIX="/tmp/scholar-test-$version-"
source .github/ci/release-context.sh

driver_body() {
    # No site/.pth or product import may precede this stdlib refusal-floor proof.
    "$python" -I -S .github/ci/probe-first-observer.py --early
    uv venv --python "$python" --seed "$TMPDIR/venv"
    local test_python="$TMPDIR/venv/bin/python"
    uv pip install --python "$test_python" -e '.[all,dev]'
    "$test_python" -m pip check
    export PATH="$TMPDIR/venv/bin:/usr/lib/postgresql/16/bin:$PATH"
    export COVERAGE_FILE="$TMPDIR/.coverage" RUNNER_TEMP="$TMPDIR" GITHUB_JOB=scholar-native
    export GITHUB_PATH="$TMPDIR/node-path"
    : > "$GITHUB_PATH"
    bash .github/ci/setup-node-owned.sh
    local node_path
    IFS= read -r node_path < "$GITHUB_PATH"
    [ -x "$node_path/node" ] && [ "${node_path%/bin}" != "$node_path" ]
    export PATH="$node_path:$PATH"
    local workers
    workers="$("$test_python" -I -S - "$CI_XDIST_WORKERS" <<'PY'
import math,os,sys
from pathlib import Path
limits=[int(sys.argv[1]),os.cpu_count()or 1]
if hasattr(os,'sched_getaffinity'):limits.append(len(os.sched_getaffinity(0)))
try:
 quota,period=Path('/sys/fs/cgroup/cpu.max').read_text().split()
 if quota!='max':limits.append(max(1,math.floor(int(quota)/int(period))))
except(FileNotFoundError,PermissionError,ValueError,ZeroDivisionError):pass
for controller in('cpu','cpu,cpuacct'):
 try:
  root=Path('/sys/fs/cgroup')/controller;quota=int((root/'cpu.cfs_quota_us').read_text());period=int((root/'cpu.cfs_period_us').read_text())
  if quota>0:limits.append(max(1,math.floor(quota/period)))
 except(FileNotFoundError,PermissionError,ValueError,ZeroDivisionError):pass
print(max(1,min(limits)))
PY
)"
    echo "Scholar registered worker cap=$CI_XDIST_WORKERS effective_workers=$workers"
    "$test_python" -I .github/ci/with-test-postgres.py -- \
        nice -n 19 ionice -c 3 "$test_python" -m pytest tests/ -n "$workers" --dist load -q \
        --cov=src/scitex_scholar --cov-report="xml:$TMPDIR/coverage.xml" --cov-report=term \
        -p no:cacheprovider
}
run_owned_body
