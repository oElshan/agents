
Запусти параллельную обработку задач на Kanban-доске. Swarm поддерживает два режима:

1. **Full Board Swarm** — все Team Leads работают параллельно, каждый обрабатывает свою колонку
2. **Stage Swarm** — один Team Lead обрабатывает указанные задачи параллельно

**ВАЖНО**: Стадию задачи Team Leads меняют ТОЛЬКО через `kanban_set N "Status"`.

**Профиль проекта**: сначала прочитай `.claude/project-profile.md` — команды build/test/deploy
бери из `commands.*`, пороги из `quality.*` (`wip_limit`, `unit_coverage_min`, `fix_loop_max`);
если `initialized: false` — выполни Fallback Detect из этого же файла.

---

## Шаг 1 — Разбор команды

Распарси `$ARGUMENTS` по следующей грамматике:

```
/swarm                                → mode: FULL_BOARD
/swarm dry-run                        → mode: FULL_BOARD, dry_run: true
/swarm analyze                        → mode: STAGE, stage: analyze, issues: auto (все из backlog)
/swarm analyze #50 #19 #20            → mode: STAGE, stage: analyze, issues: [50, 19, 20]
/swarm analyze dry-run                → mode: STAGE, stage: analyze, dry_run: true
/swarm develop                        → mode: STAGE, stage: develop, issues: auto (все из ready-for-dev)
/swarm develop #97 #98 #99            → mode: STAGE, stage: develop, issues: [97, 98, 99]
/swarm develop dry-run                → mode: STAGE, stage: develop, dry_run: true
/swarm test                           → mode: STAGE, stage: test, issues: auto (все из testing)
/swarm test #102 #104 #105            → mode: STAGE, stage: test, issues: [102, 104, 105]
/swarm test dry-run                   → mode: STAGE, stage: test, dry_run: true
/swarm deploy                         → mode: STAGE, stage: deploy, issues: auto (все из ready-to-deploy)
/swarm deploy #96 #101                → mode: STAGE, stage: deploy, issues: [96, 101]
/swarm deploy dry-run                 → mode: STAGE, stage: deploy, dry_run: true
```

**Маппинг stage → Team Lead → колонка:**

| Stage | Team Lead | Исходная колонка | Worker agents |
|-------|-----------|------------------|---------------|
| `analyze` | `analysis-lead` | **Backlog** | analyst → architect |
| `develop` | `dev-lead` | **Ready for Dev** | developer(s) |
| `test` | `qa-lead` | **Testing** | test-case-writer + e2e-tester |
| `deploy` | `ops-lead` | **Ready to Deploy** | devops |

---

## Шаг 2 — Сканирование доски

### Для FULL_BOARD — сканируй ВСЕ колонки по полю Status (параллельно):

Хелперы из `.claude/agents/kanban-board-sync.md`:

```
kanban_query "Status" "Ready to Deploy"
kanban_query "Status" "Testing"
kanban_query "Status" "In Development"
kanban_query "Status" "Ready for Dev"
kanban_query "Status" "Backlog"
```

### Для STAGE — сканируй только нужную колонку:

- Если `issues: auto` → получи все issues из соответствующей колонки
- Если `issues: [N, M, ...]` → получи конкретные issues через `mcp__github__get_issue`

Сортируй по полю Priority: `critical → high → medium → low`.

---

## Шаг 3 — WIP и capacity

```
wip_limit = quality.wip_limit из .claude/project-profile.md (default 5)
dev_wip = count(kanban_query "Status" "In Development") + count(kanban_query "Status" "Code Review")
dev_capacity = wip_limit - dev_wip
test_wip = count(kanban_query "Status" "Testing")
test_capacity = wip_limit - test_wip
```

Для STAGE mode:
- `develop`: если `dev_capacity == 0` → СТОП с предупреждением
- `test`: если `test_capacity == 0` → СТОП с предупреждением

---

## Шаг 4 — Dependency Check

Для каждого issue проверь зависимости в body: `Blocked by:`, `Depends on:`, `Requires:`.

- Если блокер НЕ closed / НЕ в колонке **Done** → issue BLOCKED, пропусти
- Если зависимостей нет или все resolved → issue READY
- Запомни BLOCKED issues для отчёта

---

## Шаг 5 — Составь план выполнения

### Для FULL_BOARD:

Определи для каждого Team Lead список задач:

