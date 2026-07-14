# Спринтовая модель доски

> **Статус:** ✅ РЕАЛИЗОВАНО (v2 — спринт как Status-колонка). Ядро — `commands/orchestrate.md`
> (scope=sprint по умолчанию = колонка `Sprint` + in-flight), команда `commands/sprint.md`,
> опция `Sprint` поля `Status`.
> **Цель:** видимая на доске колонка-обязательство `Sprint`, куда человек кладёт задачи; агенты
> берут новую работу **только оттуда** и ведут до `Done`; `Backlog` (сырой интейк) не трогают.

---

## 1. Модель (v2 — колонка, не поле)

Спринт — это **опция поля `Status`**: колонка `Sprint` сразу после `Backlog`.

```
Backlog ──(человек: /sprint add или drag)──▶ Sprint ──▶ Analysis / Ready for Dev ──▶ … ──▶ Done
(сырой интейк,                              (взято                (обычный пайплайн)
 агенты игнорят)                             в работу)
```

| Колонка | Кто ставит | Смысл |
|---|---|---|
| `Backlog` | человек (`/feature`, ручные issue) | сырой интейк/икотека — рефайнинг рукой, **агенты не берут** |
| `Sprint` | **человек** (`/sprint add #N` или перетаскивание) | взято в работу — **единственный вход оркестратора** |
| `Analysis … Deploy` | Team Leads (`kanban_set`) | стадии конвейера (in-flight) |
| `Done` | ops-lead (G8) | терминал |

**Единственное правило (и есть весь запрос):**
> Оркестратор берёт НОВОЕ в работу только из колонки `Sprint`, ведёт всё in-flight до `Done`,
> и **никогда не трогает `Backlog`**. Рабочее множество = `Status ∈ {Sprint, Analysis…Deploy}`,
> читается из живого `kb_dump` каждый тик — по факту, без домыслов.

**Роутинг приёма из `Sprint` по `Type`:** `feature`/`epic` → analysis-lead (`Sprint → Analysis`, G1);
dev-ready (`story`/`bug`/`tech-debt`/`hotfix`/`spike`) → dev-lead (`Sprint → In Development`, G3).
Дочерние stories из анализа ложатся в `Ready for Dev` (обычный in-flight).

---

## 2. Почему колонка, а не поле (пересмотр v1)

**v1 (устарела):** спринт был отдельным single-select полем `Sprint` (`Sprint 1/2/…`) + указатель
`orchestrator.current_sprint` в профиле. Плюс — батчи/итерации переживали движение по стадиям.
Минус — спринт был **не виден колонкой на доске** и ощущался «спрятанным» (поле + ключ в конфиге),
а активный спринт жил в git-файле, а не на доске.

**v2 (текущая):** одна колонка `Sprint`. Плюсы:
- **Видимость**: спринт — колонка на доске, задачу двигаешь мышкой, как в обычном Kanban.
- **Простота**: нет поля `Sprint`, батчей, `current_sprint`, `/sprint activate/close`, carry-over.
- «Взять в работу» = перетащить `Backlog → Sprint`. Оркестратор видит по факту (Status).

Компромисс: нет именованных батчей (Sprint 1 vs Sprint 2) и нативного burndown по итерации.
Для текущего запроса это не нужно — `Sprint` работает как непрерывная колонка «Selected for Work».

---

## 3. Структура (один Project, стандартный Board-view)

Одна физическая доска (Project). Стандартный view (Board, Group by `Status`) уже показывает
колонки `Backlog → Sprint → Analysis → …`. Отдельные view опциональны (`/setup-board §3.5`):
- **Board** — Group by `Status`, все колонки.
- **Backlog** — Table, фильтр `status:Backlog` (сырой интейк).

Никакой кросс-проектной автоматизации: «взять в работу» = сменить `Status` на `Sprint`.

---

## 4. Команда `/sprint`

```
/sprint                # доска спринта: колонка Sprint + всё in-flight, прогресс
/sprint add #N #M …    # ВЗЯТЬ в работу — kanban_set N "Sprint" (gate одобрения человеком)
/sprint remove #N      # вернуть в Backlog (снять с автопилота, только для ещё не начатых)
/sprint list           # распределение по колонкам (Sprint / in-flight / Backlog / Done)
```

`/sprint add` — единственный способ, которым работа попадает под автопилот. Эквивалент —
перетащить карточку в колонку `Sprint`. Убраны `new`/`activate`/`close` (батчей нет).

---

## 5. Роутинг авто-задач

- **Баг/регресс на идущей задаче** (reviewers при FAIL, test-case-writer при провале AC) →
  **сразу в колонку `Sprint`** (`kanban_set BUG "Sprint"`): блокирует идущую работу, чинится
  в этом же прогоне; оркестратор возьмёт и доведёт до `Done`. Связь — `Blocks: #{story}`.
- **Проактивный tech-debt** (postdeploy.sh / G9, ручные идеи) → в `Backlog` на триаж.

---

## 6. Как это выглядит в работе

```
1. Новые задачи   → падают в Backlog. Оркестратор их не трогает.
2. Рефайнинг      → /analyze фич (при необходимости), правки — рукой, всё ещё в Backlog.
3. Взять в работу → /sprint add #101 #102 #103  (Status → Sprint)   ← твой gate
4. Исполнение     → /orchestrate  → берёт из Sprint + ведёт всё in-flight до Done
5. Готово         → колонка пуста, in-flight пуст → стоп-причина GOAL/EMPTY
```

---

## 7. Состав изменений (v1 → v2)

| # | Файл | Что |
|---|---|---|
| 1 | `commands/setup-board.md` | опция `Sprint` в поле `Status` (после Backlog); поле `Sprint` больше не создаётся |
| 2 | `agents/kanban-board-sync.md` | `Sprint` — Status-опция; убраны поле `Sprint`, `sprint`-ключ в `kb_dump`, хелперы `current_sprint`/`sprint_query`/`kb_sprint`; новые `sprint_queue`, `kb_queue` |
| 3 | `project-profile.md` | убраны `current_sprint`/`sprint_model`/`sprint_carryover` |
| 4 | `commands/orchestrate.md` | scope=board (дефолт) = активный пайплайн (`Sprint`…`Deploy`); scope=sprint = колонка `Sprint`; приём только из `Sprint`; board_score с Sprint=1; EMPTY = пайплайн пуст |
| 5 | `commands/sprint.md` | управление колонкой `Sprint` (add/remove/list) |
| 6 | `commands/board.md`, `commands/stage.md`, алиасы `pick/sweep/swarm` | scope и буферы по колонке `Sprint` |
| 7 | `agents/quality-gates.md`, `agents/analysis-lead.md` | G1: `Sprint → Analysis`; G3: вход и из `Sprint` (dev-ready) |
| 8 | `AGENTS_FRAMEWORK.md`, `ORCHESTRATOR_DESIGN.md` | описание модели |
