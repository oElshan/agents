"""Versioned Markdown specification graph. Standard library only; no YAML execution.

Frontmatter uses YAML scalars and JSON flow arrays (a deliberately small YAML subset).
Links are vault-relative Obsidian wikilinks, including the docs/specs prefix.
"""

import json
import re
from pathlib import PurePosixPath


def require(condition, message):
    if not condition:
        raise ValueError(message)


def metadata(text):
    require(text.startswith("---\n"), "Missing spec frontmatter")
    header, sep, body = text[4:].partition("\n---\n")
    require(sep, "Unclosed spec frontmatter")
    data = {}
    for line in header.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        key, colon, value = line.partition(":")
        require(colon and re.fullmatch(r"[a-z_]+", key), "Invalid frontmatter field")
        require(key not in data, "Duplicate frontmatter field: " + key)
        value = value.strip()
        if value.startswith(('[', '{', '"')) or value in ("null", "true", "false"):
            value = json.loads(value)
        data[key] = value
    return data, body


def link_path(link):
    require(isinstance(link, str), "Spec link must be a string")
    match = re.fullmatch(r"\[\[(docs/specs/[^\]#|]+)\]\]", link)
    require(match, "Use a full vault-relative wikilink without alias/anchor: " + link)
    path = match[1]
    if not path.endswith(".md"):
        path += ".md"
    require(str(PurePosixPath(path)) == path and ".." not in PurePosixPath(path).parts,
            "Non-normalized spec link: " + link)
    return path


def overlaps(left, right):
    """Scopes are literal paths or directory prefixes ending in /, never globs."""
    return left == right or (left.endswith("/") and right.startswith(left)) or (
        right.endswith("/") and left.startswith(right))


