#!/usr/bin/env bash
# Exclusive, identity-guarded release scratch; sourced by fixed drivers.
# BEGIN owned temporary-root lifecycle
OWNED_TMPDIR=""
OWNED_TMP_ID=""
OWNED_CHILD_PID=""
OWNED_CHILD_GROUP=""
OWNED_CHILD_BIRTH=""
OWNED_CHILD_STARTING=0
OWNED_PENDING_SIGNAL=""
OWNED_PENDING_STATUS=""

owned_birth() {
    local line
    IFS= read -r line < "/proc/$1/stat" || return 1
    line="${line##*) }"
    set -- $line
    printf '%s' "${20}"
}

# IO's full all/dev environment is a reviewed large job-temp class. This is
# a filesystem cleanup budget, independent of product/kernel test deadlines.
owned_cleanup_budget() {
    local entries="$1" allocated="$2"
    [[ "$entries" =~ ^[0-9]+$ && "$allocated" =~ ^[0-9]+$ ]] || return 1
    if (( entries <= 10000 && allocated <= 1073741824 )); then
        printf '10'
    elif (( entries <= 200000 && allocated <= 34359738368 )); then
        printf '60'
    else
        return 1
    fi
}

owned_cleanup_plan() {
    local metrics='' survey_status=0 entries='' allocated='' budget=''
    metrics="$(/usr/bin/timeout 10s /usr/bin/find "$OWNED_TMPDIR" -xdev -printf '%b\n' |
        awk '{entries++; allocated+=$1*512} END {printf "%.0f %.0f", entries, allocated}')" || survey_status=$?
    if [ "$survey_status" -ne 0 ]; then
        echo "::error::owned cleanup survey failed (status=$survey_status); root retained" >&2
        return 1
    fi
    read -r entries allocated <<< "$metrics"
    budget="$(owned_cleanup_budget "$entries" "$allocated")" || {
        echo "::error::owned cleanup exceeds reviewed profile (entries=$entries allocated_bytes=$allocated); root retained" >&2
        return 1
    }
    echo "owned cleanup: entries=$entries allocated_bytes=$allocated budget_seconds=$budget" >&2
    printf '%s' "$budget"
}

cleanup_owned_tmp() {
    local result=$? cleanup_result=0 current_id='' attempt=0
    trap - EXIT INT TERM
    unset MINTED
    # Reaping the body alone is insufficient when a descendant remains.
    # The retained group must disappear before removing its scratch.
    if [[ -n "$OWNED_CHILD_GROUP" ]]; then
        for attempt in {1..40}; do
            kill -0 -- "-$OWNED_CHILD_GROUP" 2>/dev/null || break
            sleep 0.05
        done
        if kill -0 -- "-$OWNED_CHILD_GROUP" 2>/dev/null; then
            echo "::error::owned child group remains; temporary cleanup refused" >&2
            cleanup_result=1
        fi
    fi
    if [ -n "$OWNED_TMPDIR" ]; then
        current_id="$(stat -c '%d:%i:%u:%a' -- "$OWNED_TMPDIR" 2>/dev/null)" || cleanup_result=1
        if [ "$cleanup_result" -eq 0 ] && [ ! -L "$OWNED_TMPDIR" ] && [ -d "$OWNED_TMPDIR" ] &&
           [ -n "$OWNED_TMP_ID" ] && [ "$current_id" = "$OWNED_TMP_ID" ]; then
            local cleanup_budget='' removal_started=0
            if cleanup_budget="$(owned_cleanup_plan)"; then
                # Surveying may take time. Recheck the exact root immediately
                # before removal; no metadata/content inspection relaxes ownership.
                current_id="$(stat -c '%d:%i:%u:%a' -- "$OWNED_TMPDIR" 2>/dev/null)" || cleanup_result=1
                if [ "$cleanup_result" -eq 0 ] && [ ! -L "$OWNED_TMPDIR" ] &&
                   [ "$current_id" = "$OWNED_TMP_ID" ]; then
                    removal_started=$SECONDS
                    /usr/bin/timeout --signal=TERM --kill-after=2s "${cleanup_budget}s" \
                        /usr/bin/rm -rf --one-file-system -- "$OWNED_TMPDIR" || cleanup_result=$?
                    echo "owned cleanup: removal_status=$cleanup_result elapsed_seconds=$((SECONDS-removal_started))" >&2
                else
                    cleanup_result=1
                fi
            else
                cleanup_result=1
            fi
        else
            cleanup_result=1
        fi
        if [ "$cleanup_result" -ne 0 ]; then
            echo "::error::owned temporary cleanup refused or failed (status=$cleanup_result expected=$OWNED_TMP_ID actual=$current_id)" >&2
            [ "$result" -ne 0 ] || result=1
        fi
    fi
    exit "$result"
}

