---
description: "Kanban: Orchestrate. Единый оркестратор доски — замкнутая петля до готовности. /orchestrate (автопилот) | once (=sweep) | swarm | <колонка> | #N | dry-run"
argument-hint: "<пусто=continuous автопилот | once | swarm | sprint|ready-for-dev|testing|ready-to-deploy | #N | dry-run>"
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
| `scope` | `board` (весь активный пайплайн: колонки `Sprint`…`Deploy`) \| `<колонка>` \| `#<issue>` \| `backlog`/`all` (явный escape) | `board` |
| `take` | сколько задач взять из колонки (`all` \| число) | `all` (в рамках WIP) |
| `until` | `drained` \| `goal` \| `budget` (для continuous) | `drained` |
| `skip` | стадии, отключаемые **на этот запуск** (`analysis`/`develop`/`testing`/`deploy`, через запятую) | — |
| `dry_run` | план без выполнения | `false` |

**Отключённые стадии.** Эффективный список пауз = `orchestrator.disabled_stages` из профиля
(постоянные, ставит команда `/stage`) ∪ `skip:` из аргумента (разовые, только этот запуск).
Team Lead отключённой стадии НЕ запускается — его агенты не тратят токены, задачи держатся
в буфере перед стадией (HELD, см. Шаг 4). Управление постоянными паузами — `/stage`.

### Очередь и скоуп — ГЛАВНОЕ

Оркестратор крутит **активный пайплайн** и **никогда не берёт из `Backlog`**. Входная очередь —
колонка **`Sprint`**: задачи туда кладёт человек — перетаскиванием на доске GitHub **или**
`/sprint add #N` (то же самое: `kanban_set N Sprint`). Всё, что в очереди `Sprint` и уже
в работе, оркестратор гоняет по стадиям до `Done` и **лупит по кругу**, пока очередь и in-flight
не опустеют.

> **Инвариант «по факту, без домыслов».** Множество работы берётся ИСКЛЮЧИТЕЛЬНО из живого
> `kb_dump` каждый тик: issue со `Status ∈ {Sprint, Analysis, Ready for Dev, In Development,
> Code Review, Testing, Ready to Deploy, Deploy}` (всё, кроме `Backlog` и `Done`). Оркестратор
> НЕ ведёт свой список, НЕ решает, что «должно» быть в работе, и НЕ кладёт задачи в очередь сам
> (кроме авто-бага, наследующего пайплайн родителя). Как задача попала в `Sprint` — рукой на
> доске или `/sprint add` — ему безразлично: он читает только факт (`Status`). Есть задачи в этом
> множестве → берёт в работу. Нет → **ничего не делает** (Шаг 6, «очередь пуста»).

- `scope=board` (дефолт) = весь активный пайплайн (колонки `Sprint`…`Deploy`). Входная точка — `Sprint`.
- `scope=backlog` / `scope=all` — **явный escape** к интейку (`Backlog`). Только ручные
  операции, с предупреждением; автопилот их не использует.
- `scope=<колонка>` / `#N` — сужение **внутри** пайплайна (напр. `scope=sprint` — разобрать только очередь).

> Поле `Sprint` и именованные спринты (`current_sprint`) в оркестрации **больше не используются** —
> очередь это колонка `Status=Sprint`. Легаси-поле `Sprint` на доске, если осталось, игнорируется.

### Пресеты (в т.ч. как разворачиваются алиасы)

| Ввод | Разворачивается в |
|---|---|
| `/orchestrate` | `mode=continuous concurrency=auto scope=board until=drained` — **автопилот по очереди** |
| `/orchestrate once` | `mode=once concurrency=seq scope=board` — один right-to-left проход (**= /sweep**) |
| `/orchestrate swarm` | `mode=once concurrency=parallel scope=board` (**= /swarm**) |
| `/orchestrate <колонка>` | `mode=once concurrency=seq scope=<колонка>` |
| `/orchestrate <колонка> #N #M` | `mode=once scope=<колонка>` только по этим issue |
| `/orchestrate #N` | `mode=continuous scope=#N until=goal` — довести один issue до Done |
| `/orchestrate dry-run` | текущий пресет + `dry_run=true` |

Колонки-аргументы: `sprint`, `ready-for-dev`, `testing`, `ready-to-deploy` (маппинг на Status
как в `/pick`). Транзитные `Code Review`/`Deploy` таргетить нельзя — ими владеют dev-lead/ops-lead.

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

