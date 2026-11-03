"""Owned real Git/Hatch and API-envelope controls; no publish/model/domain calls."""

import base64
import hashlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "scholar_release_identity", ROOT / ".github/ci/release-identity.py"
)
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


def command(*arguments, cwd=None):
    return subprocess.run(
        arguments, cwd=cwd, check=True, capture_output=True, timeout=120
    ).stdout


class ActualScholarArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())).resolve()
        if any(part in {".cache", ".venv", "build", "dist"} for part in parent.parts):
            raise RuntimeError(
                "Artifact fixtures require an owned temp parent outside VCS-ignored ancestors"
            )
        cls.owned = tempfile.TemporaryDirectory(prefix="scholar-artifacts-", dir=parent)
        cls.root = Path(cls.owned.name)
        cls.repo = cls.root / "source"
        cls.repo.mkdir()
        raw = command("git", "-C", str(ROOT), "archive", "HEAD")
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            archive.extractall(cls.repo, filter="data")
        command(
            "git",
            "init",
            "--template=",
            "--initial-branch=main",
            "--object-format=sha1",
            "-q",
            cwd=cls.repo,
        )
        command("git", "config", "user.name", "Owned release fixture", cwd=cls.repo)
        command("git", "config", "user.email", "fixture@example.invalid", cwd=cls.repo)
        command("git", "config", "commit.gpgsign", "false", cwd=cls.repo)
        command("git", "add", "-f", ".", cwd=cls.repo)
        command("git", "commit", "-qm", "Owned actual Scholar snapshot", cwd=cls.repo)
        cls.commit = command("git", "rev-parse", "HEAD", cwd=cls.repo).decode().strip()
        cls.version = tomllib.loads((cls.repo / "pyproject.toml").read_text())[
            "project"
        ]["version"]
        cls.tag = "v" + cls.version
        cls.dist = cls.root / "dist"
        command(
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(cls.dist),
            str(cls.repo),
        )
        cls.wheel = next(cls.dist.glob("*.whl"))
        cls.sdist = next(cls.dist.glob("*.tar.gz"))

    @classmethod
    def tearDownClass(cls):
        cls.owned.cleanup()

    def copied(self, name):
        target = self.root / name
        target.mkdir()
        shutil.copyfile(self.wheel, target / self.wheel.name)
        shutil.copyfile(self.sdist, target / self.sdist.name)
        return target

    def test_actual_source_bound_artifacts(self):
        proof = identity.artifact_proof(
            self.dist, self.tag, self.commit, "123", "1", self.repo
        )
        self.assertGreater(proof["source_membership"]["wheel_public_members"], 1000)

    def test_extra_artifact_is_refused(self):
        target = self.copied("extra")
        (target / "unknown.txt").write_text("owned refusal control")
        with self.assertRaisesRegex(ValueError, "exactly one wheel"):
            identity.artifact_proof(
                target, self.tag, self.commit, "123", "1", self.repo
            )

    def test_wrong_source_version_is_refused(self):
        with self.assertRaisesRegex(ValueError, "source project metadata"):
            identity.artifact_proof(
                self.dist, "v999.0.0", self.commit, "123", "1", self.repo
            )

    def test_newline_tag_is_refused(self):
        with self.assertRaisesRegex(ValueError, "identity is malformed"):
            identity.artifact_proof(
                self.dist, self.tag + "\n", self.commit, "123", "1", self.repo
            )

    def test_artifact_symlink_is_refused(self):
        target = self.copied("symlink")
        path = target / self.wheel.name
        path.unlink()
        path.symlink_to(self.wheel)
        with self.assertRaisesRegex(ValueError, "regular file"):
            identity.artifact_proof(
                target, self.tag, self.commit, "123", "1", self.repo
            )

    def test_unknown_core_file_is_refused(self):
        target = self.root / "unknown-core"
        target.mkdir()
        (target / "foreign.py").write_text('raise RuntimeError("not executed")')
        with self.assertRaisesRegex(ValueError, "closure"):
            identity.verified_core(target)

    def source_query(self, protected=True, bad_blob=False, move_after=False):
        raw = command("git", "show", self.commit + ":pyproject.toml", cwd=self.repo)
        count = 0

        def query(path, status=200):
            nonlocal count
            prefix = "repos/scitex-ai/scitex-scholar"
            if path == prefix + "/branches/main":
                count += 1
                return {
                    "name": "main",
                    "protected": protected and not (move_after and count > 1),
                    "commit": {"sha": self.commit},
                }
            if path == prefix + "/git/ref/tags/" + self.tag:
                return {
                    "ref": "refs/tags/" + self.tag,
                    "object": {"type": "commit", "sha": self.commit},
                }
            if path == prefix + "/compare/" + self.commit + "..." + self.commit:
                return {"base_commit": {"sha": self.commit}, "status": "identical"}
            if path == prefix + "/contents/pyproject.toml?ref=" + self.commit:
                digest = hashlib.sha1(
                    b"blob " + str(len(raw)).encode() + b"\0" + raw
                ).hexdigest()
                return {
                    "encoding": "base64",
                    "content": base64.b64encode(raw).decode(),
                    "sha": "0" * 40 if bad_blob else digest,
                }
            raise AssertionError("Unexpected API-envelope path")

        return query

    def test_owned_git_metadata_resolves_api_envelope(self):
        self.assertEqual(
            identity.resolve(self.tag, self.source_query()),
            {"tag": self.tag, "commit": self.commit, "version": self.version},
        )

    def test_unprotected_main_is_refused(self):
        with self.assertRaisesRegex(ValueError, "main is not protected"):
            identity.resolve(self.tag, self.source_query(protected=False))

    def test_main_protection_drift_is_refused(self):
        with self.assertRaisesRegex(ValueError, "main changed"):
            identity.resolve(self.tag, self.source_query(move_after=True))

    def test_git_blob_mismatch_is_refused(self):
        with self.assertRaisesRegex(ValueError, "Git identity differs"):
            identity.resolve(self.tag, self.source_query(bad_blob=True))


if __name__ == "__main__":
    unittest.main()
