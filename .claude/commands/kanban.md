---
description: "Kanban: Full Pipeline. Фича от идеи до деплоя (5 этапов). Примеры: /kanban Audit Logging Service | /kanban #52"
argument-hint: "<описание фичи или #N существующего issue>"
---

# KANBAN — Full Pipeline: $ARGUMENTS

Запусти ПОЛНЫЙ Kanban pipeline для указанной фичи. Каждый этап управляется **Team Lead**, который координирует своих агентов. Этапы выполняются **последовательно** с Quality Gates между ними.

> **Альтернатива**: Для параллельной обработки НЕСКОЛЬКИХ фич/stories используй `/swarm`.
> `/kanban` — одна фича от начала до конца. `/swarm` — массовая параллельная обработка.

---

## Архитектура агентов

```
                        ┌─────────────────────────────────────────────┐
                        │              KANBAN PIPELINE                │
                        └─────────────────────────────────────────────┘
                                          │
    ┌──────────┬──────────────┬───────────┴──────────┬────────────────┐
    ▼          ▼              ▼                      ▼                ▼
 ЭТАП 1    ЭТАП 2         ЭТАП 3                ЭТАП 4           ЭТАП 5
 Feature   Analysis       Development           Testing          Deploy
    │          │              │                      │                │
 analyst   analysis-lead  dev-lead              qa-lead          ops-lead
              │  │            │  │              │       │             │
           analyst architect  │  security   tc-writer   devops
           (sonnet)(opus)  developer(s)  (sonnet)   (sonnet)  (sonnet)
                              (opus,unit tests)
```

**Разделение ответственности:**
- **developer** (ЭТАП 3): код + unit тесты (coverage >= quality.unit_coverage_min из профиля, default 95%) — G4 gate (In Development → Code Review)
- **security-reviewer + java-reviewer + frontend-reviewer (по delta)** (ЭТАП 3, статус Code Review): review — G5 gate (Code Review → Testing)
- **qa-lead** (ЭТАП 4): TC документация — G6 gate. E2E — отдельный ручной процесс (`/e2e`)
- **ops-lead** (ЭТАП 5): G7 (Ready to Deploy → Deploy) + G8 (Deploy → Done)

**Quality Gates**: G1 → G2 → G3 → G4 → G5 → G6 → G7 → G8 (см. `.claude/agents/quality-gates.md`)

---

## ЭТАП 1 — Feature Request (analyst)

Используй агента **analyst** напрямую:

1. Прочитай `.claude/project-profile.md` ПЕРВЫМ (стек, топология, команды из `commands.*`, пороги из `quality.*`; если `initialized: false` — Fallback Detect из профиля), затем `CLAUDE.md` и `ARCHITECTURE.md` (если есть)
2. Проверь дубликаты в GitHub Issues
3. Создай Feature Request Issue (без лейблов — всё в поля доски):
   - Title: `[FEATURE] {name}`
   - Стадия: `kanban_set {N} "Backlog"` (доска — источник правды о стадии)
   - Метаданные: `kb_meta {N} type=feature priority={level} size={est} component={type}`
   - Body: бизнес-ценность, user scenarios, acceptance criteria
4. Определи приоритет и размер

**Quality Gate G1**: бизнес-ценность определена, AC есть, дубликатов нет.

**Жди завершения перед следующим этапом.**

---

## ЭТАП 2 — Analysis (Analysis Team Lead)

Используй **analysis-lead** — он координирует analyst (sonnet) + architect (opus):

```
Agent(subagent_type="analysis-lead", prompt="Analyze feature #{N} '{title}'.
Read .claude/project-profile.md FIRST (stack/topology/commands source of truth; if initialized: false — run its Fallback Detect), then CLAUDE.md and ARCHITECTURE.md (if exists).

Run your team:
1. analyst (sonnet): decompose feature into User Stories (separate issues)
   - Метаданные каждой story (поля, без лейблов): kb_meta {story} type=story component={type} size={est} priority={level}
   - Стадия каждой story: kanban_set {story} "Ready for Dev"
   - Write spec: docs/specs/feature-{N}-{name}.md
   - Each story must be INVEST-compliant
2. architect (opus): create architecture design
   - Arch doc: docs/arch/feature-{N}-{name}.md
   - Define entities, services, controllers, DTOs per project stack from project-profile.md (stack.*, topology.services)
   - Create stub files with TODO markers
   - API contract, data model, migration strategy
3. Update parent feature with story links and doc links
4. Quality Gate G2: spec exists, stories INVEST, arch doc ready
5. Менять стадию ТОЛЬКО через kanban_set (доска — источник правды).

Report: story issues created, spec path, arch path.")
```

