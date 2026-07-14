---
description: "Kanban: Board. Доска: колонки, WIP, блокировки, метрики. По умолчанию — работа (Sprint + in-flight). /board | /board backlog | /board all"
argument-hint: "<пусто=работа (Sprint+in-flight) | backlog | all>"
---

# KANBAN — Board Status

Собери и покажи текущее состояние Kanban-доски проекта.

## Правила формата отчёта (СТРОГО — нарушение = плохой отчёт)

Отчёт читает человек, который не обязан знать внутренний жаргон агентской системы.

1. **Задача = `#номер` + заголовок.** Каждое упоминание задачи — только в виде
   `#527 «Story 3: Экспорт заказов …»` (пример). ЗАПРЕЩЕНО ссылаться на задачу только
   по префиксу из её заголовка («Story 3», «PERF-12», «API-08») — эти префиксы существуют
   лишь внутри заголовков issue, без `#номера` они непонятны.
2. **Никаких кодов гейтов (G1–G8) в отчёте.** Гейты — внутренний механизм агентов
   (`.claude/agents/quality-gates.md`). Для человека пиши название перехода словами:
   не «пройти G4», а «unit-тесты зелёные → перенос в Code Review».
3. **Терминология — только канбан + поля доски.** Единица работы — issue. Типы — из поля
   Type (feature / story / bug / tech-debt). Стадии — только названиями колонок доски.
   Иерархия: Feature (родительский issue) → его Stories. Не изобретай своих группировок
   и кодовых имён; если группируешь Backlog — только по полям Type / Priority / Component
   и явно это указывай.
4. **Не выдумывай данных.** Всё в отчёте должно быть выводимо из дампа доски, тел issue
   или git. Если чего-то нет в данных (assignee, возраст, причина блокировки) — пиши
   «нет данных», а не предположение.
5. **Пиши полными фразами, без телеграфного стиля.** Аббревиатуру можно использовать,
   только если она расшифрована в этом же отчёте.

## Алгоритм (АВТОНОМНО)

### 0. Scope (что показываем)

| `/board …` | Что |
|---|---|
| *(пусто)* | **работа**: колонка `Sprint` + всё in-flight (`Analysis`…`Deploy`) — то, по чему работает оркестратор |
| `backlog` | интейк: `Status=Backlog` (сырые задачи, ещё не взятые в работу) |
| `all` | вся доска (работа + бэклог + Done) |

Ниже все `jq`-фильтры дополни отбором по scope: по умолчанию
`select(.status!="Backlog" and .status!="Done")`; для `backlog` — `select(.status=="Backlog")`;
для `all` — без фильтра. В заголовке отчёта укажи scope. Колонку `Sprint` показывай отдельно —
это «взято в работу, ждёт приёма оркестратором».

### 1. Сделай один дамп доски

Источник правды о ВСЁМ состоянии — поля Project board. Сделай **один** дамп всех item'ов
со всеми полями через хелпер `kb_dump` из `.claude/agents/kanban-board-sync.md` и далее
группируй/считай локально через jq — это даёт и колонки, и WIP, и метрики из одного вызова.

```bash
kb_dump > "${TMPDIR:-/tmp}/board.json"     # JSON-массив: {number,title,state,status,type,priority,size,component,security,javareview,frontendreview,qa,deploy,coverage}

# Колонки (группировка по полю Status):
jq -r '.[] | select(.status=="Backlog")        | "#\(.number)\t\(.title)"' "${TMPDIR:-/tmp}/board.json"
jq -r '.[] | select(.status=="Sprint")          | "#\(.number)\t\(.title)"' "${TMPDIR:-/tmp}/board.json"
jq -r '.[] | select(.status=="Analysis")        | "#\(.number)\t\(.title)"' "${TMPDIR:-/tmp}/board.json"
jq -r '.[] | select(.status=="Ready for Dev")    | "#\(.number)\t\(.title)"' "${TMPDIR:-/tmp}/board.json"
jq -r '.[] | select(.status=="In Development")   | "#\(.number)\t\(.title)"' "${TMPDIR:-/tmp}/board.json"
jq -r '.[] | select(.status=="Code Review")      | "#\(.number)\t\(.title)"' "${TMPDIR:-/tmp}/board.json"
jq -r '.[] | select(.status=="Testing")          | "#\(.number)\t\(.title)"' "${TMPDIR:-/tmp}/board.json"
jq -r '.[] | select(.status=="Ready to Deploy")  | "#\(.number)\t\(.title)"' "${TMPDIR:-/tmp}/board.json"
jq -r '.[] | select(.status=="Deploy")           | "#\(.number)\t\(.title)"' "${TMPDIR:-/tmp}/board.json"
jq -r '.[] | select(.status=="Done")             | "#\(.number)\t\(.title)"' "${TMPDIR:-/tmp}/board.json"   # для Done покажи последние 10
```

