# Единый оркестратор задач — Loop Engineering (design proposal)

> **Статус:** ✅ РЕАЛИЗОВАНО. Ядро — `.claude/commands/orchestrate.md`.
> **Автор:** дизайн-сессия по loop-инженерии.
> **Решения:** имя — `/orchestrate`; `/sweep` · `/swarm` · `/pick` оставлены тонкими
> алиасами-пресетами (обратная совместимость); `/kanban` оставлен отдельной командой
> (создаёт фичу + прогоняет); парковка — новое поле доски `Parked`; дефолт `mode` —
> `continuous` (автопилот). Этот документ — концептуальная справка к коду.

Документ описывает переход оркестрации с **open-loop pipeline** (человек прогоняет проход
за проходом) на **closed-loop reconciler** (петля сама сводит доску к цели), и предлагает
единый оркестратор `/orchestrate`, для которого текущие команды становятся пресетами.

---

## 1. Проблема — сейчас оркестрация open-loop

Фреймворк — это, по сути, готовая control system: у него есть store (доска), state machine
(agent-per-status), transition guards (G1–G8), backpressure (WIP), actuators (Team Leads),
DAG-ordering и per-issue circuit breaker (`fix_loop_max`). Не хватает **одного** — замкнутой
петли, которая крутит систему к «всё Done» без нажатия кнопки человеком на каждом шаге.

Три существующие команды — это три разных **одиночных тика** без re-observe и без само-остановки:

| Команда | Что делает | Петля? |
|---|---|---|
| `/pick <col>` | 1 действие над 1 issue по приоритету | нет |
| `/sweep` | 1 проход right-to-left, последовательно | нет (проход, не re-scan) |
| `/swarm` | 1 проход, все Team Leads параллельно | нет |
| `/kanban <feat>` | 1 фича через 5 стадий последовательно | нет |

Единственные настоящие петли — локальные fix-loops (G5 review-fail, G6 qa-fail → назад
влево), ограниченные `fix_loop_max` (default 3) → эскалация человеку. Глобального reconciler'а нет.

---

## 2. Концепция — control loop / reconciler

Модель контроллера Kubernetes: желаемое состояние (все issue = `Done`), фактическое (доска
сейчас), контроллер непрерывно сокращает разницу. Отличия от pipeline:

| Свойство | Pipeline (сейчас) | Control loop |
|---|---|---|
| Управление | человек запускает каждый проход | петля сама решает «тикнуть снова» |
| Состояние | в проходе | вынесено в доску → петля stateless / resumable |
| «Что дальше» | фиксированный порядок | **политика** выбирает из текущего состояния |
| Когда стоп | «конец списка» | явный **предикат завершения** |

```
        ┌───────────────────────────────────────────────┐
        │                                               │
        ▼                                               │
   OBSERVE ─► DIAGNOSE ─► PLAN ─► ACT ─► OBSERVE' ──────►│  termination?
  (kb_dump)  (что можно  (фронт) (Team   (собрать          │
             двигать)            Leads)  результат)         │
        │                                               │
        └──────── termination? ── нет ──────────────────┘
                       │ да
                       ▼
                  STOP + отчёт (почему остановились + что осталось)
```

Инженерная петля ≠ `while(true)`. Её отличают три вещи:
1. **Termination predicate** — явное условие остановки.
2. **Progress detection** — детектор застоя (нет прогресса K тиков ∧ никто не в работе → «заклинило»).
3. **Pacing** — петля *спит*, когда ждёт внешнего (деплой, CI, человеческий APPROVE), а не опрашивает вхолостую.

---

## 3. Reconcile tick (ядро оркестратора)

```
TICK (reconcile):
  1. OBSERVE   kb_dump → снимок доски: все issues, все поля, deps
  2. DIAGNOSE
       • WIP по колонкам, capacity = wip_limit - occupied
       • DAG: у кого зависимости resolved (blocker closed / Status=Done)
       • oscillation: issue, отскочивший In-Dev↔Testing ≥ fix_loop_max → PARK(oscillation)
       • human-gate: Ready to Deploy + prod без APPROVE → PARK(human)
  3. PLAN (политика = frontier selector)
       • фронт = issues, которые МОГУТ сдвинуться сейчас:
            precondition гейта выполнен ∧ deps resolved ∧ есть WIP-capacity
       • порядок: right-to-left × Priority(critical→high→medium→low), ties → меньший #
       • группировка по Team Lead
  4. ACT       диспатч Team Leads
       • concurrency=1  → последовательно (sweep-like)
       • concurrency=N  → в одном сообщении, run_in_background=true (swarm-like)
  5. OBSERVE'  собрать результаты (агенты уже записали поля доски)
  6. TERMINATION?  (см. §4)
  7. PACE
       ждём внешнего (deploy/CI/human) → ScheduleWakeup(pace_seconds) → tick
       иначе                                                          → tick сразу
```