terminate_owned_child() {
    local signal="$1" status="$2" watchdog=""
    # A child may run before $! and its kernel birth token are registered.
    # Retain the first cancellation until admission completes; do not exit
    # with an untracked live group or signal a PID without its birth token.
    if [[ "$OWNED_CHILD_STARTING" == 1 ]]; then
        if [[ -z "$OWNED_PENDING_SIGNAL" ]]; then
            OWNED_PENDING_SIGNAL="$signal"
            OWNED_PENDING_STATUS="$status"
        fi
        return 0
    fi
    trap '' INT TERM
    if [[ -n "$OWNED_CHILD_PID" && "$OWNED_CHILD_BIRTH" =~ ^[0-9]+$ ]] \
        && [[ "$(owned_birth "$OWNED_CHILD_PID" 2>/dev/null || true)" == "$OWNED_CHILD_BIRTH" ]]; then
        kill -s "$signal" -- "-$OWNED_CHILD_PID" 2>/dev/null || true
        # The watchdog checks this exact child's kernel birth before signalling
        # its group, then is reaped by the owning shell on either outcome.
        (
            sleep 2
            if [[ "$OWNED_CHILD_BIRTH" =~ ^[0-9]+$ ]] && [[ "$(owned_birth "$OWNED_CHILD_PID" 2>/dev/null || true)" == "$OWNED_CHILD_BIRTH" ]]; then
                kill -KILL -- "-$OWNED_CHILD_PID" 2>/dev/null || true
            fi
        ) &
        watchdog=$!
        wait "$OWNED_CHILD_PID" 2>/dev/null || true
        kill -TERM -- "-$watchdog" 2>/dev/null || true
        wait "$watchdog" 2>/dev/null || true
    fi
    exit "$status"
}

trap cleanup_owned_tmp EXIT
trap 'terminate_owned_child INT 130' INT
trap 'terminate_owned_child TERM 143' TERM

run_owned_body() {
    local status=0
    OWNED_CHILD_STARTING=1
    # Bash job control creates a group for exactly this owned body, so a
    # termination targets its descendants rather than the runner's group.
    set -m
    (
        set +m
        trap 'unset MINTED' EXIT
        # Keep this exact group leader alive through the watchdog window.
        # Foreground descendants retain their ordinary signal dispositions.
        trap 'unset MINTED; sleep 3' INT TERM
        driver_body
    ) &
    OWNED_CHILD_PID=$!
    OWNED_CHILD_GROUP="$OWNED_CHILD_PID"
    OWNED_CHILD_BIRTH="$(owned_birth "$OWNED_CHILD_PID" 2>/dev/null || true)"
    OWNED_CHILD_STARTING=0
    if [[ -n "$OWNED_PENDING_SIGNAL" ]]; then
        terminate_owned_child "$OWNED_PENDING_SIGNAL" "$OWNED_PENDING_STATUS"
    fi
    wait "$OWNED_CHILD_PID" || status=$?
    OWNED_CHILD_PID=""
    return "$status"
}
# END owned temporary-root lifecycle

OWNED_TMPDIR="$(/usr/bin/mktemp -d "${SCRATCH_PREFIX}XXXXXX")"
readonly OWNED_TMPDIR
suffix="${OWNED_TMPDIR#"$SCRATCH_PREFIX"}"
[[ "$OWNED_TMPDIR" = "$SCRATCH_PREFIX"* && "$suffix" =~ ^[[:alnum:]]{6}$ ]]
[ "${OWNED_TMPDIR%/*}" = "${IO_CONTEXT_PARENT:-/tmp}" ] && [ ! -L "$OWNED_TMPDIR" ] && [ -d "$OWNED_TMPDIR" ]
OWNED_TMP_ID="$(stat -c '%d:%i:%u:%a' -- "$OWNED_TMPDIR")"
[ "${OWNED_TMP_ID##*:}" = 700 ]
[ "$(stat -c '%u' -- "$OWNED_TMPDIR")" = "$(id -u)" ]
readonly OWNED_TMP_ID
export TMPDIR="$OWNED_TMPDIR"


# Every cache and package state root belongs to this exclusive context.
mkdir -p "$TMPDIR/cache" "$TMPDIR/config" "$TMPDIR/state" "$TMPDIR/mpl"
export SCITEX_DIR="$TMPDIR/state" XDG_CACHE_HOME="$TMPDIR/cache"
export XDG_CONFIG_HOME="$TMPDIR/config" MPLCONFIGDIR="$TMPDIR/mpl"
export UV_CACHE_DIR="$TMPDIR/cache/uv" PIP_CACHE_DIR="$TMPDIR/cache/pip"
export MPLBACKEND=Agg SCITEX_DEV_NO_CURRENCY_REFRESH=1
unset VIRTUAL_ENV PYTHONHOME PYTHONPATH || true

# Package installers and pre-cluster imports must also be unable to reach an
# ambient store. The mandatory PG wrapper replaces this explicit refusal target
# with its owned socket only for the complete suite / installed-wheel smoke.
for io_pg_name in "${!PG@}"; do
    unset "$io_pg_name"
done
: > "$TMPDIR/empty-pgpass"
chmod 600 "$TMPDIR/empty-pgpass"
export PGPASSFILE="$TMPDIR/empty-pgpass"
export SCITEX_STORE_DSN="postgresql://io_ci@/io_ci?host=$TMPDIR/unavailable-store"
export SCITEX_CARDS_DB="$SCITEX_STORE_DSN"
