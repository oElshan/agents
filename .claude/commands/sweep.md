---
description: "Kanban: Sweep. Автопилот right-to-left (последовательно). Примеры: /sweep | /sweep ready-for-dev | /sweep testing | /sweep dry-run"
argument-hint: "<пусто=всё | backlog | ready-for-dev | testing | ready-to-deploy | dry-run>"
---

# SWEEP — Kanban Autopilot: $ARGUMENTS

Автоматически обработай все накопившиеся задачи на Kanban-доске через **Team Leads**. Принцип **right-to-left**: сначала завершаем то, что ближе к готовности.

**ВАЖНО**: Стадию задачи Team Leads меняют ТОЛЬКО через `kanban_set N "Status"`.

**Профиль проекта**: сначала прочитай `.claude/project-profile.md` — команды build/test/deploy
бери из `commands.*`, пороги из `quality.*` (`wip_limit`, `unit_coverage_min`); если
`initialized: false` — выполни Fallback Detect из этого же файла.

---

## Шаг 1 — Сканирование доски

Получи все открытые issues по каждой колонке (поле Status). Хелперы из
`.claude/agents/kanban-board-sync.md`:

```
kanban_query "Status" "Deploy"
kanban_query "Status" "Ready to Deploy"
kanban_query "Status" "Testing"
kanban_query "Status" "Code Review"
kanban_query "Status" "In Development"
kanban_query "Status" "Ready for Dev"
kanban_query "Status" "Analysis"
kanban_query "Status" "Backlog"
```

Сортируй по полю Priority: critical → high → medium → low.

---

## Шаг 2 — WIP и capacity

```
wip_limit = quality.wip_limit из .claude/project-profile.md (default 5)
dev_capacity = wip_limit - count(kanban_query "Status" "In Development")
test_capacity = wip_limit - count(kanban_query "Status" "Testing")
```

---

## Шаг 3 — Разбор аргумента

| Аргумент | Режим | Scope |
|----------|-------|-------|
| *(пусто)* | Полный sweep | Все колонки right-to-left |
| `dry-run` | Только план | Показать что будет сделано, БЕЗ выполнения |
| `ready-to-deploy` | Одна колонка | Только deploy |
| `testing` | Одна колонка | Только testing |
| `ready-for-dev` | Одна колонка | Только development |
| `backlog` | Одна колонка | Только analysis |

### Если dry-run — выведи план и СТОП:

```
SWEEP DRY-RUN — {date}

WIP Status:
  In Development: {count}/{wip_limit} (capacity: {dev_capacity})
  Testing: {count}/{wip_limit} (capacity: {test_capacity})

Plan (right-to-left, via Team Leads):

  DEPLOY ({count}):
    → #{N} {title} — ops-lead → devops (Deploy → Done)
  READY-TO-DEPLOY ({count}):
    → #{N} {title} — ops-lead → devops (Ready to Deploy → Deploy)
  TESTING ({count}):
    → #{N} {title} — qa-lead → test-case-writer
  CODE REVIEW ({count}):
    → #{N} {title} — dev-lead → security-reviewer + java-reviewer + frontend-reviewer (по delta) (Code Review → Testing)
  IN-DEVELOPMENT ({count}):
    → #{N} {title} — dev-lead → developer (In Development → Code Review)
  READY-FOR-DEV ({count}):
    → #{N} {title} — dev-lead → developer
    SKIPPED #{N} {title} — (WIP limit)
  ANALYSIS ({count}):
    → #{N} {title} — analysis-lead → analyst + architect
  BACKLOG ({count}):
    → #{N} {title} — analysis-lead → analyst + architect

Total: {will_process} to process, {skipped} skipped
```

**После dry-run — СТОП.**

---

## Шаг 4 — Deploy (Ops Team Lead)

Если есть issues в ready-to-deploy:

```
Agent(subagent_type="ops-lead", prompt="SWEEP: Deploy all Ready to Deploy issues.
Read .claude/project-profile.md (commands.* / quality.*), CLAUDE.md and ARCHITECTURE.md (if exists).
Get issues: kanban_query 'Status' 'Ready to Deploy' (then keep only those where kb_get N QA == passed)
Flow per issue: Ready to Deploy → (G7 pre-flight) → Deploy → (G8) → Done.
Run devops agent to:
1. G7 pre-flight checks (QA=passed, Security=passed, build green)
2. kanban_set #{N} 'Deploy'
3. Build + staging deploy: команда commands.deploy.staging из профиля (например helm upgrade --install / kustomize / kubectl apply); затем commands.deploy.status (kubectl rollout status) для каждого затронутого сервиса
4. Health checks (G8): topology.services[].health каждого затронутого сервиса; при провале — rollback командой commands.deploy.rollback
5. kanban_set #{N} 'Done' (закрытие внутри), kb_set #{N} Deploy staging
6. Close parent features if all stories done
7. Меняй стадию ТОЛЬКО через kanban_set; гейты/статусы — через хелперы из .claude/agents/kanban-board-sync.md.
Report: deployed issues, health status.")
```