Порядок фронта — тот же, что система уже использует: **колонка → dependency readiness
(skip BLOCKED) → Priority → WIP-cutoff**. Новое только одно: после ACT петля **re-observ'ит**
и решает тикнуть снова.

---

## 4. Termination predicates (сердце loop-инженерии)

Петля останавливается по **явному** предикату, а не по «список кончился». Отчёт всегда
сообщает, *почему* остановились и что осталось.

| Предикат | Условие | Действие |
|---|---|---|
| **GOAL** | все не-parked issue = `Done` | STOP(success) |
| **DRAINED** | фронт пуст, остаток весь blocked (deps/human/parked) | STOP + отчёт блокеров |
| **STALL** | `board_score` не вырос `stall_rounds` тиков ∧ никто не in-flight | STOP + «заклинило» + фронт-блокеры |
| **BUDGET** | исчерпан `budget_tokens` / `max_ticks` / дедлайн | STOP + остаток плана |
| **HUMAN** | остались только prod-approve-pending | STOP + запрос `APPROVE PRODUCTION DEPLOY` |

### Progress signal
`board_score = Σ stage_index(issue)` (индекс колонки, Backlog=0 · Sprint=1 … Done=9). Плюс продвижение
полей (`Security: pending→passed`). Тик сделал прогресс ⟺ score строго вырос ИЛИ поле
продвинулось. Если прогресса нет `stall_rounds` тиков подряд и нет in-flight агентов → **STALL**.
Это адаптация паттерна *loop-until-dry*: «dry» = нет прироста score.

### Oscillation / parking
Issue, отскакивающий In-Dev↔Testing (или зацикленный на review-fix), уже ограничен
`fix_loop_max` на уровне issue. Глобальная петля дополнительно **паркует** такой issue
(`Parked=oscillation`), убирает из фронта (чтобы не жёг тики) и выносит человеку в отчёт.

---

## 5. Политика — унификация sweep/swarm/pick/kanban

Единый оркестратор = одна петля + пространство параметров `{scope, concurrency, mode,
termination, budget}`. Старые команды — точки в этом пространстве (тонкие алиасы-пресеты):

| Старая команда | `/orchestrate` с политикой |
|---|---|
| `/pick <col>` | `scope=<col>` `concurrency=1` `mode=single-tick` `take=1` |
| `/sweep` | `scope=board` `concurrency=1` `mode=single-tick` (right-to-left) |
| `/swarm` | `scope=board` `concurrency=auto` `mode=single-tick` |
| `/kanban <feat>` | `scope=<new-feature>` `concurrency=1` `mode=continuous` `until=Done` |
| **автопилот (новое)** | `scope=board` `concurrency=auto` `mode=continuous` `until=drained` |

Единственное принципиально новое значение — `mode=continuous`: петля тикает сама до
срабатывания termination. Всё остальное уже реализовано в `sweep.md`/`swarm.md` — просто
разнесено по двум файлам (WIP-формула и dispatch-промпты сейчас дублируются в обоих).

---

## 6. Изменения в репозитории (минимальный набор)

### A. Блок политики в `.claude/project-profile.md`
```yaml
orchestrator:
  mode: single-tick          # single-tick | continuous
  concurrency: auto          # 1 (sweep) | N | auto (swarm)
  scope: board               # board | <column> | #<issue>
  max_ticks: 20              # жёсткий потолок петли
  stall_rounds: 2            # порог «заклинило» (dry-round)
  budget_tokens: null        # опциональный потолок токенов на прогон
  pace_seconds: 1200         # сон при ожидании внешнего (human/CI/deploy)
  stop_on_human_gate: true   # park prod-approve и остановиться
```

### B. Новое поле доски `Parked` (single-writer = оркестратор)
`single-select {no, deps, human, oscillation, budget}`. Держит single-writer-дисциплину,
убирает заклинившие issue из фронта, даёт человеку явный список «разбери меня».
Устанавливается через `/setup-board`.

### C. `.claude/commands/orchestrate.md` — сам контроллер (шаги §3)
Существующие `/sweep`/`/swarm`/`/pick` → 5-строчные алиасы, вызывающие `/orchestrate`
с пресетом (§5). Обратная совместимость сохраняется.

### D. Развести два бюджета
`.claude/system/budget.md` = бюджет **архитектурной сложности** (ratchet → ADR) — не трогаем.
Loop-бюджет (токены/тики/время) — **другое**, живёт в `orchestrator.budget_*`. Явно
разграничить в терминах, чтобы не путать complexity-budget и runtime-budget.

---

## 7. Два регистра реализации

