"""Thin release admission/transport; central stdlib core owns archive algorithms."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import tomllib

REPOSITORY = "scitex-ai/scitex-scholar"
TAG = re.compile(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
SHA = re.compile(r"[0-9a-f]{40}")
LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")
PROOF = "release-proof.json"
CORE_COMMIT = "286e52925a53a8a8549db860a9e4af0dfbf58474"
CORE_FILES = {
    "release_core/__init__.py": "205c84c8b79b50d7abca4196165d169f07666039c118e79539df71a77e5df85f",
    "release_core/__main__.py": "43575b4e51c1c24948d03cad287dec672e55cb6120b930d8d27448a536a76857",
    "release_core/_metadata.py": "de9ad24888e6f2595d9d87837e4e7bee738011d02c5e847743ebecc7aed3afd8",
    "release_core/artifacts.py": "724f1d3db064de2a2935b8637c3d70445e19c99c922ff00fb16bb347474e8321",
    "release_core/files.py": "29a98f933f717bae5f44660f35729b44e37fa9224bf8ebf5a5e32b444fc5d3fb",
    "release_core/policy.py": "184ed54885c8516777110ec814abd2b9cafdd1bf37a5ba7d64636714091eae51",
    "release_core/registered.py": "b927cca22ed0c3ed2c2f1c10bba41c4b52fff6fc53a69473d0caa2b711db9c91",
    "release_core/registry.py": "f79fe92d038d735704fca2169730c8e8f06e8270ca36344503f656b2aca7545d",
    "release_core/source.py": "3e157685f0141a6f4e73350c75d6659bece6e1afed48b9095ba629c8ca7f2839",
}


def api(path, status=200, *, open_url=urllib.request.urlopen):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request("https://api.github.com/" + path, headers=headers)
    with open_url(request, timeout=10) as response:
        if response.status != status:
            raise ValueError("GitHub identity response did not match")
        if status == 204:
            return {"status": 204}
        body = response.read(1048577)
        if len(body) > 1048576:
            raise ValueError("GitHub identity response too large")
        return json.loads(body)


def member_admission(query=api):
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise ValueError("release repository does not match")
    actors = {
        os.environ.get("GITHUB_ACTOR", ""),
        os.environ.get("GITHUB_TRIGGERING_ACTOR", ""),
    }
    if not actors or any(not LOGIN.fullmatch(actor) for actor in actors):
        raise ValueError("release actor is missing or malformed")
    for actor in actors:
        if query("orgs/scitex-ai/public_members/" + actor, status=204) != {
            "status": 204
        }:
            raise ValueError("organization membership is not confirmed")


def resolve(tag, query=api):
    if not TAG.fullmatch(tag):
        raise ValueError("release requires an existing vX.Y.Z tag")
    prefix = "repos/" + REPOSITORY
    before = query(prefix + "/branches/main")
    if (
        before.get("name") != "main"
        or before.get("protected") is not True
        or not SHA.fullmatch(before.get("commit", {}).get("sha", ""))
    ):
        raise ValueError("release main is not protected and qualified")
    main_commit = before["commit"]["sha"]
    ref = query(prefix + "/git/ref/tags/" + tag)
    if ref.get("ref") != "refs/tags/" + tag:
        raise ValueError("returned tag ref differs")
    item = ref["object"]
    seen = set()
    for _ in range(5):
        digest = item.get("sha", "")
        if not SHA.fullmatch(digest) or digest in seen:
            raise ValueError("invalid or cyclic tag object")
        seen.add(digest)
        if item.get("type") == "commit":
            break
        if item.get("type") != "tag":
            raise ValueError("tag does not resolve to a commit")
        item = query(prefix + "/git/tags/" + digest)["object"]
    else:
        raise ValueError("tag annotation depth exceeded")
    commit = item["sha"]
    comparison = query(prefix + "/compare/" + commit + "..." + main_commit)
    if comparison.get("base_commit", {}).get("sha") != commit or comparison.get(
        "status"
    ) not in {"ahead", "identical"}:
        raise ValueError("release source has not been promoted to main")
    content = query(prefix + "/contents/pyproject.toml?ref=" + commit)
    if content.get("encoding") != "base64":
        raise ValueError("unsupported metadata encoding")
    raw = base64.b64decode(content["content"].replace("\n", ""), validate=True)
    if len(raw) > 131072 or hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw
    ).hexdigest() != content.get("sha"):
        raise ValueError("release metadata Git identity differs")
    project = tomllib.loads(raw.decode())["project"]
    if (
        project["name"].replace("_", "-").lower() != "scitex-scholar"
        or project["version"] != tag[1:]
    ):
        raise ValueError("tag and project metadata differ")
    after = query(prefix + "/branches/main")
    if (
        after.get("name") != "main"
        or after.get("protected") is not True
        or after.get("commit", {}).get("sha") != main_commit
    ):
        raise ValueError("release main changed during source qualification")
    return {"tag": tag, "commit": commit, "version": tag[1:]}


def regular(path, limit=1048576):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError("Release input is not a bounded regular file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(limit + 1)
        after = os.fstat(fd)
        if len(raw) > limit or (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError("Release input changed while reading")
        return raw
    finally:
        os.close(fd)


def verified_core(directory):
    expected = set(CORE_FILES)
    actual = {str(path.relative_to(directory)) for path in directory.rglob("*")}
    if actual != expected | {"release_core"}:
        raise ValueError("Central core closure has unknown or missing files")
    for name, digest in CORE_FILES.items():
        if hashlib.sha256(regular(directory / name)).hexdigest() != digest:
            raise ValueError("Central core file differs from its fixed commit")


def fetch_core(directory):
    (directory / "release_core").mkdir(mode=0o700)
    for name, digest in CORE_FILES.items():
        url = (
            f"https://raw.githubusercontent.com/scitex-ai/.github/{CORE_COMMIT}/{name}"
        )
        with urllib.request.urlopen(url, timeout=20) as response:
            if response.status != 200 or response.url != url:
                raise ValueError("Unexpected core source authority")
            raw = response.read(1048577)
        if len(raw) > 1048576 or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Public central core source does not match fixed bytes")
        fd = os.open(
            directory / name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
    verified_core(directory)


def artifact_proof(directory, tag, commit, run, attempt, source_root):
    if (
        not TAG.fullmatch(tag)
        or not SHA.fullmatch(commit)
        or not run.isdigit()
        or not attempt.isdigit()
    ):
        raise ValueError("Release identity is malformed")
    project = tomllib.loads(
        subprocess.check_output(
            ["git", "show", commit + ":pyproject.toml"], cwd=source_root, text=True
        )
    )["project"]
    if project["name"] != "scitex-scholar" or project["version"] != tag[1:]:
        raise ValueError("Tag and source project metadata differ")
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Unsafe artifact directory")
    files = sorted(path for path in directory.iterdir() if path.name != PROOF)
    if any(
        path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode) for path in files
    ):
        raise ValueError("Artifact is not a regular file")
    wheels = [path for path in files if path.name.endswith(".whl")]
    sdists = [path for path in files if path.name.endswith(".tar.gz")]
    if len(files) != 2 or len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("Release requires exactly one wheel and one sdist")
    if (
        not wheels[0].name.startswith("scitex_scholar-" + tag[1:] + "-")
        or sdists[0].name != "scitex_scholar-" + tag[1:] + ".tar.gz"
    ):
        raise ValueError("Artifact filenames differ from release version")
    with tempfile.TemporaryDirectory(prefix="scholar-central-core-") as temporary:
        core = Path(temporary)
        fetch_core(core)
        arguments = [
            "verify-files",
            "--repository",
            REPOSITORY,
            "--commit",
            commit,
            "--source-root",
            str(source_root),
            "--wheel",
            str(wheels[0]),
            "--sdist",
            str(sdists[0]),
        ]
        boot = 'import runpy,sys;sys.path.insert(0,sys.argv.pop(1));runpy.run_module("release_core",run_name="__main__")'
        environment = dict(
            os.environ,
            PATH="/usr/bin:/bin",
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL="/dev/null",
        )
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", boot, str(core), *arguments],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        identity = json.loads(result.stdout)
    return {
        "schema": "scitex-scholar-release/v1",
        "repository": REPOSITORY,
        "tag": tag,
        "commit": commit,
        "run": run,
        "attempt": attempt,
        "central_core_commit": CORE_COMMIT,
        "source_membership": identity,
    }


def main(query=api):
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["resolve", "write-proof", "verify-proof"])
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit")
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--revalidate", action="store_true")
    args = parser.parse_args()
    if args.mode == "resolve":
        member_admission(query)
        identity = resolve(args.tag, query)
        if (
            os.environ.get("GITHUB_EVENT_NAME") == "push"
            and os.environ.get("GITHUB_SHA") != identity["commit"]
        ):
            raise ValueError("Push event and tag source differ")
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            for key, value in identity.items():
                stream.write(key + "=" + value + "\n")
        print(json.dumps(identity))
        return
    source_root = Path.cwd().resolve()
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if actual != args.commit:
        raise ValueError("Checkout and release source differ")
    proof = artifact_proof(
        args.dist,
        args.tag,
        args.commit,
        os.environ.get("GITHUB_RUN_ID", ""),
        os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        source_root,
    )
    path = args.dist / PROOF
    if args.mode == "write-proof":
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(proof, stream, indent=2)
    elif json.loads(regular(path)) != proof:
        raise ValueError("Artifact proof or source bytes differ")
    if args.revalidate:
        member_admission(query)
        if resolve(args.tag, query) != {
            "tag": args.tag,
            "commit": args.commit,
            "version": args.tag[1:],
        }:
            raise ValueError("Release tag identity changed")
    print(json.dumps(proof))


if __name__ == "__main__":
    main()
