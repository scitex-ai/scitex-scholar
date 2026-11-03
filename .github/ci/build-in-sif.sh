#!/usr/bin/env bash
# Whole source-bound wheel/sdist plus actual normally resolved wheel smoke.
set -euo pipefail
version="${1:?Python version required}"; [ "$version" = 3.12 ] && [ "$#" -eq 1 ]
python="/opt/venv-$version/bin/python"; test -x "$python"
: "${GITHUB_RUN_ID:?}" "${GITHUB_RUN_ATTEMPT:?}" "${RELEASE_TAG:?}" "${RELEASE_COMMIT:?}"
export LC_ALL=C.UTF-8 LANG=C.UTF-8
export PATH="/opt/venv-$version/bin:/usr/lib/postgresql/16/bin:$PATH"
SCRATCH_PREFIX="/tmp/scholar-build-$version-"
source .github/ci/release-context.sh

driver_body() {
    [ ! -e dist ] && [ ! -L dist ] || { echo '::error::stale release output refused' >&2; exit 1; }
    "$python" -I -S .github/ci/probe-first-observer.py --early
    uv venv --python "$python" --seed "$TMPDIR/build-venv"
    local build_python="$TMPDIR/build-venv/bin/python"
    uv pip install --python "$build_python" build hatchling
    "$build_python" -m pip check
    "$build_python" -m build --outdir dist
    "$python" -I -S -B .github/ci/release-identity.py write-proof --tag "$RELEASE_TAG" --commit "$RELEASE_COMMIT"
    local wheels=(dist/*.whl)
    [ "${#wheels[@]}" -eq 1 ] && [ -f "${wheels[0]}" ]
    uv venv --python "$python" --seed "$TMPDIR/wheel-venv"
    local wheel_python="$TMPDIR/wheel-venv/bin/python"
    uv pip install --python "$wheel_python" "${wheels[0]}[all,dev]"
    "$wheel_python" -m pip check
    "$wheel_python" -I .github/ci/with-test-postgres.py -- "$wheel_python" -I -c '
import importlib.metadata,json,os,pathlib,sys
import scitex_scholar
root=pathlib.Path(sys.executable).parent.parent
if not pathlib.Path(scitex_scholar.__file__).resolve().is_relative_to(root):
 raise RuntimeError("Wheel smoke imported editable/source namespace")
if importlib.metadata.version("scitex-scholar")!=os.environ["RELEASE_TAG"][1:]:
 raise RuntimeError("Installed wheel metadata differs")
from scitex_scholar.showcase import mnist_reference_bibtex
bibtex=mnist_reference_bibtex()
if not isinstance(bibtex,str)or not bibtex:
 raise RuntimeError("Published read-only example reference capability missing")
print(json.dumps({"actual_wheel_namespace":True,"public_reference_catalog":True}))
'
    "$python" -I -S -B .github/ci/release-identity.py verify-proof --tag "$RELEASE_TAG" --commit "$RELEASE_COMMIT"
}
run_owned_body