**Жди завершения перед следующим этапом.**

---

## ЭТАП 3 — Development (Dev Team Lead)

Используй **dev-lead** — он координирует developer(ов) (opus):

```
Agent(subagent_type="dev-lead", prompt="Develop ALL stories for feature #{N}.
Stories: #{s1}, #{s2}, #{s3} (from analysis step).
Read .claude/project-profile.md FIRST (commands from commands.*, thresholds from quality.*; if initialized: false — run its Fallback Detect), then CLAUDE.md and ARCHITECTURE.md (if exists), spec and arch docs.

Run your team:
- For each story, spawn developer agent (opus, isolation: worktree)
- Independent stories (different components) → PARALLEL
- Dependent stories (shared entities) → SEQUENTIAL
- WIP limit: max quality.wip_limit (default 5) in-development
- Each developer:
  1. Quality Gate G3: spec available, AC testable, deps resolved
  2. Branch: story/{story}-{short-name} from the feature branch (feature/{N}-{slug} is branched from github.default_branch per profile)
  3. Implement backend and/or frontend per spec
  4. Write unit tests (coverage >= quality.unit_coverage_min, default 95%)
  5. Verify build passes (commands.backend.build / commands.frontend[].build from profile)
  6. Commit: feat(#{N}): description (developer STAYS in In Development)
  7. Quality Gate G4 (In Development → Code Review): build + lint pass, tests written, no TODO/FIXME, clean git status
     → kanban_set {story} "Code Review"
  8. Spawn reviewers IN PARALLEL by delta: security-reviewer (ALWAYS) + java-reviewer (if backend-delta: *.java/*.kt) + frontend-reviewer (if frontend-delta: *.ts/*.tsx/*.jsx/*.html/*.scss in frontend app paths from profile). Fields: Security / JavaReview / FrontendReview; non-applicable reviewer not spawned, field stays pending, 'N/A' in Gate Report
  9. Quality Gate G5 (Code Review → Testing): Security=passed AND (JavaReview in {passed,warning} IF backend-delta) AND (FrontendReview in {passed,warning} IF frontend-delta); warning does not block
     → kanban_set {story} "Testing"
  10. Comment on issue with file list and build status
- Менять стадию ТОЛЬКО через kanban_set (доска — источник правды).

Report: branches, files changed, build status per story.")
```

**Жди завершения перед следующим этапом.**

---

## ЭТАП 4 — Testing (QA Team Lead)

Используй **qa-lead** — он координирует test-case-writer(ов) (sonnet).
Unit тесты уже написаны developer на ЭТАПЕ 3. Security + Java/Frontend review (по delta) уже пройдены в статусе Code Review (G5).
Stories в колонке Status="Testing".
**E2E автотесты — отдельный ручной процесс через `/e2e`.**

```
Agent(subagent_type="qa-lead", prompt="Test ALL stories for feature #{N}.
Stories: #{s1}, #{s2}, #{s3} (all in Status=Testing).
Read .claude/project-profile.md FIRST (thresholds from quality.*; if initialized: false — run its Fallback Detect), then CLAUDE.md and ARCHITECTURE.md (if exists).

Run your team — for EACH story spawn test-case-writer:
  test-case-writer (sonnet):
  - TC documentation from spec/arch docs (docs/test-cases/feature-{N}-{name}.md)
  - Priority: Critical/High/Medium/Low + E2E Automated flag (Planned)
  - Cross-reference sync with related TCs

E2E автотесты НЕ входят в QA pipeline. Запускать отдельно: /e2e #{N}

Verify (do NOT write — developer already did):
  - Unit coverage >= quality.unit_coverage_min (default 95%) confirmed from developer handoff (.claude/handoffs/story-{N}-dev.md)
  - kb_get {story} Security == passed (set by dev-lead). If not → BLOCKED.
  - JavaReview / FrontendReview in {passed,warning} where applicable (by delta); non-applicable field stays pending = N/A.

Collect results:
- PASSED: kanban_set {story} "Ready to Deploy" + kb_set {story} QA passed
- FAILED: kanban_set {story} "In Development" + kb_set {story} QA failed + create Bug issue
- BLOCKED (Security != passed): keep Status=Testing, request dev-lead security review

Quality Gate G6: TC docs created, Security == passed, JavaReview/FrontendReview passed/warning по применимости, unit coverage >= quality.unit_coverage_min confirmed from handoff.
Менять стадию ТОЛЬКО через kanban_set (доска — источник правды).

Report: pass/fail per story, TC count, security status.")
```

