import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


CLI = Path(__file__).resolve().parents[1] / "lib" / "gates.py"
SPEC = importlib.util.spec_from_file_location("gates", CLI)
gates = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gates)


def report(*sources):
    rows = []
    for name, missed, covered in sources:
        rows.append('<sourcefile name="{}"><counter type="LINE" missed="{}" covered="{}"/></sourcefile>'
                    .format(name, missed, covered))
    return '<report name="test"><package name="demo">{}</package></report>'.format("".join(rows))


class RepoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Gate tests")
        for path, text in {
            ".gitignore": "build/\n*/build/\n",
            "src/main/java/demo/A.java": "class A {}\n",
            "src/test/java/demo/ATest.java": "class ATest {}\n",
            "docs/specs/1.md": "AC-1-01\n",
            "docs/arch/1.md": "design\n",
            "docs/arch/budget.md": "budget\n",
            "docs/arch/ownership-map.md": "ownership\n",
            ".agents/profile.md": "profile\n",
            "AGENTS.md": "project rules\n",
            ".opencode/framework.md": "runtime rules\n",
        }.items():
            self.write(path, text)
        self.base = self.commit()

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def cli(self, expected, *args):
        run = subprocess.run([sys.executable, str(CLI), *args], cwd=self.root,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(expected, run.returncode, run.stdout + run.stderr)
        data = json.loads(run.stdout)
        self.assertEqual({0: "PASS", 1: "FAIL", 2: "ERROR"}[expected], data["status"])
        return data

    def test_freshness_rejects_test_changes(self):
        self.write("src/test/java/demo/ATest.java", "class ATest { int n; }\n")
        self.commit()
        self.cli(1, "freshness", "--verified", self.base)

    def test_freshness_invalid_sha_is_error(self):
        self.cli(2, "freshness", "--verified", "f" * 40)

    def test_freshness_only_exact_qa_file_is_exempt(self):
        self.write("docs/qa/1.md", "PASS\n")
        self.commit()
        self.cli(0, "freshness", "--verified", self.base, "--qa-report", "docs/qa/1.md")
        self.write("docs/qa/2.md", "another report\n")
        self.commit()
        self.cli(1, "freshness", "--verified", self.base, "--qa-report", "docs/qa/1.md")

    def test_freshness_rejects_qa_symlink(self):
        (self.root / "docs/qa").mkdir()
        (self.root / "docs/qa/1.md").symlink_to("../specs/1.md")
        self.commit()
        self.cli(1, "freshness", "--verified", self.base, "--qa-report", "docs/qa/1.md")

    def test_freshness_rejects_divergent_commit(self):
        self.write("other.txt", "other\n")
        other = self.commit()
        self.git("checkout", "-q", self.base)
        self.cli(1, "freshness", "--verified", other)

    def snapshot(self, expected=0, *more):
        return self.cli(expected, "contract", "--spec", "docs/specs/1.md",
                        "--arch", "docs/arch/1.md", *more)

    def test_contract_binds_all_approval_inputs(self):
        approved = self.snapshot()["snapshot"]
        for path in ("docs/specs/1.md", "docs/arch/1.md", ".agents/profile.md",
                     "AGENTS.md", "docs/arch/budget.md", "docs/arch/ownership-map.md",
                     ".opencode/framework.md"):
            with self.subTest(path=path):
                self.write(path, "changed\n")
                self.commit()
                current = self.snapshot(1, "--expected", approved)["snapshot"]
                self.assertNotEqual(approved, current)
                approved = current

    def test_contract_ignores_code_and_qa(self):
        approved = self.snapshot()["snapshot"]
        self.write("src/main/java/demo/A.java", "class A { int n; }\n")
        self.write("docs/qa/1.md", "report\n")
        self.commit()
        self.snapshot(0, "--expected", approved)

    def test_contract_missing_input_is_error(self):
        (self.root / "docs/arch/1.md").unlink()
        self.commit()
        self.snapshot(2)

    def test_empty_approval_snapshot_is_error(self):
        self.snapshot(2, "--expected", "")

    def coverage_command(self, text, destination="build/jacoco.xml"):
        code = ("from pathlib import Path; p = Path({!r}); "
                "p.parent.mkdir(parents=True, exist_ok=True); p.write_text({!r})").format(destination, text)
        return shlex.join([sys.executable, "-c", code])

    def changed_source(self, path="src/main/java/demo/A.java"):
        self.write(path, "class Changed {}\n")
        return self.commit()

    def coverage(self, expected, xml=None, *extra, command=None):
        if command is None:
            command = self.coverage_command(xml or report(("A.java", 0, 10)))
        return self.cli(expected, "coverage", "--base", self.base, "--minimum", "95",
                        "--source", "src/main/java=build/jacoco.xml", "--command", command, *extra)

    def test_coverage_missing_changed_source_never_reports_100(self):
        self.changed_source()
        self.changed_source("src/main/java/demo/B.java")
        data = self.coverage(1)
        self.assertEqual(["src/main/java/demo/B.java"], data["missing"])

    def test_coverage_complete_report_and_threshold(self):
        self.changed_source()
        self.coverage(0)
        self.coverage(1, report(("A.java", 1, 9)))

    def test_coverage_checks_rename_target(self):
        self.git("mv", "src/main/java/demo/A.java", "src/main/java/demo/B.java")
        self.commit()
        self.coverage(1)
        self.coverage(0, report(("B.java", 0, 10)))

    def test_coverage_kotlin_uses_sourcefile(self):
        self.changed_source("src/main/kotlin/demo/Functions.kt")
        self.coverage(0, report(("Functions.kt", 0, 10)),
                      "--source", "src/main/kotlin=build/jacoco.xml")

    def test_coverage_rejects_stale_report(self):
        self.changed_source()
        self.write("build/jacoco.xml", report(("A.java", 0, 10)))
        self.coverage(2, command="true")

    def test_coverage_rejects_failed_command_and_pipeline(self):
        self.changed_source()
        self.coverage(1, command="false | cat")
        self.coverage(1, command=self.coverage_command(report(("A.java", 0, 10))) + "; exit 1")

    def test_coverage_missing_command_or_report_is_error(self):
        self.changed_source()
        self.coverage(2, command="")
        self.coverage(2, command="true")

    def test_coverage_rejects_ambiguous_or_malformed_report(self):
        self.changed_source()
        self.coverage(2, report(("A.java", 0, 10), ("A.java", 0, 10)))
        self.coverage(2, "<broken")
        self.coverage(2, report(("A.java", -1, 10)))
        self.coverage(2, report(("A.java", 0, 0)))

    def test_coverage_rejects_unmapped_module(self):
        self.changed_source("service/src/main/java/demo/A.java")
        self.coverage(2)

    def test_coverage_rejects_cross_module_alias(self):
        self.changed_source()
        self.changed_source("service/src/main/java/demo/A.java")
        self.coverage(2, None, "--source", "service/src/main/java=build/jacoco.xml")

    def test_coverage_modules_have_separate_reports(self):
        self.changed_source()
        self.changed_source("service/src/main/java/demo/A.java")
        cmd = self.coverage_command(report(("A.java", 0, 10)))
        cmd += " && " + self.coverage_command(report(("A.java", 10, 0)), "service/build/jacoco.xml")
        data = self.coverage(1, None, "--source", "service/src/main/java=service/build/jacoco.xml", command=cmd)
        self.assertEqual(50, data["coverage"])

    def test_coverage_no_source_change_is_explicit(self):
        data = self.coverage(0, command="false")
        self.assertIs(False, data["applicable"])

    def test_coverage_rejects_dirty_tree_and_head_change(self):
        self.changed_source()
        self.write("src/main/java/demo/A.java", "dirty\n")
        self.coverage(2)
        self.commit()
        command = self.coverage_command(report(("A.java", 0, 10)))
        command += " && git commit --allow-empty -qm unexpected"
        self.coverage(2, command=command)

    def migrations(self, expected, tool="liquibase"):
        return self.cli(expected, "migrations", "--base", self.base, "--tool", tool,
                        "--path", ":(glob)**/db/changelog/**", "--path", ":(glob)**/db/migration/**")

    def liquibase_fixture(self):
        self.master = "src/main/resources/db/changelog/master.xml"
        self.prefix = '<databaseChangeLog xmlns="http://www.liquibase.org/xml/ns/dbchangelog">'
        self.initial = '<include file="001.sql" relativeToChangelogFile="true"/>'
        self.write(self.master, self.prefix + self.initial + "</databaseChangeLog>")
        self.write("src/main/resources/db/changelog/001.sql", "create table a(id int);\n")
        self.base = self.commit()

    def test_liquibase_allows_new_include(self):
        self.liquibase_fixture()
        self.write(self.master, self.prefix + self.initial +
                   '<include file="002.sql" relativeToChangelogFile="true"/></databaseChangeLog>')
        self.write("src/main/resources/db/changelog/002.sql", "create table b(id int);\n")
        self.commit()
        self.migrations(0)

    def test_liquibase_rejects_old_migration_edit(self):
        self.liquibase_fixture()
        self.write("src/main/resources/db/changelog/001.sql", "drop table a;\n")
        self.commit()
        self.migrations(1)

    def test_liquibase_rejects_missing_or_existing_include_target(self):
        self.liquibase_fixture()
        self.write(self.master, self.prefix + self.initial +
                   '<include file="002.sql" relativeToChangelogFile="true"/></databaseChangeLog>')
        self.commit()
        self.migrations(2)
        self.write(self.master, self.prefix + self.initial + self.initial + "</databaseChangeLog>")
        self.commit()
        self.migrations(1)

    def test_liquibase_rejects_reordered_or_changed_existing_nodes(self):
        self.liquibase_fixture()
        self.write(self.master, self.prefix + self.initial.replace("001.sql", "002.sql") + "</databaseChangeLog>")
        self.write("src/main/resources/db/changelog/002.sql", "select 1;\n")
        self.commit()
        self.migrations(1)

    def test_flyway_rejects_edit_delete_and_rename(self):
        old = "src/main/resources/db/migration/V1__initial.sql"
        self.write(old, "select 1;\n")
        self.base = self.commit()
        self.write(old, "select 2;\n")
        self.commit()
        self.migrations(1, "flyway")
        (self.root / old).unlink()
        self.write(old.replace("V1", "V2"), "select 1;\n")
        self.commit()
        self.migrations(1, "flyway")

    def test_flyway_allows_new_file(self):
        self.write("src/main/resources/db/migration/V1__initial.sql", "select 1;\n")
        self.commit()
        self.migrations(0, "flyway")

    def test_logs_distinguishes_retrieval_error_from_clean(self):
        self.cli(2, "logs", "--", sys.executable, "-c", "raise SystemExit(1)")
        self.cli(2, "logs", "--", "/not/a/command")
        self.cli(0, "logs", "--", sys.executable, "-c", "print('started')")
        data = self.cli(1, "logs", "--", sys.executable, "-c", "print('ERROR secret-value')")
        self.assertNotIn("secret-value", json.dumps(data))

    def artifact_command(self, digest=None, commit=None):
        data = {"commit": commit or self.base, "artifacts": {"api": digest or "sha256:" + "a" * 64}}
        return shlex.join([sys.executable, "-c", "print({!r})".format(json.dumps(data))])

    def test_artifact_requires_same_commit_and_deployed_digest(self):
        expected = self.cli(0, "artifact", "--verified", self.base,
                            "--command", self.artifact_command())["manifest_sha"]
        self.cli(0, "artifact", "--verified", self.base, "--expected", expected,
                 "--command", self.artifact_command())
        self.cli(1, "artifact", "--verified", self.base, "--expected", expected,
                 "--command", self.artifact_command("sha256:" + "b" * 64))
        self.cli(1, "artifact", "--verified", self.base,
                 "--command", self.artifact_command(commit="f" * 40))

    def test_artifact_rejects_tags_errors_and_head_changes(self):
        self.cli(2, "artifact", "--verified", self.base, "--command", self.artifact_command("latest"))
        self.cli(2, "artifact", "--verified", self.base, "--command", "false | cat")
        self.cli(2, "artifact", "--verified", self.base, "--command", "printf '{}'" )
        self.changed_source()
        self.cli(2, "artifact", "--verified", self.base, "--command", self.artifact_command())

    def test_sync_fingerprint_tracks_non_status_updates(self):
        payload = dict(title="Task", body="Description", status="Testing", type="story",
                       priority="medium", parked="", parked_reason="", parent="1", gate_event="G5 PASS")
        path = self.root / "build/sync.json"
        self.write("build/sync.json", json.dumps(payload))
        previous = self.cli(0, "sync-fingerprint", "--input", str(path))["fingerprint"]
        for field, value in (("priority", "high"), ("parked", "human"), ("parked_reason", "No stand"),
                             ("title", "New title"), ("body", "New description"), ("gate_event", "G6 ERROR")):
            payload[field] = value
            self.write("build/sync.json", json.dumps(payload))
            current = self.cli(0, "sync-fingerprint", "--input", str(path))["fingerprint"]
            self.assertNotEqual(previous, current)
            previous = current
        payload.pop("parked_reason")
        self.write("build/sync.json", json.dumps(payload))
        self.cli(2, "sync-fingerprint", "--input", str(path))


class HealthTests(unittest.TestCase):
    def args(self):
        return gates.parser().parse_args(["health", "--url", "http://localhost/health",
                                          "--attempts", "2", "--interval", "0"])

    def test_unhealthy_retries_end_with_failure(self):
        with patch.object(gates.urllib.request, "build_opener") as factory:
            factory.return_value.open.side_effect = gates.urllib.error.URLError("refused")
            self.assertEqual("FAIL", gates.health(self.args())["status"])
            self.assertEqual(2, factory.return_value.open.call_count)

    def test_health_recovers_on_later_attempt(self):
        with patch.object(gates.urllib.request, "build_opener") as factory:
            response = unittest.mock.MagicMock()
            response.__enter__.return_value.status = 200
            factory.return_value.open.side_effect = [gates.urllib.error.URLError("refused"), response]
            self.assertEqual("PASS", gates.health(self.args())["status"])

    def test_health_does_not_follow_login_redirect(self):
        redirect = gates.NoRedirect()
        self.assertIsNone(redirect.redirect_request(None, None, 302, "", {}, "/login"))


if __name__ == "__main__":
    unittest.main()
