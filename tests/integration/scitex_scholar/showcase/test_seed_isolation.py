"""Cold dry-run and actual per-user Web reads of the admitted primary files."""

import json
import multiprocessing
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from scitex_scholar.showcase import seed_mnist_library
from tests.scitex_scholar.showcase.test__seed import PROJECT, snapshot

_HOMES = {}


def user_home(request):
    if request.user.is_authenticated:
        return _HOMES.get(request.user.username)
    return None


def test_dry_run_is_stdlib_only_and_creates_no_home_state(tmp_path):
    # Arrange -- no site-packages, no inherited credentials or home paths.
    home = tmp_path / "home"
    home.mkdir()
    source = Path(__file__).resolve().parents[4] / "src"
    code = """import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
def no_network(event,args):
    if event=='socket.connect':raise AssertionError('Dry-run must not connect')
sys.addaudithook(no_network)
from scitex_scholar.showcase import seed_mnist_library
result=seed_mnist_library(Path(sys.argv[2])/'library',project='example-project-mnist')
print(json.dumps([result['new_papers'],list(Path(sys.argv[2]).iterdir())]))
"""
    # Act
    completed = subprocess.run(
        [sys.executable, "-I", "-S", "-c", code, str(source), str(home)],
        env={"HOME": str(home), "PATH": os.defpath},
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    # Assert
    assert json.loads(completed.stdout) == [4, []]


def test_seeded_library_is_visible_through_actual_per_user_web_root(tmp_path):
    # Arrange -- actual registered host capability; no request-root override.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scitex_scholar._django.settings")
    import django

    django.setup()
    from django.test import RequestFactory, override_settings

    from scitex_scholar._django.views import _library_root_for, library_list

    for name in ["alice", "bob"]:
        _HOMES[name] = tmp_path / name
    try:
        with override_settings(SCITEX_USER_HOME_PROVIDER=__name__ + ".user_home"):

            def request(name):
                req = RequestFactory().get(
                    "/api/library/list/", {"project": name + "/" + PROJECT}
                )
                req.user = SimpleNamespace(
                    username=name, is_authenticated=True, is_anonymous=False
                )
                return req

            alice, bob = request("alice"), request("bob")
            alice_root = _library_root_for(alice)
            bob_root = _library_root_for(bob)
            bob_record = bob_root / "MASTER" / "B0B0B0B0"
            bob_record.mkdir(parents=True)
            (bob_record / "metadata.json").write_text(
                json.dumps(
                    {
                        "metadata": {
                            "id": {"doi": "10.9999/owned-fixture-bob"},
                            "basic": {
                                "title": "Owned Bob fixture",
                                "authors": [],
                                "year": 2020,
                            },
                        }
                    }
                )
            )
            before = snapshot(bob_root)
            # Act
            seed_mnist_library(alice_root, project=PROJECT, dry_run=False)
            alice_response, bob_response = library_list(alice), library_list(bob)
            alice_data, bob_data = (
                json.loads(alice_response.content),
                json.loads(bob_response.content),
            )
            # Assert
            assert (
                alice_response.status_code,
                alice_data["count"],
                alice_data["filtered"],
                bob_response.status_code,
                bob_data["count"],
                snapshot(bob_root) == before,
            ) == (200, 4, True, 200, 1, True)
    finally:
        _HOMES.clear()


def _worker(root):
    def no_network(event, args):
        if event == "socket.connect":
            raise AssertionError("Example admission must not connect to a service")

    sys.addaudithook(no_network)
    result = seed_mnist_library(root, project=PROJECT, dry_run=False)
    return result["new_papers"], result["new_memberships"]


def test_two_real_seed_processes_converge_without_network(tmp_path):
    # Arrange -- both actual processes use the same owned library and lock.
    root = tmp_path / "library"
    # Act
    with multiprocessing.get_context("fork").Pool(2) as pool:
        results = pool.map_async(_worker, [root, root]).get(timeout=30)
    papers = sorted((root / "MASTER").glob("*/metadata.json"))
    # Assert
    assert (sorted(results), len(papers)) == ([(0, 0), (4, 4)], 4)
