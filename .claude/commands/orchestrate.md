---
description: "Kanban: Orchestrate. Единый оркестратор доски — замкнутая петля до готовности. /orchestrate (автопилот) | once (=sweep) | swarm | <колонка> | #N | dry-run"
argument-hint: "<пусто=continuous автопилот | once | swarm | backlog|ready-for-dev|testing|ready-to-deploy | #N | dry-run>"
---

# ORCHESTRATE — Единый оркестратор задач: $ARGUMENTS

Замкнутая управляющая петля над Kanban-доской. Вместо одиночного прохода
(`/sweep`/`/swarm`/`/pick` — теперь его пресеты) крутит доску **сам**: посмотрел →
выбрал что двигать → запустил Team Leads → снова посмотрел → повторил, пока не сработает
условие остановки. Останавливается по явной причине и пишет отчёт **почему** и **что осталось**.

**ВАЖНО**: стадию задачи Team Leads меняют ТОЛЬКО через `kanban_set N "Status"`.

**Профиль**: сначала прочитай `.claude/project-profile.md`. Команды build/test/deploy — из
`commands.*`, пороги — из `quality.*` (`wip_limit`, `unit_coverage_min`, `fix_loop_max`),
политику петли — из `orchestrator.*`. Если `initialized: false` — Fallback Detect из профиля.

Хелперы доски (`kb_dump`, `kanban_query`, `kanban_set`, `kb_set`, `kb_get`, `kb_meta`) —
`.claude/agents/kanban-board-sync.md`. Зависимости — `.claude/agents/dependency-resolver.md`.
Гейты G1–G8 — `.claude/agents/quality-gates.md`.

---

## Шаг 0 — Политика (парсинг `$ARGUMENTS`)

Оркестратор описывается пятью параметрами. Аргументы задают пресет; профиль даёт дефолты.

| Параметр | Значения | Дефолт |
|---|---|---|
| `mode` | `once` (один тик) \| `continuous` (петля до остановки) | `orchestrator.mode` (обычно `continuous`) |
| `concurrency` | `seq` (по очереди) \| `parallel` (все Team Leads разом) \| `auto` | `orchestrator.concurrency` |
| `scope` | `sprint` (колонка Sprint + всё in-flight = вся работа) \| `<колонка>` \| `#<issue>` \| `backlog`/`all` (явный escape к интейку) | `sprint` |
| `take` | сколько задач взять из колонки (`all` \| число) | `all` (в рамках WIP) |
| `until` | `drained` \| `goal` \| `budget` (для continuous) | `drained` |
| `skip` | стадии, отключаемые **на этот запуск** (`analysis`/`develop`/`testing`/`deploy`, через запятую) | — |
| `dry_run` | план без выполнения | `false` |

**Отключённые стадии.** Эффективный список пауз = `orchestrator.disabled_stages` из профиля
(постоянные, ставит команда `/stage`) ∪ `skip:` из аргумента (разовые, только этот запуск).
Team Lead отключённой стадии НЕ запускается — его агенты не тратят токены, задачи держатся
в буфере перед стадией (HELD, см. Шаг 4). Управление постоянными паузами — `/stage`.

### Спринт-скоуп — ГЛАВНОЕ

Спринт — это **Status-колонка `Sprint`** (после `Backlog`), а не поле. Оркестратор **берёт НОВОЕ
в работу только из колонки `Sprint`**, ведёт всё уже начатое (in-flight) до `Done` и **никогда
не трогает `Backlog`** (сырой интейк). Модель потока:

```
Backlog (икотека)  ──человек кладёт──▶  Sprint (вход)  ──▶  Analysis / Ready for Dev  ──▶ … ──▶  Done
```

> **Инвариант «по факту, без домыслов».** Рабочее множество берётся ИСКЛЮЧИТЕЛЬНО из живого
> `kb_dump` каждый тик: issue со `Status ∈ {Sprint, Analysis, Ready for Dev, In Development,
> Code Review, Testing, Ready to Deploy, Deploy}` (всё, кроме `Backlog` и `Done`). Приём НОВОГО —
> только из `Status=Sprint`. Оркестратор НЕ ведёт свой список и НЕ решает, что «должно» быть в
> спринте; как задача попала в `Sprint` — рукой на доске или `/sprint add` — ему безразлично.
> Нет задач в `Sprint` и нет in-flight → **ничего не делает** (Шаг 6, `EMPTY`).