| | **A. Prompt-level** (`orchestrate.md`) | **B. Deterministic** (Workflow-скрипт) |
|---|---|---|
| Стиль | как все текущие команды (.md-инструкция) | JS-скрипт: реальный `while` + `budget` |
| Termination / budget / dry | model-driven (Claude «решает тикнуть») | код → настоящие гарантии |
| Порог входа | ноль, вписывается сразу | нужен opt-in на Workflow-tool |
| Когда | обычный автопилот доски | большие/долгие прогоны, детерминированность петли |

**Рекомендация:** начать с **A** (ноль новых зависимостей, вписывается в prompt-архитектуру);
`continuous` на больших прогонах при желании поднять до **B**, где `loop-until-drained`,
`stall_rounds` и `budget` становятся кодом, а не инструкцией.

---

## 8. Pacing — примитивы Claude Code

- Фоновые Team Leads (`run_in_background`) харнесс сам возвращает по завершении — **polling не нужен**, петля просто `await`-ит.
- `ScheduleWakeup` нужен только для *внешнего* ожидания:
  - `~270s` — опрос катящегося деплоя / CI (кэш промпта тёплый, <5 мин);
  - `1200s+` — ожидание человеческого `APPROVE PRODUCTION DEPLOY` (нет смысла проверять чаще).
- `mode=single-tick` НЕ использует ScheduleWakeup — один тик и отчёт (полная обратная совместимость с текущим `/sweep`).

---

## 9. Что это даёт

- **Человек больше не петля** — `/orchestrate continuous` крутит доску до drained/stall/budget/human-gate сам.
- **Явная остановка** вместо «прогнал один раз» — отчёт говорит почему стоп и что осталось.
- **Детектор застоя** — осцилляция и глухие блокеры паркуются, а не жгут тики.
- **Одна точка правды оркестрации** — 4 пересекающиеся команды → 1 контроллер + пресеты; уходит дублирование WIP-формулы и dispatch-промптов между `sweep.md` и `swarm.md`.

---

## 10. Пауза стадий (`/stage`)

Иногда стадию надо временно выключить: «пока не деплою» или «не пишу тест-кейсы — экономлю
токены». Реализовано как **пауза (hold), не пропуск (skip)**:

- отключённая стадия = её Team Lead **не запускается** (ноль токенов);
- задачи копятся в **буфере перед стадией** и ждут; ничего не деградирует и не проскакивает гейт;
- включил обратно (`/stage on`) — накопленное течёт дальше.

Почему hold, а не skip: пропуск = деплой непротестированного кода / обход security. Ломает
идею гейтов. Пауза безопасна и покрывает оба сценария (не деплоить / не тратить токены на TC).

| Стадия | Team Lead | Буфер (где ждут) |
|---|---|---|
| `analysis` | analysis-lead | `Sprint` (feature/epic) |
| `develop` | dev-lead | Ready for Dev (+ dev-ready в `Sprint`) |
| `testing` | qa-lead | Testing |
| `deploy` | ops-lead | Ready to Deploy |

Security-ревью отключить нельзя (защитный гейт внутри `develop`, не стадия). Пауза дорабатывает
уже начатые задачи (drain) — worktree/деплой не бросаются на полдороге; стопится только приём новых.

Хранение: `orchestrator.disabled_stages` в профиле (постоянно, ставит `/stage`) ∪ токен
`skip:` в `/orchestrate` (разово). Новый стоп-предикат **HELD** (проверяется перед DRAINED)
не даёт отчёту соврать «Board clear», когда задачи держатся из-за паузы. Команда — `.claude/commands/stage.md`.

## 11. Принятые решения

1. **Регистр:** A (prompt-level) — вписывается в текущую .md-архитектуру, ноль зависимостей.
   B (Workflow-скрипт) остаётся апгрейдом на будущее для больших continuous-прогонов.
2. **`Parked`** — новое single-select поле доски (`no/deps/human/oscillation/budget`),
   single-writer = оркестратор. Заведено в `/setup-board` и читается `kb_dump`.
3. **Имя команды:** `/orchestrate`.
4. **`/sweep`/`/swarm`/`/pick`** — оставлены тонкими алиасами-пресетами (обратная совместимость).
   `/kanban` не трогали — он создаёт фичу и прогоняет, это отдельный сценарий.
5. **Дефолт `mode`:** `continuous` (автопилот) — это и есть заявленная новая возможность;
   `/orchestrate once` даёт старое безопасное поведение одного прохода.

## 12. Не сделано / на потом

- Регистр B (детерминированный Workflow-скрипт) — если continuous-прогоны станут длинными
  и захочется, чтобы `stall`/`budget`/`loop-until-drained` были кодом, а не инструкцией.
- Тонкая настройка авто-распарковки `oscillation` (сейчас снимает только человек).
- Проверка на реальной доске (нужны `board.env` + инициализированный проект — сейчас
  `initialized: false`).