class Graph:
    def __init__(self, repo, ref):
        self.repo, self.ref = repo, ref
        self.nodes = {}
        ids = set()
        paths = repo.git("ls-tree", "-r", "--name-only", "-z", ref, "--", "docs/specs/")
        for raw in paths.split(b"\0"):
            if not raw or not raw.endswith(b".md"):
                continue
            path = raw.decode()
            text = repo.blob(ref, path).decode()
            if not re.search(r"^schema: spec/v1$", text, re.M):
                continue  # Archived monolithic specifications remain byte-for-byte intact.
            data, body = metadata(text)
            require(isinstance(data.get("id"), str) and isinstance(data.get("kind"), str),
                    path + ": id and kind must be strings")
            require(data["id"] not in ids, "Duplicate spec id: " + data["id"])
            ids.add(data["id"])
            data["body"] = body
            self.nodes[path] = data

    def refs(self, path, field):
        values = self.nodes[path].get(field, [])
        require(isinstance(values, list) and all(isinstance(v, str) for v in values),
                path + ": " + field + " must be a JSON array of strings")
        require(len(values) == len(set(values)), path + ": duplicate " + field)
        return [link_path(v) for v in values]

    def parent(self, path):
        value = self.nodes[path].get("parent")
        return link_path(value) if value else None

    def root(self, path):
        seen = set()
        while True:
            require(path in self.nodes, "Missing structured spec: " + path)
            require(path not in seen, "Parent cycle: " + path)
            seen.add(path)
            parent = self.parent(path)
            if not parent:
                return path
            path = parent

    def dependencies(self, path):
        deps = self.refs(path, "depends_on")
        if self.nodes[path]["kind"] == "correction":
            deps += [self.parent(path)] + self.refs(path, "corrects")
        return set(deps)

    def closure(self, path):
        """Approval inputs: ancestors + prerequisites, never unrelated siblings/descendants."""
        found = set()

        def visit(p):
            require(p in self.nodes, "Missing structured spec: " + p)
            if p in found:
                return
            found.add(p)
            parent = self.parent(p)
            if parent:
                visit(parent)
            for dep in self.dependencies(p):
                visit(dep)
            if p == path and self.nodes[p]["kind"] == "master":
                for child in self.refs(p, "stories"):
                    visit(child)

        visit(path)
        return sorted(found)

    def validate(self, selected):
        root = self.root(selected)
        family = {p for p in self.nodes if self.root(p) == root}
        # Validate the selected family and its prerequisite families.
        pending = list(family)
        while pending:
            p = pending.pop()
            for dep in self.dependencies(p):
                require(dep in self.nodes, "Dangling dependency: " + dep)
                if dep not in family:
                    family.add(dep)
                    pending.append(dep)
        ids, ac_ids = set(), set()
        for p in sorted(family):
            n = self.nodes[p]
            kind, ident = n.get("kind"), n.get("id", "")
            patterns = {"master": r"F[1-9][0-9]*", "story": r"F[1-9][0-9]*-S[1-9][0-9]*",
                        "correction": r"F[1-9][0-9]*-S[1-9][0-9]*-C[1-9][0-9]*"}
            require(kind in patterns and isinstance(ident, str) and re.fullmatch(patterns[kind], ident),
                    p + ": invalid kind/id")
            require(ident not in ids, "Duplicate spec id: " + ident)
            ids.add(ident)
            require(isinstance(n.get("title"), str) and n["title"].strip(), p + ": missing title")
            require("parent" in n and "depends_on" in n, p + ": missing parent/depends_on")
            if kind != "correction":
                require("corrects" not in n and "supersedes" not in n,
                        p + ": only corrections may replace acceptance criteria")
            if kind != "master":
                require("stories" not in n, p + ": only master may enumerate stories")
            parent = self.parent(p)
            if kind == "master":
                require(n["parent"] is None, p + ": master parent must be null")
                children = self.refs(p, "stories")
                require(children, p + ": every feature needs at least one story")
                require(not self.refs(p, "depends_on"), p + ": dependencies belong to stories")
                for child in children:
                    require(child in self.nodes and self.parent(child) == p and
                            self.nodes[child].get("kind") == "story", p + ": invalid story link")
            else:
                expected_kind = "master" if kind == "story" else "story"
                require(parent in self.nodes and self.nodes[parent].get("kind") == expected_kind,
                        p + ": invalid parent kind")
                require(ident.startswith(self.nodes[parent]["id"] + ("-S" if kind == "story" else "-C")),
                        p + ": id does not match parent")
                if kind == "story":
                    require(p in self.refs(parent, "stories"), p + ": missing master backlink")
                for field in ("depends_on", "blockers", "writes", "reads", "resources"):
                    require(field in n and isinstance(n[field], list) and
                            all(isinstance(v, str) and v.strip() for v in n[field]), p + ": invalid " + field)
                    require(len(n[field]) == len(set(n[field])), p + ": duplicate " + field)
                require(n["writes"], p + ": declare write scope")
                for scope in n["writes"] + n["reads"]:
                    normalized = scope.rstrip("/")
                    require(normalized and not scope.startswith("/") and
                            ".." not in PurePosixPath(normalized).parts and
                            str(PurePosixPath(normalized)) == normalized and
                            not any(c in scope for c in "*?[]\\"), p + ": invalid literal scope")
                matches = list(re.finditer(r"^### (AC-[A-Za-z0-9-]+)(?:\s|$)", n["body"], re.M))
                require(matches, p + ": missing acceptance criteria")
                for i, match in enumerate(matches):
                    ac = match[1]
                    require(re.fullmatch(r"AC-" + re.escape(ident) + r"-[0-9]{2,}", ac), p + ": AC namespace mismatch")
                    require(ac not in ac_ids, "Duplicate AC: " + ac)
                    ac_ids.add(ac)
                    block = n["body"][match.end():matches[i + 1].start() if i + 1 < len(matches) else len(n["body"])]
                    for label in ("Given", "When", "Then"):
                        require(re.search(r"^" + label + r"\s+\S", block, re.M), ac + ": missing " + label)
                    require(re.search(r"^Проверка: (stand|integration|unit)\s*$", block, re.M), ac + ": missing verification mode")
            if kind == "master":
                require(not re.search(r"^### AC-", n["body"], re.M), p + ": AC belong in story specs")
            for dep in self.dependencies(p):
                require(dep != p and dep in self.nodes and self.nodes[dep].get("kind") != "master",
                        p + ": invalid prerequisite")
            if kind == "correction":
                corrected = self.refs(p, "corrects")
                require(corrected, p + ": correction must identify previous behavior")
                for old in corrected:
                    require(old == parent or (old in self.nodes and self.nodes[old].get("kind") == "correction"
                                             and self.parent(old) == parent), p + ": correction crosses story boundary")
                supersedes = n.get("supersedes")
                require(isinstance(supersedes, list) and supersedes and
                        all(isinstance(ac, str) for ac in supersedes), p + ": list superseded AC")
                require(len(supersedes) == len(set(supersedes)), p + ": duplicate superseded AC")
                old_ac = set()
                for old in corrected:
                    old_ac.update(re.findall(r"^### (AC-[A-Za-z0-9-]+)(?:\s|$)", self.nodes[old]["body"], re.M))
                require(set(supersedes) <= old_ac, p + ": unknown superseded AC")
        visiting, visited = set(), set()

        def visit(p):
            require(p not in visiting, "Dependency cycle: " + p)
            if p in visited:
                return
            visiting.add(p)
            for dep in self.dependencies(p):
                visit(dep)
            visiting.remove(p)
            visited.add(p)

        for p in family:
            visit(p)
        # Two corrections cannot replace the same AC independently.
        replacements = {}
        for p in family:
            for ac in self.nodes[p].get("supersedes", []):
                require(ac not in replacements, "Competing corrections for " + ac)
                replacements[ac] = p
        return sorted(family)

    def conflicts(self, left, right):
        a, b = self.nodes[left], self.nodes[right]
        reasons = sorted(set(a["resources"]) & set(b["resources"]))
        for w in a["writes"]:
            for other in b["writes"] + b["reads"]:
                if overlaps(w, other):
                    reasons.append(w + " <> " + other)
        for w in b["writes"]:
            for other in a["reads"]:
                if overlaps(w, other):
                    reasons.append(w + " <> " + other)
        return sorted(set(reasons))

    def effective(self, selected, integrated, include=None):
        family = self.validate(selected)
        by_id = {n["id"]: p for p, n in self.nodes.items()}
        requested = list(integrated) + ([include] if include else [])
        require(len(requested) == len(set(requested)), "Duplicate effective unit")
        for ident in requested:
            require(ident in by_id and self.nodes[by_id[ident]]["kind"] != "master", "Unknown unit: " + ident)
        paths = {by_id[i] for i in requested}
        for p in paths:
            require(self.dependencies(p) <= paths, "Effective unit has unmet prerequisites: " + p)
        ac, superseded = {}, set()
        root = self.root(selected)
        for p in sorted(paths & set(family)):
            if self.root(p) != root:
                continue
            for ident in re.findall(r"^### (AC-[A-Za-z0-9-]+)(?:\s|$)", self.nodes[p]["body"], re.M):
                ac[ident] = p
            superseded.update(self.nodes[p].get("supersedes", []))
        return dict(active_ac={k: v for k, v in ac.items() if k not in superseded},
                    superseded=sorted(superseded), units=sorted(requested))

    def plan(self, selected, completed, active, resolved, limit, candidates=None):
        family = self.validate(selected)
        by_id = {n["id"]: p for p, n in self.nodes.items()}
        require(limit > 0, "Parallel limit must be positive")
        require(not set(completed) & set(active), "A unit cannot be both active and completed")
        for ident in completed + active:
            require(ident in by_id and self.nodes[by_id[ident]]["kind"] != "master", "Unknown unit: " + ident)
        for ident in candidates or []:
            require(ident in by_id and by_id[ident] in family and self.nodes[by_id[ident]]["kind"] != "master",
                    "Unknown candidate: " + ident)
        done = {by_id[i] for i in completed}
        running = [by_id[i] for i in active]
        for i, p in enumerate(running):
            require(self.dependencies(p) <= done, "Active unit has unmet dependencies: " + p)
            require(set(self.nodes[p]["blockers"]) <= set(resolved), "Active unit has unresolved blockers: " + p)
            for other in running[:i]:
                require(not self.conflicts(p, other), "Active units conflict: " + p + " / " + other)
        selected_units, blocked = [], {}
        order = {ident: i for i, ident in enumerate(candidates or [])}
        for p in sorted(family, key=lambda p: (order.get(self.nodes[p]["id"], len(order)), self.nodes[p]["id"])):
            n = self.nodes[p]
            if n["kind"] == "master" or p in done or p in running:
                continue
            if candidates is not None and n["id"] not in candidates:
                continue
            reasons = ["depends_on:" + self.nodes[d]["id"] for d in sorted(self.dependencies(p) - done)]
            reasons += ["blocker:" + b for b in n["blockers"] if b not in resolved]
            for other in running + selected_units:
                reasons += ["conflict:" + self.nodes[other]["id"] + ":" + r for r in self.conflicts(p, other)]
            if len(running) + len(selected_units) >= limit:
                reasons.append("capacity")
            if reasons:
                blocked[n["id"]] = reasons
            else:
                selected_units.append(p)
        return {"ready": [self.nodes[p]["id"] for p in selected_units], "blocked": blocked,
                "active": active, "completed": completed}