- `scope=sprint` (дефолт) = `scope=board` — рабочая доска = колонка `Sprint` + всё in-flight (синонимы).
- `scope=backlog` / `scope=all` — **явный escape** к интейку (`Status=Backlog`). Только ручные
  операции, с предупреждением; автопилот их не использует.
- `scope=<колонка>` / `#N` — сужение **внутри** рабочего множества.

**Роутинг приёма из `Sprint` по `Type`:** `feature`/`epic` → analysis-lead (`Sprint → Analysis`);
`story`/`bug`/`tech-debt`/`hotfix`/`spike` (dev-ready) → dev-lead (`Sprint → In Development`).
Дочерние stories, рождённые анализом, ложатся в `Ready for Dev` (обычный in-flight) — их dev-lead
берёт оттуда же.

### Пресеты (в т.ч. как разворачиваются алиасы)

| Ввод | Разворачивается в |
|---|---|
| `/orchestrate` | `mode=continuous concurrency=auto scope=sprint until=drained` — **автопилот по спринту** |
| `/orchestrate once` | `mode=once concurrency=seq scope=sprint` — один right-to-left проход по спринту (**= /sweep**) |
| `/orchestrate swarm` | `mode=once concurrency=parallel scope=sprint` (**= /swarm**) |
| `/orchestrate <колонка>` | `mode=once concurrency=seq scope=<колонка>` (внутри спринта) |
| `/orchestrate <колонка> #N #M` | `mode=once scope=<колонка>` только по этим issue |
| `/orchestrate #N` | `mode=continuous scope=#N until=goal` — довести один issue до Done |
| `/orchestrate dry-run` | текущий пресет + `dry_run=true` |

> **Разведение перегрузки `sprint`:** дефолтный `scope=sprint` (бэйр `/orchestrate`, `once`, `swarm`) =
> **всё рабочее множество** (колонка `Sprint` + in-flight), синоним `scope=board`. Но когда `sprint`
> приходит как **колонка-аргумент** (`/orchestrate sprint`, `/pick sprint`, `/sweep sprint`) — это
> сужение до **колонки `Sprint`** (только приём новой работы), как любой `scope=<колонка>`.

Колонки-аргументы: `sprint`, `backlog`, `ready-for-dev`, `testing`, `ready-to-deploy` (маппинг на
Status как в `/pick`). `sprint` = приём новой работы из колонки `Sprint`. Транзитные
`Code Review`/`Deploy` таргетить нельзя — ими владеют dev-lead/ops-lead.

**Две формы ввода принимаются равноправно:**
- человекочитаемые пресеты (`once`, `swarm`, `<колонка>`, `#N`, `dry-run`) — из таблицы выше;
- явные `key=value`-токены (`mode=once concurrency=seq scope=testing take=1 dry_run=true`) —
  их эмитят алиасы `/sweep` / `/swarm` / `/pick`. Явный токен **переопределяет** дефолт пресета
  и профиля (например `swarm scope=testing` = parallel только по колонке Testing).

Выведи распознанную политику одной строкой перед стартом.

---

## Шаг 1 — Состояние петли (durable)

Петля stateless по задачам (правда — на доске), но свои счётчики держит в
`.claude/memory/orchestrator-state.json` — чтобы `stall`/`budget`/`tick` пережили
`ScheduleWakeup`-паузу. Файла нет → свежая петля (self-healing).

```json
{ "started": "<ISO>", "tick": 0, "last_score": -1, "stall_count": 0,
  "tokens_spent_est": 0, "policy": "<строка политики>" }
```

Прочитай файл в начале. В `mode=once` он не нужен (один тик — читать/писать не обязательно).

---

## Шаг 2 — OBSERVE (снимок доски → срез спринта)

```bash
kb_dump > "${TMPDIR:-/tmp}/orch.json"
```

