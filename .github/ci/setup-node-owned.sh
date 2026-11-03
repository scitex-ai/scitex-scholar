#!/usr/bin/env bash
# Install the official Node binary in a job directory, without the runner cache.
set -euo pipefail

node_version="20.20.2"
archive_name="node-v${node_version}-linux-x64.tar.xz"
archive_sha256="df770b2a6f130ed8627c9782c988fda9669fa23898329a61a871e32f965e007d"
node_dir=$(mktemp -d "${RUNNER_TEMP:?}/scitex-scholar-node-${GITHUB_JOB:?}-${GITHUB_RUN_ID:?}-${GITHUB_RUN_ATTEMPT:?}.XXXXXX")
archive_path="$node_dir/$archive_name"

curl --fail --location --silent --show-error --retry 2 \
    --connect-timeout 10 --max-time 60 \
    "https://nodejs.org/dist/v${node_version}/${archive_name}" \
    --output "$archive_path"
printf '%s  %s\n' "$archive_sha256" "$archive_path" | sha256sum --check --status
tar --extract --xz --file "$archive_path" --strip-components=1 --directory "$node_dir"

export PATH="$node_dir/bin:$PATH"
test "$(node -p 'process.execPath')" = "$node_dir/bin/node"
node --version
npm --version
node -p 'process.execPath'
printf '%s\n' "$node_dir/bin" >> "${GITHUB_PATH:?}"
