#!/usr/bin/env bash
# Fixed native Scholar release executor; no host profile or editable fallback.
set -euo pipefail
inner="${1:?registered inner driver required}"; shift
case "$inner" in run-in-sif.sh|build-in-sif.sh) ;; *) exit 1;; esac
version="${1:?Python version required}"
[[ "$version" =~ ^3\.(11|12|13)$ ]] && [ "$#" -eq 1 ]
expected_image=e8461fc77a2218b5f7e2c475bd601dddaec97c6335bee459a1b0d4e0ca374d83
expected_runtime=7bdb501fdddbb7264b4e4d6038e0ec27201f63e217519e5f7f0db950c9285ddd
: "${SCITEX_CI_SIF:?}" "${SCITEX_CI_APPTAINER:?}" "${SCITEX_CI_SIF_SHA256:?}" "${SCITEX_CI_APPTAINER_SHA256:?}"
[ "$SCITEX_CI_SIF_SHA256" = "$expected_image" ] && [ "$SCITEX_CI_APPTAINER_SHA256" = "$expected_runtime" ]
sif="$(realpath -- "$SCITEX_CI_SIF")"; runtime="$(realpath -- "$SCITEX_CI_APPTAINER")"
[ -f "$sif" ] && [ -x "$runtime" ]
[ "$(basename -- "$sif")" = "ci-cpu-sha256-$expected_image.sif" ]
[ "$(stat -c %s -- "$sif")" = 1381281792 ] && [ "$(stat -c %s -- "$runtime")" = 48096048 ]
value="$(sha256sum -- "$sif")"; [ "${value%% *}" = "$expected_image" ]
value="$(sha256sum -- "$runtime")"; [ "${value%% *}" = "$expected_runtime" ]
for name in GITHUB_RUN_ID GITHUB_RUN_ATTEMPT RELEASE_TAG RELEASE_COMMIT; do
    [ -n "${!name:-}" ] || exit 1
done
[[ "$GITHUB_RUN_ID" =~ ^[0-9]+$ && "$GITHUB_RUN_ATTEMPT" =~ ^[0-9]+$ && "$RELEASE_COMMIT" =~ ^[a-f0-9]{40}$ ]]
[[ "$RELEASE_TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]
: "${CI_XDIST_WORKERS:?registered worker budget required}" "${RUNNER_TEMP:?owned temporary parent required}"
[[ "$CI_XDIST_WORKERS" =~ ^[1-4]$ ]]
[ ! -L "$RUNNER_TEMP" ] && [ -d "$RUNNER_TEMP" ]
IO_CONTEXT_PARENT="$(realpath -- "$RUNNER_TEMP")"
[ "$(stat -c %u -- "$IO_CONTEXT_PARENT")" = "$(id -u)" ]
# This variable name is retained by the byte-identical qualified lifecycle port.
SCRATCH_PREFIX="$IO_CONTEXT_PARENT/scholar-native-$version-"
source .github/ci/release-context.sh

driver_body() {
    mkdir "$TMPDIR/apptainer"
    # Remove inherited runtime injection aliases before the first Python process.
    # env -i also excludes model/auth/active-project settings from the test image.
    env -i PATH=/usr/local/bin:/usr/bin:/bin HOME="$HOME" LANG=C.UTF-8 \
        APPTAINER_TMPDIR="$TMPDIR/apptainer" APPTAINER_CACHEDIR="$TMPDIR/apptainer" \
        "$runtime" exec --cleanenv --no-home --pwd "$PWD" \
        --bind "$PWD:$PWD" --bind "$TMPDIR:/tmp" \
        --env "GITHUB_RUN_ID=$GITHUB_RUN_ID" --env "GITHUB_RUN_ATTEMPT=$GITHUB_RUN_ATTEMPT" \
        --env "RELEASE_TAG=$RELEASE_TAG" --env "RELEASE_COMMIT=$RELEASE_COMMIT" \
        --env "CI_XDIST_WORKERS=$CI_XDIST_WORKERS" "$sif" bash ".github/ci/$inner" "$version"
}
run_owned_body
