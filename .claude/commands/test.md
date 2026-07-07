---
description: "Kanban: Test. TC документация из specs. E2E — отдельный ручной процесс (/e2e). Unit тесты — ответственность developer (G4). Примеры: /test #102 | /test #102 #104 #105 | /test all"
argument-hint: "<#N issue | несколько через пробел | all>"
---

# KANBAN — Testing: $ARGUMENTS

Запускает **qa-lead** который координирует **test-case-writer** для каждой story:
- **test-case-writer**: TC документация из specs/arch docs, cross-reference sync

> **E2E автотесты** — отдельный ручной процесс. Запускать через `/e2e #N`.
> **Unit тесты** — ответственность DEVELOPER, написаны на ЭТАПЕ 3 (coverage >= quality.unit_coverage_min из профиля, default 95% — проверен в G4).
> **Security review** — выполняется dev-lead до перехода в Testing (поле Security=passed обязательно).
> QA проверяет unit coverage из handoff и поля Security/JavaReview/FrontendReview (`kb_get N Security` и т.д.), но не пишет их.

## Алгоритм

### ШАГ 1 — Определи scope

```
Read(".claude/project-profile.md")  # ПЕРВЫМ: команды из commands.*, пороги из quality.*; если initialized: false — Fallback Detect из профиля
Read("CLAUDE.md")
```

- Если `all` → все issues в колонке "Testing" (kanban_query "Status" "Testing")
- Если номер(а) → конкретные issues

### ШАГ 2 — Запуск QA Team Lead

```
Agent(subagent_type="qa-lead", prompt="Test stories: $ARGUMENTS.

Read .claude/project-profile.md FIRST (commands from commands.*, thresholds from quality.*; if initialized: false — run its Fallback Detect), then CLAUDE.md and ARCHITECTURE.md (if exists).

QA TEAM — для КАЖДОЙ story запускай test-case-writer:
- test-case-writer: TC документация из spec/arch, cross-reference sync
- E2E автотесты НЕ входят в QA pipeline — запускать отдельно через /e2e

If '$ARGUMENTS' == 'all':
  Get all: kanban_query "Status" "Testing"

Steps for EACH story:
1. Pre-flight: get issue + verify Security==passed (kb_get N Security) + check build passes (commands.backend.build from profile)
2. Spawn test-case-writer (run_in_background=true for swarm mode)
3. Wait for completion
4. Quality Gate G6:
   PASS if: TC docs created + Security==passed + (JavaReview in {passed,warning} IF backend-delta) + (FrontendReview in {passed,warning} IF frontend-delta) + unit coverage >= quality.unit_coverage_min (default 95%) confirmed from handoff
   (non-applicable review field stays pending = N/A, does not block)
   NEEDS WORK if: TC docs incomplete
   BLOCKED if: Security != passed OR an applicable review field is failed/pending (request dev-lead review)
5. PASS: kb_set {N} QA passed (+ kb_num {N} Coverage <pct>), then kanban_set {N} "Ready to Deploy"
   FAIL: kb_set {N} QA failed, then kanban_set {N} "In Development"
   BLOCKED: keep Status="Testing", comment reason

For MULTIPLE stories: test-case-writer for all stories run in parallel.
Priority: critical → high → medium → low.
WIP limit: quality.wip_limit (default 5) stories in testing.

Important:
- DO NOT write unit tests — developer already did (verify from handoff, not rewrite)
- NO integration tests (базового integration-класса проекта достаточно — developer уже использовал его; если такого класса нет, это зона developer, не QA)
- NO load tests (separate performance cycle)
- NO E2E tests — separate manual process via /e2e

Change stages ONLY via kanban_set (helpers in .claude/agents/kanban-board-sync.md).
Report: pass/fail per story, TC count, E2E compile/runtime status, Security field status.")
```

### ШАГ 3 — Финальный отчёт

```
TESTING COMPLETE
Team: qa-lead (test-case-writer)
Mode: {single|swarm}

PASSED:
  #{N} — TCs: {N} ({N} critical) | Security: PASS

FAILED:
  #{N} — {reason} | Bugs: #{bug1}

BLOCKED:
  #{N} — {reason}

Summary: {passed}/{total} passed
Next steps:
  /deploy #{N}   — deploy to staging
  /e2e #{N}      — run E2E tests manually (optional)
```
