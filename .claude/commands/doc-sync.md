# doc-sync — Sync Documentation & Traceability

Generate/update the traceability matrix and validate spec↔code consistency.

## Steps

1. Launch **doc-sync** agent:

```
Agent(subagent_type="doc-sync", prompt="Run full documentation sync.
Read CLAUDE.md for project context.

1. Generate docs/traceability.md — scan all features, specs, arch docs, stories, code files, tests, PRs
2. Validate spec↔code consistency for features changed in last 10 commits
3. Mark stale docs
4. Report inconsistencies

Working directory: $CWD")
```

## Output

- `docs/traceability.md` — updated traceability matrix
- Console report of inconsistencies and stale docs