### 2. Построй Kanban Board

Если в колонке ≤ 10 задач — перечисли все (каждую как `#N — заголовок`).
Если больше 10 (обычно Backlog) — покажи число задач, затем топ-5 по Priority,
затем остаток сгруппируй по полю Type с количеством (например «feature: 34, story: 17»).
Родительскую Feature и её Stories показывай вместе: сначала `#518 (Feature)`,
под ней — её stories с номерами.

Выведи таблицу:

```
KANBAN BOARD
{date}

| Backlog | Sprint | Analysis | Ready for Dev | In Development | Code Review | Testing | Ready to Deploy | Deploy | Done (last 10) |
|---------|--------|----------|---------------|----------------|-------------|---------|-----------------|--------|-----------------|
| #{N}    | #{N}   | #{N}     | #{N}          | #{N}           | #{N}        | #{N}    | #{N}            | #{N}   | #{N}            |
| {title} | {title}| {title}  | {title}       | {title}        | {title}     | {title} | {title}         | {title}| {title}         |

WIP LIMITS (лимит {wip_limit} = quality.wip_limit из .claude/project-profile.md, default 5):
  In Development: {count}/{wip_limit} {OK/OVER}
  Code Review: {count}/{wip_limit} {OK/OVER}
  Testing: {count}/{wip_limit} {OK/OVER}

BLOCKED:
  #{N} — {reason}

METRICS:
  Total open: {N}
  Features: {N} | Stories: {N} | Bugs: {N}
  Priority: {critical} critical | {high} high | {medium} medium | {low} low
```

WIP и метрики считаются из того же дампа через jq по полям:

```bash
# WIP по колонкам:
jq '[.[]|select(.status=="In Development")] | length' "${TMPDIR:-/tmp}/board.json"   # In Development
jq '[.[]|select(.status=="Testing")]        | length' "${TMPDIR:-/tmp}/board.json"   # Testing

# Метрики по полям Type / Priority (только открытые):
jq '[.[]|select(.state=="OPEN")] | length' "${TMPDIR:-/tmp}/board.json"                          # Total open
jq -r '[.[]|select(.state=="OPEN")] | group_by(.type)     | map("\(.[0].type // "—"): \(length)")     | join(" | ")' "${TMPDIR:-/tmp}/board.json"
jq -r '[.[]|select(.state=="OPEN")] | group_by(.priority) | map("\(.[0].priority // "—"): \(length)") | join(" | ")' "${TMPDIR:-/tmp}/board.json"
```

### 2.5. Dependencies

Для каждого open issue — проверь `Blocked by:` / `Depends on:` / `Requires:` в body.
Если есть зависимости — покажи в секции BLOCKED:

```
DEPENDENCIES:
  🚫 #{N} "{title}" — blocked by #{M} (open, Status={column})
  🔓 #{K} "{title}" — all deps resolved, ready to proceed
```

### 3. Предупреждения

Выведи предупреждения если:
- WIP limit превышен в любой колонке
- Есть issues в колонке Status="In Development" старше 5 дней
- Есть issues в колонке Status="Testing" старше 3 дней
- Есть issues с полем Priority=critical не в колонках In Development/Testing
- Есть bugs без назначенного исполнителя
- Есть issues с полем Security=failed
- Есть issues с полем FrontendReview=failed
- Есть circular dependencies

### 4. Рекомендации

На основе состояния доски дай рекомендации:
- Если в работе (Sprint + in-flight) есть незавершённые задачи → предложи `/orchestrate` (автопилот)
- Если работа пуста, а в Backlog есть задачи → предложи `/sprint add #{N}` (взять в работу — колонка Sprint)
- Если в Ready to Deploy что-то ждёт, а деплой на паузе → напомни `/stage on deploy`
- Если Backlog пуст → предложи `/feature`
- Если есть блокировки → предложи решение

### 5. Sprint Standup View (Async Daily Standup)

Покажи дополнительно:

```
DAILY STANDUP (async)
{date}

DONE YESTERDAY (closed в последние 24ч):
  ✅ #{N} — {title}

IN PROGRESS TODAY:
  🔄 #{N} — {title} (developer: {assignee|unknown}, {age} days)

BLOCKED / NEEDS ATTENTION:
  🚫 #{N} — {reason}

SPRINT HEALTH:
  Velocity: {closed_this_week} stories/week
  Overdue (>3d in same column): {count}
  Critical issues open: {count}
```

**Использование /board для Scrum ceremonies:**
- **Sprint Planning**: показывает Backlog с приоритетами для выбора задач
- **Daily Standup**: секция 5 выше
- **Sprint Review**: смотри Done (last 10) + items с полем Deploy=staging
- **Retrospective**: смотри overdue + паттерны полей Security=failed + QA=failed
