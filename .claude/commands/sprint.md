---
description: "Спринт: взять задачи в работу. Спринт — это колонка Status на доске. /sprint | /sprint add #N… | /sprint remove #N… | /sprint list"
argument-hint: "<пусто=доска спринта | add #N… | remove #N… | list>"
---

# SPRINT — взять задачи в работу: $ARGUMENTS

**Спринт — это Status-колонка `Sprint`** на доске (между `Backlog` и `Analysis`), а не поле и не
батч. Модель простая:

```
Backlog (сырой интейк — агенты игнорят)  ──/sprint add──▶  Sprint (взято в работу)  ──▶ … ──▶  Done
```

- В `Backlog` падают все новые задачи (`/feature`, ручные issue). Оркестратор их **не трогает**.
- Кладёшь задачу в колонку `Sprint` (этой командой или перетаскиванием на доске) — это **gate**:
  единственный момент, когда работа попадает под автопилот `/orchestrate`.
- Оркестратор берёт НОВОЕ только из `Sprint`, ведёт всё in-flight до `Done`. Никаких «Sprint 1/2»,
  `current_sprint` и `/sprint activate` — модель упрощена до одной колонки.

Хелперы (`.claude/agents/kanban-board-sync.md`): `sprint_add`, `sprint_remove`, `sprint_query`,
`board_work`, `kanban_set`, `kb_dump`. Преамбула — `source .claude/board.env`.

---

## Разбор `$ARGUMENTS`

| Ввод | Действие |
|---|---|
| *(пусто)* | Доска спринта: колонка `Sprint` + всё in-flight, прогресс (Шаг «Доска») |
| `add #N [#M …]` | **Взять в работу** — `kanban_set N "Sprint"` (gate одобрения человеком) |
| `remove #N [#M …]` | Вернуть в бэклог — `kanban_set N "Backlog"` (снять с автопилота) |
| `list` | Сводка по колонкам работы (сколько в Sprint / in-flight / Done) |

---

## Доска спринта (пусто)

```bash
source .claude/board.env 2>/dev/null || { echo "Нет board.env — /init"; exit 1; }
echo "=== Sprint (ждут приёма оркестратором) ==="
sprint_query                       # number  title  (Status=Sprint)
echo "=== In-flight (в работе) ==="
board_work | grep -v -P '\tSprint\t'   # всё, кроме Backlog/Done, за вычетом Sprint
```
Выведи по колонкам (`Sprint` / Analysis / Ready for Dev / In Development / Code Review / Testing /
Ready to Deploy / Done), прогресс `Done/всего в работе`, и что осталось. Подскажи: `/orchestrate` — гнать до Done.

## add `#N …` (взять в работу — gate одобрения)

```bash
for N in <номера>; do sprint_add "$N"; done    # = kanban_set N "Sprint"
```
Это **единственный** момент, когда задача попадает под автопилот. Эквивалент — перетащить карточку
в колонку `Sprint` на доске. Оркестратор увидит по факту (Status=Sprint). Выведи, что добавлено, и предложи `/orchestrate`.

> Можно класть **любую** задачу: сырую фичу (оркестратор → analysis-lead декомпозирует),
> готовую story или баг (→ dev-lead в разработку). Роутинг по полю `Type` — на стороне оркестратора.

## remove `#N …`

```bash
for N in <номера>; do sprint_remove "$N"; done  # = kanban_set N "Backlog" — назад в интейк
```
Работает только для ещё не начатых задач (в колонке `Sprint`). Задачу, уже ушедшую в пайплайн
(`Analysis`…`Deploy`), так «выдёргивать» не стоит — доведи до конца или закрой issue вручную.

## list

```bash
kb_dump | jq -r 'group_by(.status)[] | "\(.[0].status // "—"): \(length)"'
```
Покажи распределение по колонкам: сколько ждёт в `Sprint`, сколько in-flight по стадиям,
сколько в `Backlog` (вне работы) и `Done`.

---

## Пример потока

```bash
/feature Bulk Export данных     # создать issue → падает в Backlog (интейк)
/sprint add #101 #102 #103      # взять в работу → колонка Sprint   ← твой gate
/orchestrate                    # автопилот ведёт #101 #102 #103 (и то, что уже in-flight) до Done
/sprint                         # посмотреть доску спринта: что в работе, что осталось
```