## Шаг 2 — OBSERVE (снимок доски → активный пайплайн)

```bash
kb_dump > "${TMPDIR:-/tmp}/orch.json"
```

Один дамп даёт все issue со всеми полями (Status/…/**Parked**). **Сузь до scope
ПО ФАКТУ** — это и есть множество работы; ничего не додумывай:

```bash
# по умолчанию scope=board: активный пайплайн — всё, кроме Backlog и Done
jq '[.[] | (.status // "") as $s
     | select($s!="" and $s!="Backlog" and $s!="Done")]' "${TMPDIR:-/tmp}/orch.json" \
  > "${TMPDIR:-/tmp}/orch.scope.json"
# scope=backlog → select(.status=="Backlog") ; scope=all → без фильтра ;
# scope=<колонка>/#N → доп. фильтр (напр. scope=sprint → select(.status=="Sprint"))
```

**Если срез пуст** (в колонках `Sprint`…`Deploy` нет ни одной issue) → оркестратор **ничего не
делает**: сразу Шаг 6, стоп-причина `EMPTY` («очередь пуста — положи задачи в колонку `Sprint`:
перетащи на доске или `/sprint add #N`»). Никаких попыток «найти работу» в бэклоге.

Посчитай **board_score** — сумму индексов стадий (мера прогресса) по срезу:

```
index: Sprint 1 · Analysis 2 · Ready for Dev 3 · In Development 4 · Code Review 5
     · Testing 6 · Ready to Deploy 7 · Deploy 8 · Done 9   (Backlog 0 — вне скоупа)
board_score = Σ index(status) по всем не-Parked issue в срезе пайплайна
```

```bash
jq '[.[] | select((.parked // "no")=="no") | .status as $s |
     (["Backlog","Sprint","Analysis","Ready for Dev","In Development","Code Review","Testing","Ready to Deploy","Deploy","Done"]
      | index($s)) // 0] | add' "${TMPDIR:-/tmp}/orch.scope.json"
```

---

## Шаг 3 — DIAGNOSE

1. **WIP / capacity** (`wip_limit = quality.wip_limit`, default 5) — считаем **по срезу пайплайна**
   (`orch.scope.json`), а не по всей доске:
   ```
   dev_wip  = count(In Development) + count(Code Review)
   test_wip = count(Testing)
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
In Development → Ready for Dev → Analysis → Sprint
```
`Backlog` во фронт **не входит** — это сырой интейк, автопилот его не трогает.

Ограничения:
- `Ready for Dev` → бери не больше `dev_capacity` (остальное — SKIPPED (WIP)).
- `Testing` → в рамках `test_capacity`.
- `Ready to Deploy` → только issue с `QA=passed` И `Security=passed`.
- `Sprint` (очередь) → analysis-lead забирает в `Analysis` (в рамках WIP; `take` ограничивает сколько взять за тик).
- `take=1` (пресет `/pick`) → взять ровно одну верхнюю по приоритету из scope-колонки.
- `scope=<колонка>` → только эта колонка; `scope=#N` → только этот issue (и его дети-stories).

Сгруппируй фронт по Team Lead: **ops-lead** (Ready to Deploy) · **qa-lead** (Testing) ·
**dev-lead** (In Development + Ready for Dev) · **analysis-lead** (Sprint).

### Отключённые стадии (HELD)

Возьми эффективный список пауз (профиль `orchestrator.disabled_stages` ∪ аргумент `skip:`).
Стадия → Team Lead → буфер, где задачи держатся:

| Стадия | Team Lead исключается | Буфер (HELD) |
|---|---|---|
| `analysis` | analysis-lead | Sprint |
| `develop` | dev-lead | Ready for Dev |
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
Queue (Sprint): {q} задач · in-flight (Analysis…Deploy): {f} задач
Policy: mode={..} concurrency={..} scope={..} until={..}
WIP: Dev {dev_wip}/{wip_limit} (cap {dev_capacity}) · Test {test_wip}/{wip_limit} (cap {test_capacity})

DISABLED stages: {список отключённых или «нет»}

FRONTIER (right-to-left):
  OPS   → #N … (Ready to Deploy→Done)          [строку пропусти, если deploy off]
  QA    → #N … (Testing→Ready to Deploy)        [пропусти, если testing off]
  DEV   → #N … (In Dev→Review→Testing) | #N … (Ready for Dev→In Dev)   [приём из Ready for Dev пропусти, если develop off]
  ANLZ  → #N … (Sprint→Analysis→Ready for Dev)  [пропусти, если analysis off]

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

### ANALYSIS (Sprint — очередь)
```
Agent(subagent_type="analysis-lead"[, run_in_background=true], prompt="ORCHESTRATE — ANALYSIS LEAD.
Read .claude/project-profile.md, CLAUDE.md, ARCHITECTURE.md (if exists).
Задачи из очереди Sprint: {список из колонки Sprint}.
Per задача: G1 → analyst (если feature — декомпозиция → stories + docs/specs/feature-N-*.md, SDC 8 слотов, SD-1..SD-5; если story/bug — уточнение spec) → architect (docs/arch/feature-N-*.md, ERD/API/ADR по budget-threshold). Разные задачи — ПАРАЛЛЕЛЬНО; одна фича analyst→architect последовательно.
Дочерние stories: kb_meta N type=story priority=* size=* component=* → kanban_set N 'Ready for Dev'.
G2 → kanban_set N 'Ready for Dev'. Стадию — ТОЛЬКО kanban_set. Report: ANALYZED (stories/spec/arch)/FAILED.")
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
| **EMPTY** | в пайплайне нет ни одной issue (колонки `Sprint`…`Deploy` пусты) | 🈳 нечего делать |
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
Queue (Sprint): {q} задач · in-flight: {f} · Done(+{n} за прогон)
Policy: mode={..} concurrency={..} scope={..} until={..}
Ticks: {tick} · Duration: ~{time}

PROCESSED (right-to-left):
  OPS  → #N deployed / parent closed
  QA   → #N QA=passed | #N QA=failed (bug #B)
  DEV  → #N developed (coverage N%, Security/JavaReview/FrontendReview)
  ANLZ → #N analyzed ({k} stories) (Sprint→Analysis)

HELD (стадии на паузе — токены не тратились):
  ⏸️ deploy off → #N #M ждут в Ready to Deploy
  ⏸️ testing off → #K ждёт в Testing
PARKED (нужен человек):
  🅿️ #N — oscillation (откатывался {fix_loop_max}×)
  🅿️ #N — human (ждёт `APPROVE PRODUCTION DEPLOY`)
  🅿️ #N — deps (цикл/глубина >10)

BLOCKED (зависимости): 🚫 #N — by #M
SKIPPED (WIP): ⊘ #N

STOP REASON: {EMPTY очередь пуста — положи задачи в колонку Sprint (перетащи или /sprint add #N) |
              GOAL всё Done | HELD стадии {X} отключены, {N} задач ждут |
              DRAINED остаток заблокирован | STALL нет прогресса {stall_rounds}× |
              BUDGET {max_ticks} тиков/лимит токенов | HUMAN ждём APPROVE}

BOARD AFTER: Sprint(очередь) {n} · Analysis {n} · Ready for Dev {n} · In Dev {n}/{wip} ·
             Code Review {n} · Testing {n}/{wip} · Ready to Deploy {n} · Deploy {n} · Done(+{n})

NEXT: {что человеку сделать — положить задачи в очередь (перетащить в колонку Sprint или /sprint add #N),
       включить стадию (/stage on deploy), разпарковать #N, дать APPROVE, разблокировать deps; либо «Очередь пуста 🎉»}
```

В `mode=continuous`, если завершились по HUMAN/STALL/BUDGET и хочешь, чтобы петля продолжилась
после вмешательства человека — перезапусти `/orchestrate` тем же пресетом.

---

## Примеры

```bash
/orchestrate                      # автопилот: крутит очередь Sprint → пайплайн до drained/stall/budget/human
/orchestrate dry-run              # план автопилота без выполнения
/orchestrate once                 # один right-to-left проход (= /sweep)
/orchestrate swarm                # один параллельный проход (= /swarm)
/orchestrate sprint               # разобрать только очередь (Sprint→Analysis)
/orchestrate testing              # добить колонку Testing
/orchestrate ready-for-dev #97 #98  # разработать только эти две story
/orchestrate #52                  # довести фичу #52 (и её stories) до Done
```