**Только если ВСЕ stories прошли → переходи к ЭТАПУ 5.**
Если есть failures → сообщи пользователю и предложи `/swarm develop #{bug}` для исправления.

---

## ЭТАП 5 — Deploy (Ops Team Lead)

Используй **ops-lead** — он координирует devops (sonnet):

```
Agent(subagent_type="ops-lead", prompt="Deploy ALL stories for feature #{N} to staging.
Stories: #{s1}, #{s2}, #{s3} (all Status=Ready to Deploy, QA=passed, Security=passed).
Read .claude/project-profile.md FIRST (deploy commands from commands.deploy.*, services from topology.services; if initialized: false — run its Fallback Detect), then CLAUDE.md and ARCHITECTURE.md (if exists).

Run your team (flow: Ready to Deploy → G7 → Deploy → G8 → Done):
1. Quality Gate G7 (Ready to Deploy → Deploy): tests green, build OK, kb_get {story} QA == passed, kb_get {story} Security == passed; for production wait human APPROVE
2. All story issues: kanban_set {story} "Deploy"
3. Pre-deploy validation (full test suite via commands.backend.test / commands.frontend[].test)
4. Build artifacts / образы согласно commands.deploy (и commands.backend.build / commands.frontend[].build)
5. Deploy to staging via commands.deploy.staging (k8s primary: helm/kustomize/kubectl; verify rollout via commands.deploy.status for each affected service)
6. Health checks по topology.services[].health + smoke tests (commands.smoke.staging)
7. Verify logs (no errors in first 60s)
8. Quality Gate G8 (Deploy → Done): health/smoke/logs OK, rollback rehearsal — реально выполнить commands.deploy.rollback на staging и вернуть — + kill switch
9. All story issues: kanban_set {story} "Done" (auto-close) + kb_set {story} Deploy staging
10. Parent feature #{N}: kanban_set {N} "Done" (if all stories done)
11. Менять стадию ТОЛЬКО через kanban_set (доска — источник правды).

Report: deploy status, health checks, closed issues.")
```

---

## ФИНАЛЬНЫЙ ОТЧЁТ

```
KANBAN PIPELINE COMPLETE — {date}

Feature: #{N} — {title}
Mode: Full Pipeline (sequential, 5 stages)

Stage Reports:
  1. Feature Request  → #{N} created (analyst)
  2. Analysis Lead    → {count} stories created, spec + arch ready
     Stories: #{s1}, #{s2}, #{s3}
     Spec: docs/specs/feature-{N}-{name}.md
     Arch: docs/arch/feature-{N}-{name}.md
  3. Dev Lead         → {count} stories developed, {files} files changed
     Branches: story/{s1}-{name}, story/{s2}-{name}
  4. QA Lead          → {passed}/{total} passed, {coverage}% coverage
     Security: {status}
     Bugs: {count} (#{bug1}, ...)
  5. Ops Lead         → staging deployed, health OK

Quality Gates: G1 ✓ → G2 ✓ → G3 ✓ → G4 ✓ → G5 ✓ → G6 ✓ → G7 ✓ → G8 ✓

GitHub Issues: {count} closed
Production: ожидает ручного деплоя (/deploy production)
```

---

## Связанные команды

| Нужно | Используй |
|-------|-----------|
| Одна фича от начала до конца | `/kanban {описание}` (эта команда) |
| Параллельно несколько фич/stories | `/swarm` или `/swarm {stage} #{N}...` |
| Последовательно right-to-left | `/sweep` |
| Только один этап | `/analyze`, `/develop`, `/test`, `/deploy` |
| Следующая задача по приоритету | `/pick {колонка}` |
| Состояние доски | `/board` |