Один дамп даёт все issue со всеми полями (Status/…/**Parked**). **Сузь до scope ПО ФАКТУ** — это
и есть множество работы; ничего не додумывай:

```bash
# по умолчанию scope=sprint: колонка Sprint + всё in-flight (всё, кроме Backlog и Done)
jq '[.[] | select(.status!=null and .status!="Backlog" and .status!="Done")]' "${TMPDIR:-/tmp}/orch.json" \
  > "${TMPDIR:-/tmp}/orch.scope.json"
# scope=backlog → select .status=="Backlog" ;  scope=all → без фильтра ;  scope=<колонка>/#N → доп. фильтр
```

**Если срез пуст** (нет ни одной issue в `Sprint` и нет in-flight — всё либо в `Backlog`, либо
`Done`) → оркестратор **ничего не делает**: сразу Шаг 6, стоп-причина `EMPTY` («в спринте пусто —
переложи задачи из Backlog в Sprint / `/sprint add`»). Никаких попыток «найти работу» в бэклоге.

Посчитай **board_score** — сумму индексов стадий (мера прогресса) по срезу:

```
index: Backlog 0 · Sprint 1 · Analysis 2 · Ready for Dev 3 · In Development 4 · Code Review 5
     · Testing 6 · Ready to Deploy 7 · Deploy 8 · Done 9
board_score = Σ index(status) по всем не-Parked issue в срезе
```

```bash
jq '[.[] | select((.parked // "no")=="no") | .status as $s |
     (["Backlog","Sprint","Analysis","Ready for Dev","In Development","Code Review","Testing","Ready to Deploy","Deploy","Done"]
      | index($s)) // 0] | add' "${TMPDIR:-/tmp}/orch.scope.json"
```

---

## Шаг 3 — DIAGNOSE

1. **WIP / capacity** (`wip_limit = quality.wip_limit`, default 5) — считаем **по срезу спринта**
   (`orch.scope.json`), а не по всей доске:
   ```
   dev_wip  = count(In Development) + count(Code Review)   # в пределах спринта
   test_wip = count(Testing)                               # в пределах спринта
   dev_capacity  = wip_limit - dev_wip
   test_capacity = wip_limit - test_wip
   ```
2. **Зависимости** (по `dependency-resolver.md`): для каждого issue разбери `Blocked by:` /
   `Depends on:` / `Requires:` из body. Блокер resolved ⟺ closed ИЛИ Status=Done. Есть
   нерешённый → issue BLOCKED (в план не берём). Цикл / глубина >10 → PARK.
3. **Осцилляция**: issue, который откатывался назад (Testing→In Development или review-fail)
   уже `fix_loop_max` раз (default 3). Такой issue → **PARK(oscillation)**.
4. **Human-gate**: issue в `Ready to Deploy` с `Type`≈prod-кандидат, где нужен человеческий
   `APPROVE PRODUCTION DEPLOY`, а его нет в комментариях → **PARK(human)**. Staging — не паркуем.

### Парковка (single-writer поля `Parked` = оркестратор)

```bash
kb_set N Parked oscillation   # заклинило — нужен человек
kb_set N Parked human         # ждём APPROVE на прод
kb_set N Parked deps          # цикл/слишком глубокая цепочка зависимостей
kb_set N Parked no            # снять парковку
```

**Авто-распарковка каждый тик:** `Parked=deps` и зависимости теперь resolved → `Parked no`.
`Parked=human` и в комментариях появился `APPROVE PRODUCTION DEPLOY` → `Parked no`.
`Parked=oscillation` НЕ снимается автоматически — только человеком.
Parked-issue исключены из фронта, но всплывают в финальном отчёте.

---

## Шаг 4 — PLAN (фронт)

**Фронт** = issue, которые МОГУТ сдвинуться прямо сейчас:
`precondition гейта выполнен` ∧ `не BLOCKED` ∧ `не Parked` ∧ `есть WIP-capacity`.

Порядок обработки — **right-to-left** (сначала то, что ближе к готовности), внутри стадии —
по полю **Priority** (`critical → high → medium → low`, при равенстве — меньший #):

```
Ready to Deploy → Testing → (Code Review, Deploy — ведут сами Team Leads) →
In Development → Ready for Dev → Analysis → Sprint (приём новой работы)
```
`Backlog` во фронт **не входит** — это сырой интейк, автопилот его не трогает.

Ограничения:
- `Ready for Dev` → бери не больше `dev_capacity` (остальное — SKIPPED (WIP)).
- `Testing` → в рамках `test_capacity`.
- `Ready to Deploy` → только issue с `QA=passed` И `Security=passed`.
- `Sprint` (приём) → маршрутизируй по `Type`: `feature`/`epic` → analysis-lead; остальные
  (dev-ready) → dev-lead, в рамках `dev_capacity`.
- `take=1` (пресет `/pick`) → взять ровно одну верхнюю по приоритету из scope-колонки.
- `scope=<колонка>` → только эта колонка; `scope=#N` → только этот issue (и его дети-stories).

Сгруппируй фронт по Team Lead: **ops-lead** (Ready to Deploy) · **qa-lead** (Testing) ·
**dev-lead** (In Development + Ready for Dev + dev-ready из `Sprint`) ·
**analysis-lead** (`feature`/`epic` из `Sprint`).

### Отключённые стадии (HELD)

Возьми эффективный список пауз (профиль `orchestrator.disabled_stages` ∪ аргумент `skip:`).
Стадия → Team Lead → буфер, где задачи держатся:

| Стадия | Team Lead исключается | Буфер (HELD) |
|---|---|---|
| `analysis` | analysis-lead | `Sprint` (feature/epic ждут приёма) |
| `develop` | dev-lead | `Ready for Dev` (+ dev-ready в `Sprint`) |
| `testing` | qa-lead | Testing |
| `deploy` | ops-lead | Ready to Deploy |

Правила:
- Team Lead отключённой стадии **в фронт не попадает** (агенты не запускаются → ноль токенов).
  Его буферные задачи помечаются **HELD** и в отчёте показываются отдельно (не как «Done», не как «BLOCKED»).
- **Пауза = стоп приёма новых, но in-flight дорабатывается (drain).** Отключённый Team Lead
  не берёт новое из буфера, но задачи, УЖЕ находящиеся в его активных статусах, доводит до
  выхода — чтобы не бросить worktree/деплой на полдороге. Конкретно: `develop` off → не берём
  из `Ready for Dev`, но `In Development`/`Code Review` доводим до `Testing`; `deploy` off → не
  берём из `Ready to Deploy`, но задачу уже в `Deploy` докатываем до `Done`.
- **Разовый override:** если `scope` явно указывает ровно одну отключённую колонку
  (`/orchestrate testing` при выключенном testing) — выполни её этот раз и предупреди
  («testing на паузе в /stage — выполняю разово, постоянная пауза не снята»).

### dry-run → выведи план и СТОП

```
ORCHESTRATE DRY-RUN — {date}
Scope: sprint (колонка Sprint + in-flight) — {N} задач в работе, {M} ждут приёма в Sprint
Policy: mode={..} concurrency={..} scope={..} until={..}
WIP: Dev {dev_wip}/{wip_limit} (cap {dev_capacity}) · Test {test_wip}/{wip_limit} (cap {test_capacity})

DISABLED stages: {список отключённых или «нет»}

FRONTIER (right-to-left):
  OPS   → #N … (Ready to Deploy→Done)          [строку пропусти, если deploy off]
  QA    → #N … (Testing→Ready to Deploy)        [пропусти, если testing off]
  DEV   → #N … (In Dev→Review→Testing) | #N … (Ready for Dev→In Dev) | #N … (Sprint→In Dev, dev-ready)   [приём пропусти, если develop off]
  ANLZ  → #N … (Sprint→Analysis, feature/epic)  [пропусти, если analysis off]

HELD (стадия отключена — ждут в буфере):
  ⏸️ #N — deploy off (в Ready to Deploy)
  ⏸️ #N — testing off (в Testing)
PARKED:  🅿️ #N (oscillation|human|deps)
BLOCKED: 🚫 #N — by #M
SKIPPED: ⊘ #N — WIP limit
BACKLOG (не в работе, автопилот игнорит): {K} задач — переложи в Sprint, чтобы взять

Termination target: {until}
```
**После dry-run — СТОП.**

---

## Шаг 5 — ACT (диспатч Team Leads)

`concurrency=seq` → Team Leads по очереди (foreground), right-to-left. Минимум гонок.
`concurrency=parallel`/`auto` → все Team Leads с задачами В ОДНОМ СООБЩЕНИИ,
`run_in_background=true` (до 4 параллельно). Быстрее, но возможны гонки на разных полях —
допустимо, т.к. поля single-writer.

> `auto` = `parallel`, кроме случая, когда во фронте только одна стадия (тогда `seq` не хуже),
> или `scope=#N` (одна цепочка — `seq`).

Диспатч-промпты (единый источник — здесь; `/sweep` и `/swarm` их больше не дублируют):

### OPS (Ready to Deploy)
```
Agent(subagent_type="ops-lead"[, run_in_background=true если parallel], prompt="ORCHESTRATE — OPS LEAD.
Read .claude/project-profile.md (commands.*/quality.*), CLAUDE.md, ARCHITECTURE.md (if exists).
Issues (deploy): {список из фронта}. Только те, где kb_get N QA==passed И Security==passed.
Per issue: G7 pre-flight → kanban_set N 'Deploy' → devops: build + commands.deploy.staging → commands.deploy.status (rollout) по каждому сервису → health topology.services[].health → smoke commands.smoke.staging → при провале rollback commands.deploy.rollback. G8 OK → kb_set N Deploy staging → kanban_set N 'Done'. Закрыть родительскую feature, если все stories Done.
Стадию менять ТОЛЬКО через kanban_set. Report: DEPLOYED/FAILED/PARENT CLOSED.")
```

### QA (Testing)
```
Agent(subagent_type="qa-lead"[, run_in_background=true], prompt="ORCHESTRATE — QA LEAD.
Read .claude/project-profile.md, CLAUDE.md, ARCHITECTURE.md (if exists).
Issues (test): {список}. Пропусти BLOCKED (deps).
Per issue pre-flight: kb_get N Security==passed (иначе BLOCKED — Testing остаётся, comment); coverage из .claude/handoffs/story-N-dev.md >= quality.unit_coverage_min; build green.
Per issue (pre-flight OK): test-case-writer (QA-инженер) — TC из AC → поднять реальный стенд (commands.local_env.up → иначе commands.backend.integration_test/Testcontainers → иначе degraded с флагом) → ПРОГНАТЬ каждый AC по живой системе (curl/REST: happy/RBAC 401-403/error/persistence; microservices → graceful degradation+идемпотентность; high_load → пагинация) → перепрогнать commands.backend.test ПО ФАКТУ → завести Bug issue на КАЖДЫЙ провалившийся AC (repro+Expected+Actual(evidence)+Blocks:#N, kanban_set BUG Sprint — сразу в работу) → living QA report + traceability. НЕ unit-тесты (developer), НЕ security (Code Review), НЕ UI E2E (отдельный /e2e).
G6: PASS (ВСЕ AC verified PASS + автотесты SUCCESS + build green) → kb_set N QA passed (+ kb_num N Coverage) + kanban_set N 'Ready to Deploy'. FAIL (любой AC FAIL / build/тесты сломаны) → баги заведены тестировщиком, kb_set N QA failed + kanban_set N 'In Development' (петля). WIP=quality.wip_limit.
Стадию — ТОЛЬКО kanban_set. Report: per issue — stand level (A/B/C), {pass}/{total} AC, autotests, VERDICT, bugs filed.")
```

### DEV (In Development + Ready for Dev)
```
Agent(subagent_type="dev-lead"[, run_in_background=true], prompt="ORCHESTRATE — DEV LEAD.
Read .claude/project-profile.md, CLAUDE.md, ARCHITECTURE.md (if exists).
Stories: {список dev_tasks в рамках dev_capacity} — из 'Ready for Dev' И dev-ready задач (story/bug/tech-debt/hotfix/spike) из колонки 'Sprint' (их developer двигает Sprint→In Development). Пропусти BLOCKED. Sort by Priority.
Независимые stories → developer'ы ПАРАЛЛЕЛЬНО (isolation=worktree); зависимые (общие entity) → последовательно.
Each developer: ветка feature/{featN}-{slug} → story/{N}-{slug} от неё → implement backend/frontend по spec/arch → unit-тесты (coverage>=quality.unit_coverage_min, реально через commands.backend.coverage) → build green → commit + merge story→feature. developer НЕ меняет Status.
dev-lead после каждого: G4 (git status чист + commands.backend.test SUCCESS + merged) → kanban_set N 'Code Review' → reviewers по delta ПАРАЛЛЕЛЬНО: security-reviewer (всегда) + java-reviewer (backend-delta) + frontend-reviewer (frontend-delta) → G5 (Security=passed И JavaReview∈{passed,warning} если backend-delta И FrontendReview∈{passed,warning} если frontend-delta; неприменимый reviewer не запускается — поле pending, «N/A» в Gate Report) → kanban_set N 'Testing'.
review-fail → developer fix, max quality.fix_loop_max циклов (потом эскалация — оркестратор паркует). WIP=quality.wip_limit (In Dev + Code Review вместе).
Стадию — ТОЛЬКО kanban_set. Report: DEVELOPED (branch/files/build/coverage/Security/JavaReview/FrontendReview)/FAILED/BLOCKED.")
```

### ANALYSIS (Backlog)
```
Agent(subagent_type="analysis-lead"[, run_in_background=true], prompt="ORCHESTRATE — ANALYSIS LEAD.
Read .claude/project-profile.md, CLAUDE.md, ARCHITECTURE.md (if exists).
Features (feature/epic из колонки Sprint): {список}. Backlog НЕ трогай — это интейк.
Per feature: G1 (Sprint→Analysis, kanban_set N 'Analysis') → analyst (декомпозиция → stories + docs/specs/feature-N-*.md, SDC 8 слотов, SD-1..SD-5) → architect (docs/arch/feature-N-*.md, ERD/API/ADR по budget-threshold). Разные фичи — ПАРАЛЛЕЛЬНО; одна фича analyst→architect последовательно.
Дочерние stories: kb_meta N type=story priority=* size=* component=* → kanban_set N 'Ready for Dev'.
G2 → kanban_set feature 'Ready for Dev'. Стадию — ТОЛЬКО kanban_set. Report: ANALYZED (stories/spec/arch)/FAILED.")
```

Дождись результатов (foreground — сразу; background — по completion-нотификации).

---

## Шаг 6 — OBSERVE′ + TERMINATION

Пере-считай `kb_dump` и `board_score`. Определи, был ли **прогресс** в этом тике:
`board_score` вырос ИЛИ хоть одно поле продвинулось (напр. `Security: pending→passed`).

Обнови state-файл: `tick++`; если прогресса нет → `stall_count++`, иначе `stall_count=0`;
`last_score = board_score`.

Проверь условия остановки (первое сработавшее — стоп):

| Предикат | Условие | Итог |
|---|---|---|
| **EMPTY** | нет ни одной issue в `Sprint` и нет in-flight (всё в `Backlog` или `Done`) | 🈳 нечего делать |
| **GOAL** | все не-Parked issue в scope = `Done` | ✅ success |
| **HELD** | фронт пуст только из-за отключённых стадий, а в их буферах есть задачи | ⏸️ на паузе |
| **DRAINED** | фронт пуст И нет in-flight агентов (остаток = Parked/BLOCKED) | ⏹ drained |
| **STALL** | `stall_count >= orchestrator.stall_rounds` (default 2) И нет in-flight | ⚠️ заклинило |
| **BUDGET** | `tick >= max_ticks` ИЛИ оценка токенов ≥ `budget_tokens` (если задан) | 💰 budget |
| **HUMAN** | во фронте не осталось ничего, кроме `Parked=human` | 🙋 ждём APPROVE |

> **HELD важнее DRAINED:** если работа стоит из-за паузы стадии — это НЕ «всё готово».
> Проверяй HELD перед DRAINED, чтобы отчёт не соврал «Board clear», когда 5 задач ждут деплоя.

`mode=once` → всегда стоп после одного тика (шаги 5–6 выполнились раз).

---

## Шаг 7 — PACE (только `mode=continuous`)

Если ни один предикат не сработал — следующий тик:

- Есть actionable-фронт и НЕ ждём внешнего → **тикай сразу** (вернись к Шагу 2 в этом же ходу).
- Ждём **внешнего** (катится деплой/CI, либо только `Parked=human`) → НЕ опрашивай вхолостую:
  вызови `ScheduleWakeup` и заверши ход. Петля возобновится тем же `/orchestrate $ARGUMENTS`.
  - активный деплой/CI, который стоит перепроверить скоро → `delaySeconds≈270` (кэш тёплый);
  - ждём человеческий APPROVE / общий idle → `delaySeconds = orchestrator.pace_seconds` (default 1200).
  ```
  ScheduleWakeup(delaySeconds=<270|pace_seconds>,
    reason="orchestrate: <ждём deploy #N | APPROVE #N | idle re-check>",
    prompt="/orchestrate $ARGUMENTS")
  ```

Фоновые Team Leads (`run_in_background`) харнесс возвращает сам по завершении — их не опрашивай,
просто продолжай тик по completion-нотификации.

---

## Шаг 8 — Финальный отчёт

```
ORCHESTRATE {STOP-REASON} — {date}
Scope: sprint (колонка Sprint + in-flight) — {N} задач в работе
Policy: mode={..} concurrency={..} scope={..} until={..}
Ticks: {tick} · Duration: ~{time}

PROCESSED (right-to-left):
  OPS  → #N deployed / parent closed
  QA   → #N QA=passed | #N QA=failed (bug #B)
  DEV  → #N developed (coverage N%, Security/JavaReview/FrontendReview)
  ANLZ → #N analyzed ({k} stories)

HELD (стадии на паузе — токены не тратились):
  ⏸️ deploy off → #N #M ждут в Ready to Deploy
  ⏸️ testing off → #K ждёт в Testing
PARKED (нужен человек):
  🅿️ #N — oscillation (откатывался {fix_loop_max}×)
  🅿️ #N — human (ждёт `APPROVE PRODUCTION DEPLOY`)
  🅿️ #N — deps (цикл/глубина >10)

BLOCKED (зависимости): 🚫 #N — by #M
SKIPPED (WIP): ⊘ #N

STOP REASON: {EMPTY в спринте пусто — переложи задачи в Sprint (/sprint add #N) | GOAL всё Done |
              HELD стадии {X} отключены, {N} задач ждут | DRAINED остаток заблокирован |
              STALL нет прогресса {stall_rounds}× | BUDGET {max_ticks} тиков/лимит токенов | HUMAN ждём APPROVE}

BOARD AFTER: Sprint {n} (ждут приёма) · Analysis {n} · Ready for Dev {n} · In Dev {n}/{wip} ·
             Code Review {n} · Testing {n}/{wip} · Ready to Deploy {n} · Done(+{n})   [Backlog {n} — интейк, вне работы]

NEXT: {что человеку сделать — переложить задачи из Backlog в Sprint (/sprint add #N), включить
       стадию (/stage on deploy), разпарковать #N, дать APPROVE, разблокировать deps; либо «Всё в спринте готово 🎉»}
```

В `mode=continuous`, если завершились по HUMAN/STALL/BUDGET и хочешь, чтобы петля продолжилась
после вмешательства человека — перезапусти `/orchestrate` тем же пресетом.

---

## Примеры

```bash
/orchestrate                      # автопилот: крутит доску до drained/stall/budget/human
/orchestrate dry-run              # план автопилота без выполнения
/orchestrate once                 # один right-to-left проход (= /sweep)
/orchestrate swarm                # один параллельный проход (= /swarm)
/orchestrate testing              # добить колонку Testing
/orchestrate ready-for-dev #97 #98  # разработать только эти две story
/orchestrate #52                  # довести фичу #52 (и её stories) до Done
```