```
ops_tasks   = [issues в колонке Ready to Deploy где поля QA=passed и Security=passed]
qa_tasks    = [issues в колонке Testing, не BLOCKED]
dev_tasks   = [top {dev_capacity} issues из колонки Ready for Dev по полю Priority, не BLOCKED]
analysis_tasks = [issues в колонке Backlog]
```

### Для STAGE:

```
{stage}_tasks = [указанные issues или auto-detected, не BLOCKED, в рамках WIP]
```

### Выведи план пользователю:

```
SWARM PLAN — {date}
Mode: {FULL_BOARD | STAGE: {stage}}

WIP Status:
  In Development: {dev_wip}/{wip_limit} (capacity: {dev_capacity})
  Testing: {test_wip}/{wip_limit} (capacity: {test_capacity})

{Для каждого активного stage:}

  {STAGE_NAME} ({count} tasks) → {team-lead}:
    → #{N} "{title}" [Priority={level}, Size={size}]
    → #{N} "{title}" [Priority={level}, Size={size}]
    ⊘ #{N} "{title}" — BLOCKED by #{M}
    ⊘ #{N} "{title}" — WIP limit exceeded

Parallel agents: {count}
Estimated: {count} tasks to process, {blocked} blocked, {wip_skip} skipped
```

### Если `dry_run: true` → выведи план и СТОП.

> **FULL_BOARD WIP коллизия (известное ограничение)**:
> dev-lead и qa-lead работают параллельно и берут snapshot доски в начале своей работы.
> dev-lead может добавить новые stories в колонку **Testing** пока qa-lead уже запущен — qa-lead их **не возьмёт** в этом run (ок, следующий `/swarm test` подхватит).
> Если qa-lead вернёт story в колонку **In Development** (qa:failed) — dev-lead должен учитывать WIP динамически. Dev-lead проверяет WIP перед каждым новым developer-ом, не только в начале.

---

## Шаг 6 — Параллельный запуск Team Leads

**КРИТИЧЕСКИ ВАЖНО**: Все Team Leads запускаются В ОДНОМ СООБЩЕНИИ с `run_in_background=true`.

### 6.1 — FULL_BOARD mode

Запусти ВСЕ Team Leads у которых есть задачи (до 4 параллельных агентов):

