---
description: "Спринты: планирование и утверждение задач для оркестратора. /sprint | /sprint add #N | /sprint new | /sprint activate | /sprint close"
argument-hint: "<пусто=доска спринта | new <name> | activate <name> | add #N… | remove #N… | list | close>"
---

# SPRINT — управление спринтами: $ARGUMENTS

Спринт — утверждённый человеком список задач, по которому работает `/orchestrate`.
Оркестратор берёт **только** задачи с `Sprint = orchestrator.current_sprint` и **никогда** не
трогает бэклог (issue без спринта). Задачу можно положить в спринт **любым способом** — эта
команда или перетаскивание на доске (в view, сгруппированном по полю `Sprint`); оркестратор
смотрит только на факт — значение поля.

Поле `Sprint` — single-select (см. `kanban-board-sync.md`). Пишет его **человек**; оркестратор
только читает. Хелперы: `current_sprint`, `sprint_query`, `kb_sprint`. Преамбула — `source .claude/board.env`.

---

## Разбор `$ARGUMENTS`

| Ввод | Действие |
|---|---|
| *(пусто)* | Доска текущего спринта (Шаг «Доска») |
| `list` | Все спринты (опции поля Sprint) + сколько задач и сколько Done в каждом |
| `new <name>` | Создать спринт — дописать опцию в поле Sprint |
| `activate <name>` | Сделать текущим — записать `orchestrator.current_sprint` в профиль |
| `add #N [#M …]` | **Утвердить** issue в текущий спринт (`Sprint=current`) |
| `add <name> #N …` | Утвердить в конкретный спринт |
| `remove #N [#M …]` | Вернуть issue в бэклог (очистить `Sprint`) |
| `close` | Закрыть текущий спринт: carry-over недоделанного + сводка |

---

## Доска спринта (пусто)

```bash
source .claude/board.env 2>/dev/null || { echo "Нет board.env — /init"; exit 1; }
CUR="$(current_sprint)"; [ -z "$CUR" ] && echo "Текущий спринт не выбран — /sprint activate <name>"
kb_dump | jq -r --arg s "$CUR" '[.[]|select((.sprint//"")==$s)]
  | "Спринт: '"$CUR"' — \(length) задач"' 
sprint_query "$CUR" | sort   # number  status  title
```
Выведи по колонкам (Ready for Dev / In Development / Code Review / Testing / Ready to Deploy /
Done), прогресс `Done/всего`, и что осталось. Дальше подскажи: `/orchestrate` — гнать спринт.

## list

```bash
kb_fields | jq -r '.fields[]|select(.name=="Sprint")|.options[].name'   # все спринты
kb_dump | jq -r 'group_by(.sprint)[] | "\(.[0].sprint // "(бэклог)"): \(length) задач, Done \([.[]|select(.status=="Done")]|length)"'
```

## new `<name>`

Добавляет опцию в single-select `Sprint`. Мутация `updateProjectV2Field` **заменяет весь набор
опций** — существующие пришли **с их `id`** (иначе GitHub осиротит поле у всех items), новая —
**без id**. (Тот же приём, что для Status в `/setup-board §1.5`.)

```bash
SF=$(kb_fields | jq -r '.fields[]|select(.name=="Sprint")|.id')
# 1) текущие опции с id:
gh api graphql -f query='{ node(id:"'"$PROJECT_ID"'"){ ... on ProjectV2 {
  field(name:"Sprint"){ ... on ProjectV2SingleSelectField { options{ id name } } } } } }' \
  --jq '.data.node.field.options[] | "\(.id)\t\(.name)"'
# 2) пошли полный набор: {id:"…",name:"…"} для каждой существующей + {name:"<new>"} без id.
#    (сформируй singleSelectOptions по образцу setup-board §1.5)
```
Проще и без риска — добавить опцию в UI: Project → Settings → Sprint → + Add option.

## activate `<name>`

Проверь, что такой спринт существует (опция поля). Затем запиши в профиль
`.claude/project-profile.md` строку `orchestrator.current_sprint`:

```yaml
  current_sprint: "<name>"
```
Подтверди: «Текущий спринт: <name>. Оркестратор теперь работает только по нему.»

## add `#N …` (утвердить — gate одобрения)

```bash
CUR="$(current_sprint)"   # либо явный <name> из аргумента
for N in <номера>; do kb_sprint "$N" "$CUR"; done
```
Это **единственный** момент, когда задача попадает под автопилот. Эквивалент — перетащить её в
спринт на доске. Оркестратор увидит по факту (поле `Sprint`). Выведи, что добавлено, и предложи `/orchestrate`.

## remove `#N …`

```bash
for N in <номера>; do kb_sprint "$N" ""; done   # очистка Sprint → назад в бэклог
```

## close

```bash
CUR="$(current_sprint)"
kb_dump | jq -r --arg s "$CUR" '[.[]|select((.sprint//"")==$s)]
  | { done:([.[]|select(.status=="Done")]|length), left:[.[]|select(.status!="Done")|.number] }'
```
Недоделанное (Status ≠ Done) переноси по `orchestrator.sprint_carryover` из профиля:
- `next` (дефолт) — `kb_sprint <N> "<следующий спринт>"` (создай /activate его при необходимости);
- `backlog` — `kb_sprint <N> ""` (в интейк).

Сводка:
```
SPRINT CLOSED — <CUR>
  Done:     {k} задач
  Carried:  {m} задач → {next|бэклог}
  Next:     /sprint activate <next>  →  /orchestrate
```

---

## Пример потока

```bash
/sprint new "Sprint 2"          # создать
/sprint activate "Sprint 2"     # сделать текущим
/analyze #40                    # (в бэклоге, вручную) разбить фичу на stories
/sprint add #101 #102 #103      # утвердить готовые stories в спринт  ← gate
/orchestrate                    # автопилот гонит ТОЛЬКО #101 #102 #103 до Done
/sprint close                   # недоделанное → Sprint 3
```
