#!/usr/bin/env python3
"""Local gate checks. Python 3.9+, standard library only.

stdout: one JSON result. Exit codes: 0 PASS, 1 FAIL, 2 ERROR.
This CLI checks evidence; it does not sandbox agents or own board transitions.
"""

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath


class GateError(Exception):
    pass


def result(status="PASS", **details):
    return dict(status=status, **details)


def path_arg(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or str(path) != value:
        raise GateError("Expected a normalized repository-relative path: " + value)
    return value


class Repo:
    def __init__(self):
        self.root = Path(self.git("rev-parse", "--show-toplevel").decode().strip())

    def git(self, *args):
        run = subprocess.run(["git", *args], cwd=getattr(self, "root", None),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run.returncode:
            raise GateError("git {} failed (exit {})".format(args[0], run.returncode))
        return run.stdout

    def commit(self, ref):
        if not ref or ref.startswith("-"):
            raise GateError("Invalid commit reference")
        return self.git("rev-parse", "--verify", "--end-of-options",
                        ref + "^{commit}").decode().strip()

    def ancestor(self, base, head):
        run = subprocess.run(["git", "merge-base", "--is-ancestor", base, head],
                             cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run.returncode not in (0, 1):
            raise GateError("git merge-base failed")
        return run.returncode == 0

    def changes(self, base, head, *paths, existing_only=False):
        args = ["diff", "--no-ext-diff", "--no-renames", "--name-only", "-z"]
        if existing_only:
            args.append("--diff-filter=ACMT")
        data = self.git(*args, base, head, "--", *paths)
        return [p.decode("utf-8") for p in data.split(b"\0") if p]

    def entry(self, ref, path):
        data = self.git("ls-tree", "-z", ref, "--", ":(literal)" + path)
        if not data:
            return None
        meta, name = data.rstrip(b"\0").split(b"\t", 1)
        if name.decode() != path:
            raise GateError("Ambiguous git path: " + path)
        mode, kind, oid = meta.decode().split()
        return mode, kind, oid

    def blob(self, ref, path):
        entry = self.entry(ref, path)
        if not entry or entry[0] not in ("100644", "100755") or entry[1] != "blob":
            raise GateError("Missing regular tracked file: " + path)
        return self.git("cat-file", "blob", entry[2])

    def clean(self, head):
        if self.commit("HEAD") != head:
            raise GateError("HEAD changed or does not match the requested commit")
        if self.git("status", "--porcelain", "--untracked-files=all"):
            raise GateError("Working tree is not clean")


def freshness(args):
    repo = Repo()
    verified, head = repo.commit(args.verified), repo.commit(args.head)
    if not repo.ancestor(verified, head):
        return result("FAIL", reason="Verified commit is not an ancestor of HEAD")
    changed = repo.changes(verified, head)
    if args.qa_report:
        path = path_arg(args.qa_report)
        if not path.startswith("docs/qa/") or not path.endswith(".md"):
            raise GateError("QA exception must name one Markdown file in docs/qa/")
        if path in changed:
            current = repo.entry(head, path)
            previous = repo.entry(verified, path)
            # Only a regular documentation file may use the exception.
            if current and current[0] == "100644" and (not previous or previous[0] == "100644"):
                changed.remove(path)
    return result("FAIL" if changed else "PASS", verified_commit=verified,
                  head_commit=head, changed=changed)


def contract(args):
    expected_hash(args.expected)
    repo = Repo()
    ref = repo.commit(args.ref)
    paths = [path_arg(args.spec), path_arg(args.arch), ".agents/profile.md", "AGENTS.md",
             "docs/arch/budget.md", "docs/arch/ownership-map.md"]
    entries = {}
    for path in paths:
        repo.blob(ref, path)
        entries[path] = repo.entry(ref, path)
    for path in ("opencode.json", "opencode.jsonc"):
        if repo.entry(ref, path):
            repo.blob(ref, path)
            entries[path] = repo.entry(ref, path)
    policy = repo.git("ls-tree", "-r", "-z", ref, "--", ".opencode/")
    if not policy:
        raise GateError("No tracked .opencode policy files")
    for row in policy.split(b"\0"):
        if not row:
            continue
        meta, path = row.split(b"\t", 1)
        entry = tuple(meta.decode().split())
        if entry[0] not in ("100644", "100755") or entry[1] != "blob":
            raise GateError("Policy contains a non-regular file")
        entries[path.decode()] = entry
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    snapshot = hashlib.sha256(encoded).hexdigest()
    return result("FAIL" if args.expected and args.expected != snapshot else "PASS",
                  commit=ref, snapshot=snapshot, spec_sha=entries[args.spec][2], files=entries)


def parse_xml(data):
    # ElementTree does not fetch external DTDs. Reject internal entities explicitly.
    if b"<!ENTITY" in data.upper() or re.search(br"<!DOCTYPE[^>]*\[", data, re.I):
        raise GateError("XML entities and internal DTDs are unsupported")
    return ET.fromstring(data)


def run_profile(command, cwd):
    if not command or not command.strip():
        raise GateError("Required profile command is empty")
    # The command is supplied explicitly from the trusted project profile.
    return subprocess.run(["bash", "-e", "-o", "pipefail", "-c", command],
                          cwd=cwd, stdout=sys.stderr, stderr=sys.stderr).returncode


def source_maps(values):
    maps = {}
    for value in values:
        root, sep, report = value.partition("=")
        if not sep or root in maps:
            raise GateError("Use unique --source ROOT=REPORT entries")
        maps[path_arg(root)] = path_arg(report)
    return maps


def coverage(args):
    repo = Repo()
    head, base = repo.commit(args.head), repo.commit(args.base)
    base = repo.git("merge-base", base, head).decode().strip()
    if not math.isfinite(args.minimum) or not 0 <= args.minimum <= 100:
        raise GateError("Coverage minimum must be between 0 and 100")
    maps = source_maps(args.source)
    files = repo.changes(base, head, existing_only=True)
    selected = {}
    for path in files:
        if not path.endswith((".java", ".kt")):
            continue
        roots = [root for root in maps if path.startswith(root + "/")]
        if not roots:
            if re.search(r"(^|/)src/(test|integrationTest|it|testFixtures)/", path):
                continue
            raise GateError("No coverage source mapping for " + path)
        if len(roots) != 1:
            raise GateError("Overlapping coverage source roots for " + path)
        root = roots[0]
        selected[path] = (maps[root], path[len(root) + 1:])
    if not selected:
        return result(applicable=False, reason="No changed production Java/Kotlin sources")
    repo.clean(head)
    reports = set(report for report, _ in selected.values())
    old_stats = {}
    for report in reports:
        path = repo.root / report
        if path.is_symlink() or not path.resolve().is_relative_to(repo.root):
            raise GateError("Report must be inside the repository: " + report)
        old_stats[report] = path.stat().st_mtime_ns if path.exists() else None
    started = time.time_ns()
    code = run_profile(args.command, repo.root)
    if code:
        return result("FAIL", reason="Coverage command failed", command_exit=code)
    repo.clean(head)
    indexes = {}
    for report in sorted(reports):
        path = repo.root / report
        if path.is_symlink() or not path.resolve().is_relative_to(repo.root) or not path.is_file():
            raise GateError("Missing regular coverage report: " + report)
        mtime = path.stat().st_mtime_ns
        if mtime < started or mtime == old_stats[report]:
            raise GateError("Coverage report was not regenerated: " + report)
        xml = parse_xml(path.read_bytes())
        if xml.tag != "report":
            raise GateError("Expected JaCoCo XML report: " + report)
        index = {}
        for package in xml.iter("package"):
            for source in package.findall("sourcefile"):
                key = "/".join(filter(None, (package.attrib["name"], source.attrib["name"])))
                if key in index:
                    raise GateError("Ambiguous source in report: " + key)
                counters = source.findall("counter[@type='LINE']")
                if len(counters) != 1:
                    raise GateError("Missing or duplicate LINE counter: " + key)
                missed, covered = (int(counters[0].attrib[name]) for name in ("missed", "covered"))
                if min(missed, covered) < 0 or missed + covered == 0:
                    raise GateError("No executable line evidence: " + key)
                index[key] = missed, covered
        indexes[report] = index
    missing = [path for path, (report, key) in selected.items() if key not in indexes[report]]
    if missing:
        return result("FAIL", reason="Changed sources absent from report", missing=missing)
    identities = list(selected.values())
    if len(set(identities)) != len(identities):
        raise GateError("Different source roots map to the same reported file")
    missed = sum(indexes[report][key][0] for report, key in identities)
    covered = sum(indexes[report][key][1] for report, key in identities)
    pct = 100 * covered / (missed + covered)
    return result("PASS" if pct >= args.minimum else "FAIL", tested_commit=head,
                  coverage=round(pct, 4), minimum=args.minimum, sources=sorted(selected))


def xml_node(node):
    # Ignore indentation between nodes, but retain leaf text (including SQL) exactly.
    text = node.text or ""
    if len(node) and not text.strip():
        text = ""
    return (node.tag, sorted(node.attrib.items()), text,
            [(xml_node(child), child.tail if (child.tail or "").strip() else "") for child in node])


def liquibase_append(repo, base, head, path):
    before, after = (parse_xml(repo.blob(ref, path)) for ref in (base, head))
    ns = "{http://www.liquibase.org/xml/ns/dbchangelog}"
    if before.tag not in ("databaseChangeLog", ns + "databaseChangeLog"):
        return False
    if (before.tag, before.attrib, (before.text or "").strip()) != (
            after.tag, after.attrib, (after.text or "").strip()):
        return False
    if len(after) <= len(before):
        return False
    if [xml_node(n) for n in before] != [xml_node(n) for n in list(after)[:len(before)]]:
        return False
    existing = {n.attrib.get("file") for n in before if n.tag in ("include", ns + "include")}
    for node in list(after)[len(before):]:
        if node.tag not in ("include", ns + "include") or len(node) or (node.text or "").strip():
            return False
        if set(node.attrib) != {"file", "relativeToChangelogFile"}:
            return False
        name = path_arg(node.attrib["file"])
        if name in existing or node.attrib["relativeToChangelogFile"] != "true":
            return False
        existing.add(name)
        target = str(PurePosixPath(path).parent / name)
        if repo.entry(base, target):
            return False
        repo.blob(head, target)
    return True


def migrations(args):
    repo = Repo()
    base, head = repo.commit(args.base), repo.commit(args.head)
    base = repo.git("merge-base", base, head).decode().strip()
    if not args.path:
        raise GateError("Migration pathspecs are required")
    failures = []
    changed = repo.changes(base, head, *args.path)
    for path in changed:
        previous, current = repo.entry(base, path), repo.entry(head, path)
        if not previous:
            repo.blob(head, path)
            continue
        if (args.tool == "liquibase" and path.endswith(".xml") and current
                and previous[0] == current[0] == "100644"
                and liquibase_append(repo, base, head, path)):
            continue
        failures.append(path)
    return result("FAIL" if failures else "PASS", changed=changed, immutable_files_changed=failures)


def logs(args):
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise GateError("A log retrieval command is required after --")
    run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         timeout=args.timeout)
    if run.returncode:
        return result("ERROR", reason="Could not retrieve logs", command_exit=run.returncode)
    content = run.stdout.decode("utf-8", errors="replace")
    matches = re.findall(r"error|exception|fatal", content, flags=re.I)
    # Do not print logs; they can contain secrets.
    return result("FAIL" if matches else "PASS", bytes=len(run.stdout), error_matches=len(matches))


def artifact(args):
    expected_hash(args.expected)
    repo = Repo()
    head = repo.commit(args.verified)
    repo.clean(head)
    if not args.command.strip():
        raise GateError("Artifact command is required")
    run = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", args.command],
                         cwd=repo.root, stdout=subprocess.PIPE, stderr=sys.stderr)
    if run.returncode:
        return result("ERROR", reason="Artifact command failed", command_exit=run.returncode)
    repo.clean(head)
    manifest = json.loads(run.stdout)
    if not isinstance(manifest, dict) or set(manifest) != {"commit", "artifacts"}:
        raise GateError("Manifest must contain only commit and artifacts")
    if manifest["commit"] != head:
        return result("FAIL", reason="Artifact commit differs from the verified commit")
    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, dict) or not artifacts:
        raise GateError("Artifact manifest is empty")
    for name, digest in artifacts.items():
        if not name or not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise GateError("Every artifact must have a SHA-256 digest")
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    fingerprint = hashlib.sha256(encoded).hexdigest()
    return result("FAIL" if args.expected and fingerprint != args.expected else "PASS",
                  manifest_sha=fingerprint, manifest=manifest)


