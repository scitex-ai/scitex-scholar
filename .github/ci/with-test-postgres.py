"""Require one public, private PG16.15 context for the complete Scholar suite."""

from __future__ import annotations

import json
import os
import signal
import stat
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def birth(pid):
    try:
        parts = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
    except FileNotFoundError:
        return None
    return None if parts[0] in {"Z", "X"} else parts[19]


def interrupted(signum, _frame):
    raise SystemExit(128 + signum)


def main(arguments):
    command = arguments[1:] if arguments[:1] == ["--"] else arguments
    if not command:
        raise SystemExit("usage: with-test-postgres.py -- COMMAND [ARGS...]")
    # This environment was established by the stdlib-first shell before install.
    import importlib.util

    path = Path(__file__).with_name("probe-first-observer.py")
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Unowned boundary helper")
    spec = importlib.util.spec_from_file_location("_scholar_boundary", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.early_boundary()
    root = module.private_root()
    for tool in ("postgres", "initdb", "pg_ctl", "pg_controldata"):
        actual = Path("/usr/lib/postgresql/16/bin") / tool
        if not actual.is_file() or not os.access(actual, os.X_OK):
            raise RuntimeError("Required PG16 server tools are absent")
    version = subprocess.check_output(
        ["/usr/lib/postgresql/16/bin/postgres", "--version"], text=True
    ).strip()
    if version.split()[:3] != ["postgres", "(PostgreSQL)", "16.15"]:
        raise RuntimeError("PostgreSQL image capability differs")
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig in handlers:
        signal.signal(sig, interrupted)
    from scitex_dev.store import host_store
    from scitex_dev.store.testing import ephemeral_cluster_dsn

    if host_store(pkg="scholar").dsn != os.environ["SCITEX_STORE_DSN"]:
        raise RuntimeError("First public provider ignored the unavailable boundary")
    import psycopg

    data = None
    pid = None
    token = None
    status = None
    try:
        with ephemeral_cluster_dsn() as dsn:
            target = urlsplit(dsn)
            query = parse_qs(target.query)
            if (
                target.scheme != "postgresql"
                or target.hostname is not None
                or target.username != "postgres"
                or target.password is not None
                or target.path != "/postgres"
                or set(query) != {"host"}
                or len(query["host"]) != 1
            ):
                raise RuntimeError("Private cluster returned an unexpected target")
            socket = Path(query["host"][0])
            cluster = socket.parent
            s = cluster.lstat()
            if (
                cluster.parent != root
                or cluster.is_symlink()
                or not stat.S_ISDIR(s.st_mode)
                or s.st_uid != os.getuid()
                or stat.S_IMODE(s.st_mode) != 0o700
                or not cluster.name.startswith("scitex-store-test-")
            ):
                raise RuntimeError("Private cluster is outside its exclusive context")
            sock = socket / ".s.PGSQL.5432"
            info = sock.lstat()
            if (
                socket.is_symlink()
                or not stat.S_ISSOCK(info.st_mode)
                or info.st_uid != os.getuid()
            ):
                raise RuntimeError("Private PG socket is not owned")
            with psycopg.connect(dsn) as connection:
                connection.execute("SET TRANSACTION READ ONLY")
                directory, system_id, server, listen = connection.execute(
                    "SELECT current_setting('data_directory'),system_identifier::text,current_setting('server_version_num'),current_setting('listen_addresses') FROM pg_control_system()"
                ).fetchone()
                data = Path(directory)
                if (
                    data != cluster / "data"
                    or data.is_symlink()
                    or server != "160015"
                    or listen != ""
                ):
                    raise RuntimeError(
                        "Private SQL does not attest the owned PG16.15 resource"
                    )
            pid = int((data / "postmaster.pid").read_text().splitlines()[0])
            token = birth(pid)
            if token is None:
                raise RuntimeError("Owned postmaster is not alive")
            os.environ.update(
                SCITEX_STORE_DSN=dsn,
                SCITEX_CARDS_DB=dsn,
                SCITEX_SCHOLAR_TEST_PG_DSN=dsn,
                SCITEX_SCHOLAR_TEST_PG_REQUIRED="1",
                PGHOST=str(socket),
                PGPORT="5432",
                PGDATABASE="postgres",
                PGUSER="postgres",
            )
            if host_store(pkg="scholar").dsn != dsn:
                raise RuntimeError("Whole-suite provider ignored its owned PG")
            print(
                "SCHOLAR_PRIVATE_PG "
                + json.dumps(
                    {
                        "server_version": server,
                        "system_id": system_id,
                        "socket_owned": True,
                        "tcp_disabled": True,
                    }
                ),
                flush=True,
            )
            try:
                status = subprocess.run(
                    command, env=dict(os.environ), check=False
                ).returncode
            finally:
                # Complete the provider's own stop before handling cancellation.
                for sig in handlers:
                    signal.signal(sig, signal.SIG_IGN)
        if data.exists() or birth(pid) == token:
            raise RuntimeError("Private PostgreSQL cleanup did not complete")
        print(
            "SCHOLAR_PRIVATE_PG_CLEANUP "
            + json.dumps({"owned_pg_removed": True, "owned_postmaster_gone": True}),
            flush=True,
        )
        return status if status >= 0 else 128 - status
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
