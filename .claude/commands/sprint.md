---
description: "Очередь оркестратора (колонка Sprint): положить/убрать задачи и посмотреть. /sprint | /sprint add #N | /sprint remove #N"
argument-hint: "<пусто=очередь+пайплайн | add #N… | remove #N… | list>"
---

# SPRINT — очередь оркестратора (колонка `Status=Sprint`): $ARGUMENTS

Очередь — это колонка **`Sprint`** на доске. `/orchestrate` берёт задачи **только** из активного
пайплайна (`Sprint`…`Deploy`) и **никогда** не трогает `Backlog`. Точка входа — колонка `Sprint`:
что туда положено, то оркестратор и разбирает, гоняя по стадиям до `Done`, и лупит по кругу.

Положить задачу в очередь можно **двумя равнозначными способами**:
- перетащить карточку в колонку **`Sprint`** на доске GitHub (в board-view, сгруппированном по `Status`);
- `/sprint add #N` — то же самое из CLI (`kanban_set N Sprint`).

Оркестратор смотрит только на факт — значение `Status`. Именованные спринты и поле `Sprint`
**упразднены** (одна непрерывная очередь). Хелперы: `sprint_queue`, `kb_queue`, `kanban_set`
(см. `kanban-board-sync.md`). Преамбула — `source .claude/board.env`.

---

## Разбор `$ARGUMENTS`

| Ввод | Действие |
|---|---|
| *(пусто)* | Показать очередь (`Sprint`) + активный пайплайн (Шаг «Очередь») |
| `list` | То же, что пусто (сводка по колонкам) |
| `add #N [#M …]` | **Положить в очередь**: `kanban_set N Sprint` (эквивалент перетаскивания в колонку `Sprint`) |
| `remove #N [#M …]` | Убрать из очереди назад в интейк: `kanban_set N Backlog` |

> `new` / `activate` / `close` (именованные спринты по полю `Sprint`) — **удалены**. Модель —
> единая очередь-колонка `Sprint`; «закрытие спринта» не нужно, задачи сами утекают в `Done`.

---

## Очередь (пусто / `list`)

```bash
source .claude/board.env 2>/dev/null || { echo "Нет board.env — /init"; exit 1; }
kb_dump > "${TMPDIR:-/tmp}/board.json"

echo "=== Очередь (Status=Sprint) ==="
jq -r '.[] | select(.status=="Sprint") | "#\(.number)\t[\(.priority//"—")]\t\(.title)"' "${TMPDIR:-/tmp}/board.json"

echo "=== В работе (in-flight) по колонкам ==="
jq -r '["Analysis","Ready for Dev","In Development","Code Review","Testing","Ready to Deploy","Deploy"] as $order
  | [.[] | select(.status as $s | $order|index($s))]
  | group_by(.status)
  | map("\(.[0].status): \(length)") | .[]' "${TMPDIR:-/tmp}/board.json"

echo "=== Backlog (интейк, оркестратор НЕ трогает) ==="
jq '[.[] | select(.status=="Backlog")] | length' "${TMPDIR:-/tmp}/board.json"
```

Выведи: сколько в очереди, что в работе по стадиям, прогресс. Дальше подскажи: `/orchestrate` —
запустить автопилот по очереди; `/sprint add #N` — добавить задачу; либо перетащить в `Sprint` на доске.

## add `#N …` (положить в очередь)

```bash
for N in <номера>; do kanban_set "$N" "Sprint"; done   # = kb_queue N add
```
Это момент, когда задача попадает под автопилот. Эквивалент — перетащить её в колонку `Sprint`
на доске. Оркестратор увидит по факту (`Status=Sprint`). Выведи, что добавлено, и предложи `/orchestrate`.

## remove `#N …` (убрать из очереди)

```bash
for N in <номера>; do kanban_set "$N" "Backlog"; done  # = kb_queue N remove
```
Возвращает задачу в интейк (`Backlog`). Применимо только к задачам, ещё не ушедшим в работу.

---

## Пример потока

```bash
/analyze #40                    # (в бэклоге, вручную) разбить фичу на stories — они лягут в Backlog
/sprint add #101 #102 #103      # положить готовые stories в очередь (колонка Sprint)  ← или перетащить на доске
/orchestrate                    # автопилот берёт #101 #102 #103 из очереди и гонит до Done, лупит
/sprint                         # посмотреть, что осталось в очереди / в работе
```
