---
description: "Kanban: Test. Реальная верификация: тестировщик поднимает стенд, прогоняет AC по живой реализации, заводит баги на провалы и возвращает story на доработку. E2E — отдельный /e2e. Unit тесты — developer (G4). Примеры: /test #102 | /test #102 #104 #105 | /test all"
argument-hint: "<#N issue | несколько через пробел | all>"
---

# KANBAN — Testing: $ARGUMENTS

Запускает **qa-lead** который координирует **test-case-writer** (QA-инженер) для каждой story:
- **test-case-writer**: строит TC из AC → **поднимает реальный стенд** (local_env.up / Testcontainers / degraded) → **прогоняет каждый AC по живой реализации** (curl/REST: happy/RBAC/error/persistence) → перепрогоняет автотесты по факту → **заводит Bug issue на каждый провал** → возвращает story в разработку (замыкает петлю).

> **E2E автотесты** — отдельный ручной процесс. Запускать через `/e2e #N`.
> **Unit тесты** — ответственность DEVELOPER (G4). QA их **перепрогоняет** и подтверждает зелёное по факту, но не пишет.
> **Security review** — выполняется dev-lead до перехода в Testing (поле Security=passed обязательно).
> Смену Status и поле QA владеет qa-lead; баги заводит тестировщик (у него evidence).

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
Agent(subagent_type="qa-lead", prompt="Verify stories: $ARGUMENTS on a real stand.

Read .claude/project-profile.md FIRST (commands.*, stack.data.*, topology.services[], quality.*; if initialized: false — run its Fallback Detect), then CLAUDE.md and ARCHITECTURE.md (if exists).

QA TEAM — для КАЖДОЙ story запускай test-case-writer (реальная верификация, не только документация):
- test-case-writer: TC из AC → поднять стенд (local_env.up→Testcontainers→degraded) → прогнать КАЖДЫЙ AC по живой системе (curl/REST) → перепрогнать автотесты по факту → завести Bug issue на каждый провал → living QA report + traceability
- E2E автотесты НЕ входят в QA-петлю — запускать отдельно через /e2e

If '$ARGUMENTS' == 'all':
  Get all: kanban_query \"Status\" \"Testing\"

Steps for EACH story:
1. Pre-flight: get issue + verify Security==passed (kb_get N Security) + check build passes (commands.backend.build)
2. Spawn test-case-writer (run_in_background=true for swarm mode) — прогон AC по стенду + баги на провалы
3. Wait for completion, прочитай вердикт (per-AC PASS/FAIL + evidence, stand level, autotests, bugs filed)
4. Quality Gate G6:
   PASS if: ВСЕ AC verified PASS on real stand (with evidence) + autotests re-run SUCCESS + build green + TC docs committed + Security==passed + (JavaReview in {passed,warning} IF backend-delta) + (FrontendReview in {passed,warning} IF frontend-delta) + unit coverage >= threshold
   (non-applicable review field stays pending = N/A, does not block)
   FAIL if: любой AC FAIL, или build/autotests сломаны (баги уже заведены тестировщиком; если нет — заведи сам)
   BLOCKED if: Security != passed OR an applicable review field is failed
5. PASS: kb_set {N} QA passed (+ kb_num {N} Coverage <pct>), then kanban_set {N} \"Ready to Deploy\"
   FAIL: kb_set {N} QA failed, then kanban_set {N} \"In Development\"  ← петля: developer чинит по багам, задача вернётся в Testing
   BLOCKED: keep Status=\"Testing\", comment reason

For MULTIPLE stories: test-case-writer for all stories run in parallel.
Priority: critical → high → medium → low. WIP limit: quality.wip_limit (default 5) in testing.

Important:
- DO NOT write unit tests — developer already did (re-run and confirm green, not rewrite)
- Integration tests только для допокрытия непокрытых AC на стенде уровня B (иначе зона developer)
- NO load tests (separate performance cycle)
- NO UI E2E tests — separate manual process via /e2e

Change Status ONLY via kanban_set; QA field via kb_set (helpers in .claude/agents/kanban-board-sync.md). Bugs — созданы тестировщиком.
Report: per story — stand level, {pass}/{total} AC verified, autotests SUCCESS/FAILED, VERDICT, bugs filed, Security field status.")
```

### ШАГ 3 — Финальный отчёт

```
TESTING COMPLETE
Team: qa-lead (test-case-writer — QA verification)
Mode: {single|swarm}

PASSED:
  #{N} — {pass}/{total} AC verified (stand A/B/C) | autotests SUCCESS | Security: PASS → Ready to Deploy

FAILED (петля → In Development):
  #{N} — AC-{P}-{seq} FAIL: {что не так} | Bugs: #{bug1} (severity)

BLOCKED:
  #{N} — {reason: Security≠passed / review failed}

Summary: {passed}/{total} passed · bugs filed: {count}
Next steps:
  /deploy #{N}      — deploy to staging (для PASSED)
  /develop #{bug1}  — исправить баги (для FAILED; или /orchestrate добьёт петлю сам)
  /e2e #{N}         — run UI E2E tests manually (optional)
```