```
# Только если ops_tasks не пусты:
Agent(subagent_type="ops-lead", name="swarm-ops", run_in_background=true,
  prompt="SWARM MODE — OPS LEAD
Context: Read .claude/project-profile.md (commands.* / quality.*), CLAUDE.md and ARCHITECTURE.md (if exists).

TASK LIST (deploy these issues):
{для каждого issue из ops_tasks:}
  - #{N} "{title}"

Instructions:
1. Pre-deploy checks (G7 pre-flight): full test suite, verify build, kb_get #{N} QA==passed + Security==passed
2. For EACH issue: kanban_set #{N} \"Deploy\" (G7 passed), then run devops agent:
   - Build artifacts / Docker images
   - Deploy to staging: commands.deploy.staging из профиля (например helm upgrade --install / kustomize / kubectl apply), затем commands.deploy.status (kubectl rollout status) для каждого затронутого сервиса
   - Health check: topology.services[].health каждого затронутого сервиса
   - Smoke test main API: commands.smoke.staging
   - On failure: rollback командой commands.deploy.rollback
3. On success (G8): kb_set #{N} Deploy staging, then kanban_set #{N} \"Done\" (закрытие внутри)
4. Check if parent feature has all stories done → close parent too
5. Меняй стадию ТОЛЬКО через kanban_set; статусы/гейты — через хелперы из .claude/agents/kanban-board-sync.md

Report format:
DEPLOYED: #{N} — status
FAILED: #{N} — reason
PARENT CLOSED: #{F} — all stories done")


# Только если qa_tasks не пусты:
Agent(subagent_type="qa-lead", name="swarm-qa", run_in_background=true,
  prompt="SWARM MODE — QA LEAD
Context: Read .claude/project-profile.md (commands.* / quality.*), CLAUDE.md and ARCHITECTURE.md (if exists).

TASK LIST (test these issues):
{для каждого issue из qa_tasks:}
  - #{N} "{title}"

Instructions:
1. For EACH issue — pre-flight FIRST (всё состояние — в полях доски, не лейблах):
   a. kb_set #{N} QA in-progress
   b. Verify kb_get #{N} Security == passed (set by security-reviewer on G5). If not → BLOCKED: keep stage Testing, kb_set #{N} QA pending, comment reason.
   c. Read .claude/handoffs/story-{N}-dev.md — confirm unit coverage >= quality.unit_coverage_min (default 95%)
   d. Verify build passes
2. For EACH issue (pre-flight passed) — spawn TWO agents IN PARALLEL:
   - test-case-writer: TC documentation from spec/arch, cross-reference sync
   - e2e-tester (opus): E2E Java tests (Playwright+JUnit5+POM), compile + run on live system
   NOTE: Do NOT spawn tester or security-reviewer — unit tests are developer's responsibility, code review done by dev-lead in Code Review status.
3. Collect results per issue (G6: Testing → Ready to Deploy):
   PASSED: kb_set #{N} QA passed (+ kb_num #{N} Coverage <pct>), kanban_set #{N} \"Ready to Deploy\".
   FAILED: kb_set #{N} QA failed + create Bug issue, kanban_set #{N} \"In Development\".
   BLOCKED: kb_set #{N} QA pending, keep stage Testing, comment reason.
4. Multiple issues → run ALL pairs in PARALLEL
5. Меняй стадию ТОЛЬКО через kanban_set; поля — через kb_set/kb_num

Report format:
PASSED: #{N} — TCs: {N}, E2E: compiled OK / {N} passed
FAILED: #{N} — reason, bug: #{bug}
BLOCKED: #{N} — reason (Security != passed / build broken)")


# Только если dev_tasks не пусты:
Agent(subagent_type="dev-lead", name="swarm-dev", run_in_background=true,
  prompt="SWARM MODE — DEV LEAD
Context: Read .claude/project-profile.md (commands.* / quality.*), CLAUDE.md and ARCHITECTURE.md (if exists).

TASK LIST (develop these stories):
{для каждого issue из dev_tasks:}
  - #{N} "{title}"

Instructions:
1. Analyze dependencies between stories in the list
2. Independent stories (different components) → spawn developers in PARALLEL
3. Dependent stories (shared entities) → spawn SEQUENTIALLY
4. Each developer agent (in isolated worktree):
   - Create branch: feature/{N}-{short-name}
   - Read spec from docs/specs/ and arch from docs/arch/
   - Implement backend and/or frontend per spec
   - Write unit tests (coverage >= quality.unit_coverage_min, default 95% — verify with commands.backend.coverage из профиля (JaCoCo-отчёт для Gradle/Maven), real numbers)
   - Verify build passes
   - Commit: feat(#{N}): description with trailers; merge story-branch into feature-branch
   - Create handoff: .claude/handoffs/story-{N}-dev.md with real coverage %
   - developer STAYS in In Development (does NOT change Status) — dev-lead advances it
   After each developer (dev-lead):
   - G4: verify git status --short empty + commands.backend.test из профиля (например ./gradlew test или mvn test) SUCCESS + branch merged → kanban_set #{N} \"Code Review\"
   - Spawn reviewers по delta IN PARALLEL: security-reviewer (always) + java-reviewer (if backend files in delta) + frontend-reviewer (if frontend files in delta); they set fields Security / JavaReview / FrontendReview. Неприменимый reviewer не запускается, его поле остаётся pending («N/A» в Gate Report)
   - G5: kb_get #{N} Security == passed AND (JavaReview ∈ {passed,warning} IF backend-delta) AND (FrontendReview ∈ {passed,warning} IF frontend-delta) → kanban_set #{N} \"Testing\"
     (Security=failed / JavaReview=failed / FrontendReview=failed → back to In Development, developer fixes, max quality.fix_loop_max cycles, default 3)
   - Comment on issue with file list, build status, coverage %, Security/JavaReview/FrontendReview
5. Меняй стадию ТОЛЬКО через kanban_set; поля — через kb_set
6. NEVER exceed WIP limit of quality.wip_limit, default 5 (In Development + Code Review together)

Report format:
DEVELOPED: #{N} — branch: feature/{N}-{name}, files: X, build: OK, coverage: N%, Security: passed, JavaReview: passed/warning/N-A, FrontendReview: passed/warning/N-A
FAILED: #{N} — reason
BLOCKED: #{N} — skipped, reason")


# Только если analysis_tasks не пусты:
Agent(subagent_type="analysis-lead", name="swarm-analysis", run_in_background=true,
  prompt="SWARM MODE — ANALYSIS LEAD
Context: Read .claude/project-profile.md (commands.* / quality.*), CLAUDE.md and ARCHITECTURE.md (if exists).

TASK LIST (analyze these features):
{для каждого issue из analysis_tasks:}
  - #{N} "{title}"

Instructions:
1. For EACH feature:
   a. Run analyst agent: decompose into User Stories, write spec (docs/specs/feature-{N}-{name}.md)
   b. Run architect agent: create arch doc (docs/arch/feature-{N}-{name}.md), define entities/services/API
2. Multiple features → run analyst+architect PAIRS in PARALLEL (each pair is sequential: analyst THEN architect)
3. Create child story issues БЕЗ лейблов; метаданные — в поля: kb_meta #{story} type=story component=* size=* priority=*; then kanban_set #{story} \"Ready for Dev\"
4. Update parent feature: add story links, mark as analyzed
5. Меняй стадию ТОЛЬКО через kanban_set

Report format:
ANALYZED: #{N} — stories: [#{s1}, #{s2}], spec: path, arch: path
FAILED: #{N} — reason")
```