def expected_hash(value):
    if value is not None and not re.fullmatch(r"[0-9a-f]{64}", value):
        raise GateError("Expected snapshot must be a non-empty SHA-256 hash")


def sync_fingerprint(args):
    payload = json.loads(Path(args.input).read_text())
    fields = {"title", "body", "status", "type", "priority", "parked", "parked_reason", "parent", "gate_event"}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise GateError("Sync payload must contain exactly: " + ", ".join(sorted(fields)))
    if not all(isinstance(value, str) for value in payload.values()):
        raise GateError("Sync payload values must be strings; use empty strings for absent values")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return result(fingerprint=hashlib.sha256(encoded).hexdigest())


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def health(args):
    url = urllib.parse.urlsplit(args.url)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
        raise GateError("Health URL must be HTTP(S) without credentials")
    if args.attempts < 1 or args.interval < 0 or args.timeout <= 0:
        raise GateError("Invalid health retry parameters")
    opener = urllib.request.build_opener(NoRedirect())
    for attempt in range(1, args.attempts + 1):
        try:
            with opener.open(args.url, timeout=args.timeout) as response:
                if 200 <= response.status < 300:
                    return result(attempts=attempt, http_status=response.status)
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        if attempt < args.attempts:
            time.sleep(args.interval)
    return result("FAIL", reason="Health did not return HTTP 2xx", attempts=args.attempts)


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="gate", required=True)
    p = sub.add_parser("freshness")
    p.add_argument("--verified", required=True)
    p.add_argument("--head", default="HEAD")
    p.add_argument("--qa-report")
    p = sub.add_parser("contract")
    p.add_argument("--ref", default="HEAD")
    p.add_argument("--spec", required=True)
    p.add_argument("--arch", required=True)
    p.add_argument("--expected")
    p = sub.add_parser("coverage")
    p.add_argument("--base", required=True)
    p.add_argument("--head", default="HEAD")
    p.add_argument("--source", action="append", default=[], metavar="ROOT=REPORT")
    p.add_argument("--command", default="")
    p.add_argument("--minimum", type=float, required=True)
    p = sub.add_parser("migrations")
    p.add_argument("--base", required=True)
    p.add_argument("--head", default="HEAD")
    p.add_argument("--tool", choices=("flyway", "liquibase"), required=True)
    p.add_argument("--path", action="append", default=[])
    p = sub.add_parser("logs")
    p.add_argument("--timeout", type=float, default=60)
    p.add_argument("command", nargs=argparse.REMAINDER)
    p = sub.add_parser("artifact")
    p.add_argument("--verified", required=True)
    p.add_argument("--command", required=True)
    p.add_argument("--expected")
    p = sub.add_parser("sync-fingerprint")
    p.add_argument("--input", required=True)
    p = sub.add_parser("health")
    p.add_argument("--url", required=True)
    p.add_argument("--attempts", type=int, default=24)
    p.add_argument("--interval", type=float, default=5)
    p.add_argument("--timeout", type=float, default=5)
    return root


def main():
    args = parser().parse_args()
    try:
        output = globals()[args.gate.replace("-", "_")](args)
    except (GateError, OSError, ValueError, KeyError, ET.ParseError, subprocess.TimeoutExpired) as error:
        output = result("ERROR", reason=str(error))
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return {"PASS": 0, "FAIL": 1, "ERROR": 2}[output["status"]]


if __name__ == "__main__":
    sys.exit(main())