---

## Шаг 5 — Testing (QA Team Lead)

Если есть issues в testing:

```
Agent(subagent_type="qa-lead", prompt="SWEEP: Test all issues in column Testing.
Read .claude/project-profile.md (commands.* / quality.*), CLAUDE.md and ARCHITECTURE.md (if exists).
Get issues: kanban_query 'Status' 'Testing'
Check dependencies (Blocked by/Depends on) — skip BLOCKED issues.

For EACH issue run TWO agents IN PARALLEL:
- test-case-writer: TC documentation from spec/arch, cross-reference sync
- e2e-tester (opus): E2E Java tests (Playwright+JUnit5+POM), compile + run on live system

Pre-flight per issue:
1. Verify kb_get N Security == passed (set by dev-lead). If not → BLOCKED (do not proceed).
2. Check build passes.
3. Confirm unit coverage >= quality.unit_coverage_min (default 95%) from developer handoff (.claude/handoffs/story-{N}-dev.md).

PASSED: kb_set #{N} QA passed, kanban_set #{N} 'Ready to Deploy'.
FAILED: kb_set #{N} QA failed + create Bug issue, kanban_set #{N} 'In Development'.
BLOCKED (Security != passed): keep stage Testing, comment reason.
WIP limit: quality.wip_limit (default 5)
Меняй стадию ТОЛЬКО через kanban_set; гейты/статусы — через хелперы из .claude/agents/kanban-board-sync.md.
Report: pass/fail per issue, TC count, E2E compile/runtime status, Security field status, BLOCKED issues.")
```

---

## Шаг 6 — Development (Dev Team Lead)

Если есть issues в ready-for-dev И dev_capacity > 0:

```
Agent(subagent_type="dev-lead", prompt="SWEEP: Develop up to {dev_capacity} stories from Ready for Dev.
Read .claude/project-profile.md (commands.* / quality.*), CLAUDE.md and ARCHITECTURE.md (if exists).
Get issues: kanban_query 'Status' 'Ready for Dev'
Sort by field Priority. Take top {dev_capacity} issues.
Check dependencies (Blocked by/Depends on) — skip BLOCKED stories.
Run developer agents:
- Independent stories → PARALLEL (swarm)
- Dependent stories → sequential
Each developer: branch → implement → tests → build → commit (STAYS in In Development).
Then dev-lead drives each story to Testing through Code Review:
  G4 → kanban_set #{N} 'Code Review' → reviewers по delta IN PARALLEL: security-reviewer (всегда) + java-reviewer (если в delta есть backend-файлы) + frontend-reviewer (если в delta есть frontend-файлы) → G5 (Security=passed И JavaReview∈{passed,warning} ЕСЛИ backend-delta И FrontendReview∈{passed,warning} ЕСЛИ frontend-delta; неприменимый reviewer не запускается, его поле остаётся pending — «N/A» в Gate Report) → kanban_set #{N} 'Testing'.
WIP limit: quality.wip_limit (default 5)
Меняй стадию ТОЛЬКО через kanban_set.
Report: branches, files, build status per story, BLOCKED stories.")
```

---

## Шаг 7 — Analysis (Analysis Team Lead)

Если есть issues в backlog:

```
Agent(subagent_type="analysis-lead", prompt="SWEEP: Analyze all features in column Backlog.
Read .claude/project-profile.md (commands.* / quality.*), CLAUDE.md and ARCHITECTURE.md (if exists).
Get issues: kanban_query 'Status' 'Backlog'
For each feature:
1. Run analyst: decompose into stories, write spec
2. Run architect: arch doc, stubs, API contract
Multiple features → run analysts in PARALLEL, then architects in PARALLEL
Меняй стадию ТОЛЬКО через kanban_set.
Report: features analyzed, stories created, specs and arch docs.")
```

---

## Шаг 8 — Финальный отчёт

```
SWEEP COMPLETE — {date}
Mode: Team Leads

PROCESSED (right-to-left):

  OPS LEAD → DONE:
    #{N} — deployed to staging

  QA LEAD → READY-TO-DEPLOY / IN-DEVELOPMENT:
    #{N} — QA=passed
    #{N} — QA=failed, bugs: #{bug}

  DEV LEAD → TESTING:
    #{N} — developed

  ANALYSIS LEAD → READY-FOR-DEV:
    #{N} — {count} stories created

SKIPPED (WIP):
  #{N} — dev WIP full

BLOCKED (dependencies):
  🚫 #{N} — blocked by #{M} (not resolved)

SUMMARY:
  Processed: {count}
  Skipped (WIP): {count}
  Blocked (deps): {count}
  Security issues: {count}
  Errors: {count}
  WIP: Dev {count}/{wip_limit} | Test {count}/{wip_limit}

NEXT ACTIONS:
  {recommendations}
```