### 6.2 — STAGE mode

Запусти ОДИН Team Lead с конкретным списком задач:

```
# stage=analyze:
Agent(subagent_type="analysis-lead", name="swarm-analysis",
  prompt="SWARM MODE — ANALYSIS LEAD
  ... (то же что в 6.1, но с конкретным списком issues)")

# stage=develop:
Agent(subagent_type="dev-lead", name="swarm-dev",
  prompt="SWARM MODE — DEV LEAD
  ... (то же что в 6.1, но с конкретным списком issues)")

# stage=test:
Agent(subagent_type="qa-lead", name="swarm-qa",
  prompt="SWARM MODE — QA LEAD
  ... (то же что в 6.1, но с конкретным списком issues)")

# stage=deploy:
Agent(subagent_type="ops-lead", name="swarm-ops",
  prompt="SWARM MODE — OPS LEAD
  ... (то же что в 6.1, но с конкретным списком issues)")
```

**Для STAGE mode**: НЕ используй `run_in_background` — жди результата, чтобы дать пользователю немедленный отчёт.

---

## Шаг 7 — Ожидание и сбор результатов

### FULL_BOARD mode:
- Дождись завершения ВСЕХ background Team Leads
- Собери результаты из каждого

### STAGE mode:
- Результат приходит сразу (foreground agent)

---

## Шаг 8 — Финальный консолидированный отчёт

```
SWARM COMPLETE — {date}
Mode: {FULL_BOARD | STAGE: {stage}}
Team Leads: {count} launched
Duration: ~{time}

{Для каждого Team Lead:}

═══ {STAGE_NAME} LEAD ═══
  PROCESSED:
    ✓ #{N} "{title}" — {result summary}
    ✓ #{N} "{title}" — {result summary}

  FAILED:
    ✗ #{N} "{title}" — {failure reason}

  SKIPPED:
    ⊘ #{N} "{title}" — {BLOCKED by #{M} | WIP limit}

═══════════════════════════

SUMMARY:
  Total tasks:    {count}
  Processed:      {count} ✓
  Failed:         {count} ✗
  Blocked:        {count} ⊘
  Skipped (WIP):  {count}
  Bugs created:   {count}
  Security issues: {count}

BOARD STATE AFTER SWARM:
  Backlog:          {count}
  Analysis:         {count}
  Ready for Dev:    {count}
  In Development:   {count}/{wip_limit}
  Testing:          {count}/{wip_limit}
  Ready to Deploy:  {count}
  Done (this run):  {count}

NEXT ACTIONS:
  {если появились новые ready-for-dev → предложи /swarm develop}
  {если появились новые testing → предложи /swarm test}
  {если есть ready-to-deploy → предложи /swarm deploy}
  {если всё чисто → Board clear! 🎉}
  {если WIP полон → Завершите текущие задачи перед запуском новых}
  {если были BLOCKED → предложи разблокировку конкретных issues}
```

---

## Примеры использования

```bash
# Полный swarm — все колонки параллельно
/swarm

# Только посмотреть план
/swarm dry-run

# Параллельный анализ 3 фич
/swarm analyze #50 #19 #20

# Параллельная разработка 5 stories
/swarm develop #97 #98 #99 #103 #108

# Тестирование всех issues в колонке testing
/swarm test

# Тестирование конкретных stories
/swarm test #102 #104 #105

# Деплой всего готового
/swarm deploy

# Деплой конкретных stories
/swarm deploy #96 #101 #106
```
