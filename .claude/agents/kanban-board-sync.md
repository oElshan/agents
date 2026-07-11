# Board State Protocol — SINGLE SOURCE OF TRUTH

> **Архитектурное решение:** единственный источник правды о ВСЁМ состоянии задачи —
> **поля GitHub Project board** проекта. Стадия, тип, приоритет, размер, компонент,
> статусы review/qa/deploy — всё это **поля доски**, не лейблы. Лейблы как механизм
> синхронизации **УПРАЗДНЕНЫ полностью**.
>
> Раньше состояние дублировалось в лейблах (issue + метка + доска), агент вручную держал
> их согласованность → хронический рассинхрон. Плюс review-state лейблы (`security:*`,
> `qa:*`, `deployed:*`) накапливались и не сбрасывались. Теперь агент пишет **только поля
> доски**, ключ — board item node-id. Доска физически не может разойтись сама с собой.

## ЖЕЛЕЗНОЕ ПРАВИЛО

**Любое состояние меняем ТОЛЬКО через хелперы (`kb_set` / `kanban_set`). Никаких
`gh issue edit --add-label …` для состояния — state-лейблов больше не существует.**

`kanban_set` сам приводит `open/closed` в соответствие со Status (Done → close, иначе → reopen).
Отдельный `gh issue close/reopen` для смены стадии не нужен и запрещён.

## Идентичность доски — `.claude/board.env`

Константы доски **не хардкодятся в агентах**. Их пишет `/init` (или `/setup-board`) в
`.claude/board.env`, все хелперы начинаются с его загрузки:

```bash
# .claude/board.env — генерируется /init, коммитится в репо (секретов нет)
OWNER="<github-org-or-user>"
REPO="<repo-name>"
PROJECT_NUMBER=<N>
PROJECT_ID="<PVT_...>"        # node-id доски: gh project view N --owner OWNER --format json --jq .id
```

```bash
# Обязательная преамбула каждого агента, работающего с доской:
source .claude/board.env 2>/dev/null || { echo "❌ Нет .claude/board.env — запусти /init (или /setup-board)"; exit 1; }
```

ID полей и опций **не хардкодятся** — резолвятся по имени из `gh project field-list`
(кэш на время сессии). Это убирает дрейф ID при пересоздании/переименовании опций.

## Поля доски

| Поле | Тип | Значения | Пишет (single-writer) |
|------|-----|----------|----------------------|
| **Status** | single-select | Backlog, Analysis, Ready for Dev, In Development, Code Review, Testing, Ready to Deploy, Deploy, Done | Team Lead (`kanban_set`) |
| **Type** | single-select | feature, epic, story, bug, tech-debt, hotfix, spike | analyst |
| **Priority** | single-select | critical, high, medium, low | analyst |
| **Size** | single-select | xs, s, m, l, xl | analyst |
| **Component** | text (CSV) | backend,frontend,ai,infra,docs,qa | analyst |
| **Security** | single-select | pending, passed, failed | security-reviewer |
| **JavaReview** | single-select | pending, passed, warning, failed | java-reviewer |
| **FrontendReview** | single-select | pending, passed, warning, failed | frontend-reviewer |
| **QA** | single-select | pending, in-progress, passed, failed | qa-lead |
| **Deploy** | single-select | none, staging, production | devops |
| **Coverage** | number | % покрытия из QA | qa-lead |
| **Parked** | single-select | no, deps, human, oscillation, budget | оркестратор (`/orchestrate`) |
| **Sprint** | single-select | (пусто)=бэклог, `Sprint 1`, `Sprint 2`, … | **человек** (`/sprint` или перетаскивание на доске) |

> Поля создаются один раз через `/setup-board`. `Component` — TEXT (CSV), т.к. ProjectV2
> не имеет multi-select, а компонент бывает многозначным.
>
> `JavaReview` / `FrontendReview` выставляются только когда в delta есть соответственно
> backend/frontend файлы; иначе остаются `pending`, а dev-lead фиксирует «N/A» в Gate Report.

### Status = активный агент (agent-per-status)

Каждый **Status** соответствует агенту, который владеет задачей на этой стадии — доска
показывает, кто именно сейчас работает. Некоторые статусы держат группу агентов (работают
параллельно). Полная карта и гейты — в `AGENTS_FRAMEWORK.md` → «Kanban Flow».

| Status | Активный агент(ы) | Тип |
|--------|-------------------|-----|
| Backlog | — (заявка) | ожидание |
| Analysis | analyst + architect | активный [2] |
| Ready for Dev | — (dev-lead берёт) | ожидание |
| In Development | developer | активный |
| **Code Review** | security-reviewer + java-reviewer + frontend-reviewer (по delta) | активный [2..3] |
| Testing | test-case-writer | активный |
| Ready to Deploy | — (ручной APPROVE для prod) | ожидание |
| **Deploy** | devops | активный |
| Done | — | терминал |

## Канонические хелперы (копипастить в любой агент)

```bash
source .claude/board.env 2>/dev/null || { echo "❌ Нет .claude/board.env — запусти /init"; exit 1; }

# --- кэш описания полей (1 вызов на сессию; KB_REFRESH=1 для принудительного обновления) ---
kb_fields(){ local c="${TMPDIR:-/tmp}/kb_fields_${PROJECT_NUMBER}.json"
  if [ ! -s "$c" ] || [ -n "${KB_REFRESH:-}" ]; then
    gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --limit 50 --format json >"$c" 2>/dev/null
  fi; cat "$c"; }

# --- issue number → board item id (моно-репо: номер уникален). Создаёт item, если его нет ---
kb_item(){ local N="$1" item cid
  item=$(gh api graphql -f query="{ repository(owner:\"$OWNER\",name:\"$REPO\"){ issue(number:$N){ projectItems(first:10){ nodes{ id project{ id } } } } } }" \
    --jq ".data.repository.issue.projectItems.nodes[] | select(.project.id==\"$PROJECT_ID\") | .id")
  if [ -z "$item" ]; then
    cid=$(gh api graphql -f query="{ repository(owner:\"$OWNER\",name:\"$REPO\"){ issue(number:$N){ id } } }" --jq '.data.repository.issue.id')
    item=$(gh api graphql -f query="mutation{ addProjectV2ItemById(input:{ projectId:\"$PROJECT_ID\" contentId:\"$cid\" }){ item{ id } } }" --jq '.data.addProjectV2ItemById.item.id')
  fi; echo "$item"; }

# --- SET single-select поля: kb_set N Field Option ---
kb_set(){ local N="$1" FIELD="$2" OPT="$3" f fid oid item
  f="$(kb_fields)"
  fid=$(printf '%s' "$f" | jq -r --arg n "$FIELD" '.fields[]|select(.name==$n)|.id')
  oid=$(printf '%s' "$f" | jq -r --arg n "$FIELD" --arg o "$OPT" '.fields[]|select(.name==$n)|.options[]?|select(.name==$o)|.id')
  [ -z "$fid" ] && { echo "kb_set: нет поля '$FIELD'" >&2; return 1; }
  [ -z "$oid" ] && { echo "kb_set: нет опции '$OPT' в поле '$FIELD'" >&2; return 1; }
  item="$(kb_item "$N")" || return 1
  gh api graphql -f query="mutation{ updateProjectV2ItemFieldValue(input:{ projectId:\"$PROJECT_ID\" itemId:\"$item\" fieldId:\"$fid\" value:{ singleSelectOptionId:\"$oid\" } }){ projectV2Item{ id } } }" >/dev/null || return 1
  echo "#$N $FIELD=$OPT"; }

# --- SET text поля (Component): kb_text N Component "backend,infra" ---
kb_text(){ local N="$1" FIELD="$2" VAL="$3" fid item
  fid=$(kb_fields | jq -r --arg n "$FIELD" '.fields[]|select(.name==$n)|.id')
  [ -z "$fid" ] && { echo "kb_text: нет поля '$FIELD'" >&2; return 1; }
  item="$(kb_item "$N")" || return 1
  gh api graphql -f query="mutation{ updateProjectV2ItemFieldValue(input:{ projectId:\"$PROJECT_ID\" itemId:\"$item\" fieldId:\"$fid\" value:{ text:\"$VAL\" } }){ projectV2Item{ id } } }" >/dev/null
  echo "#$N $FIELD=$VAL"; }

# --- SET number поля (Coverage): kb_num N Coverage 96 ---
kb_num(){ local N="$1" FIELD="$2" VAL="$3" fid item
  fid=$(kb_fields | jq -r --arg n "$FIELD" '.fields[]|select(.name==$n)|.id')
  item="$(kb_item "$N")" || return 1
  gh api graphql -f query="mutation{ updateProjectV2ItemFieldValue(input:{ projectId:\"$PROJECT_ID\" itemId:\"$item\" fieldId:\"$fid\" value:{ number:$VAL } }){ projectV2Item{ id } } }" >/dev/null
  echo "#$N $FIELD=$VAL"; }

# --- GET значение любого поля для issue N: kb_get N Field ---
kb_get(){ gh api graphql -f query="{ repository(owner:\"$OWNER\",name:\"$REPO\"){ issue(number:$1){ projectItems(first:10){ nodes{ project{id} fieldValueByName(name:\"$2\"){ ... on ProjectV2ItemFieldSingleSelectValue{name} ... on ProjectV2ItemFieldTextValue{text} ... on ProjectV2ItemFieldNumberValue{number} } } } } } }" \
    --jq ".data.repository.issue.projectItems.nodes[]|select(.project.id==\"$PROJECT_ID\")|.fieldValueByName|(.name // .text // (.number|tostring) // \"\")" 2>/dev/null; }

# --- ЕДИНСТВЕННАЯ операция смены стадии. Двигает Status + приводит open/closed к нему ---
kanban_set(){ local N="$1" STATUS="$2"
  kb_set "$N" "Status" "$STATUS" >/dev/null || return 1
  if [ "$STATUS" = "Done" ]; then gh issue close "$N" --reason completed 2>/dev/null
  else gh issue reopen "$N" 2>/dev/null; fi
  echo "#$N → $STATUS"; }

# --- Список issue где поле=значение (доска — источник правды). Печатает number<TAB>title ---
kanban_query(){ local FIELD="$1" VAL="$2"
  gh api graphql --paginate -f query='query($endCursor:String){ node(id:"'"$PROJECT_ID"'"){ ... on ProjectV2 { items(first:100,after:$endCursor){ pageInfo{hasNextPage endCursor} nodes{ content{ ... on Issue { number title repository{nameWithOwner} } } fieldValueByName(name:"'"$FIELD"'"){ ... on ProjectV2ItemFieldSingleSelectValue{name} } } } } } }' 2>/dev/null \
   | jq -rs --arg repo "$OWNER/$REPO" --arg v "$VAL" '[.[].data.node.items.nodes[]] | .[] | select(.content.repository.nameWithOwner==$repo and (.fieldValueByName.name//"")==$v) | "\(.content.number)\t\(.content.title)"'; }

# --- Дамп всей доски со ВСЕМИ полями одним запросом (для /board, /pick). JSON-массив ---
kb_dump(){ gh api graphql --paginate -f query='query($endCursor:String){ node(id:"'"$PROJECT_ID"'"){ ... on ProjectV2 { items(first:100,after:$endCursor){ pageInfo{hasNextPage endCursor} nodes{
      content{ ... on Issue { number title state repository{nameWithOwner} } }
      st:fieldValueByName(name:"Status"){ ... on ProjectV2ItemFieldSingleSelectValue{name} }
      tp:fieldValueByName(name:"Type"){ ... on ProjectV2ItemFieldSingleSelectValue{name} }
      pr:fieldValueByName(name:"Priority"){ ... on ProjectV2ItemFieldSingleSelectValue{name} }
      sz:fieldValueByName(name:"Size"){ ... on ProjectV2ItemFieldSingleSelectValue{name} }
      cm:fieldValueByName(name:"Component"){ ... on ProjectV2ItemFieldTextValue{text} }
      se:fieldValueByName(name:"Security"){ ... on ProjectV2ItemFieldSingleSelectValue{name} }
      jr:fieldValueByName(name:"JavaReview"){ ... on ProjectV2ItemFieldSingleSelectValue{name} }
      fr:fieldValueByName(name:"FrontendReview"){ ... on ProjectV2ItemFieldSingleSelectValue{name} }
      qa:fieldValueByName(name:"QA"){ ... on ProjectV2ItemFieldSingleSelectValue{name} }
      dp:fieldValueByName(name:"Deploy"){ ... on ProjectV2ItemFieldSingleSelectValue{name} }
      cv:fieldValueByName(name:"Coverage"){ ... on ProjectV2ItemFieldNumberValue{number} }
      pk:fieldValueByName(name:"Parked"){ ... on ProjectV2ItemFieldSingleSelectValue{name} }
      sp:fieldValueByName(name:"Sprint"){ ... on ProjectV2ItemFieldSingleSelectValue{name} } } } } } }' 2>/dev/null \
   | jq -s --arg repo "$OWNER/$REPO" '[.[].data.node.items.nodes[] | select(.content.repository.nameWithOwner==$repo and .content.number!=null) | {number:.content.number, title:.content.title, state:.content.state, status:.st.name, type:.tp.name, priority:.pr.name, size:.sz.name, component:.cm.text, security:.se.name, javareview:.jr.name, frontendreview:.fr.name, qa:.qa.name, deploy:.dp.name, coverage:.cv.number, parked:.pk.name, sprint:.sp.name}]'; }

# --- Удобный сеттер метаданных: kb_meta N type=story priority=high size=m component=backend,infra ---
kb_meta(){ local N="$1"; shift
  for kv in "$@"; do case "$kv" in
    type=*)      kb_set  "$N" Type      "${kv#type=}";;
    priority=*)  kb_set  "$N" Priority  "${kv#priority=}";;
    size=*)      kb_set  "$N" Size      "${kv#size=}";;
    component=*) kb_text "$N" Component "${kv#component=}";;
  esac; done; }

# --- текущий спринт из профиля (orchestrator.current_sprint). Пусто → спринт не задан ---
current_sprint(){ grep -E '^[[:space:]]*current_sprint:' .claude/project-profile.md 2>/dev/null \
  | head -1 | sed -E 's/.*current_sprint:[[:space:]]*"?([^"#]*)"?.*/\1/; s/[[:space:]]+$//'; }

# --- issue спринта (по умолчанию — текущего): sprint_query [<name>] → number<TAB>status<TAB>title ---
sprint_query(){ local S="${1:-$(current_sprint)}"
  kb_dump | jq -r --arg s "$S" '.[] | select((.sprint//"")==$s) | "\(.number)\t\(.status // "—")\t\(.title)"'; }

# --- назначить issue в спринт / вернуть в бэклог: kb_sprint N "Sprint 2"  |  kb_sprint N ""  (пустой → бэклог) ---
kb_sprint(){ local N="$1" S="$2" fid item
  if [ -n "$S" ]; then kb_set "$N" Sprint "$S"; return; fi
  fid=$(kb_fields | jq -r '.fields[]|select(.name=="Sprint")|.id'); item="$(kb_item "$N")" || return 1
  gh api graphql -f query="mutation{ clearProjectV2ItemFieldValue(input:{ projectId:\"$PROJECT_ID\" itemId:\"$item\" fieldId:\"$fid\" }){ projectV2Item{ id } } }" >/dev/null && echo "#$N Sprint=(бэклог)"; }
```

### Примеры

```bash
kanban_set 97 "In Development"          # dev-lead: developer стартует (issue reopen если был закрыт)
kanban_set 97 "Code Review"             # dev-lead: G4 пройден → запуск reviewers по delta
kanban_set 97 "Testing"                 # dev-lead: G5 пройден (все применимые ревью)
kanban_set 97 "Deploy"                  # ops-lead: G7 пройден → devops деплоит
kanban_set 97 "Done"                    # ops-lead: G8 пройден + auto-close issue
kb_set     97 Security passed           # security-reviewer: проставить гейт (в статусе Code Review)
kb_set     97 JavaReview warning        # java-reviewer (в статусе Code Review)
kb_set     97 FrontendReview passed     # frontend-reviewer (в статусе Code Review, если frontend-delta)
kb_set     97 QA passed; kb_num 97 Coverage 96   # qa-lead
kb_set     97 Deploy staging            # devops
kb_meta    97 type=story priority=high size=m component=backend,infra  # analyst при создании
kb_get     97 Security                  # → passed
kanban_query "Status" "Ready for Dev"   # что готово к разработке
kanban_query "QA" "passed"             # что прошло QA
kb_dump | jq -r '.[]|select(.status=="In Development")|.number'        # WIP
```

## Создание нового issue

```bash
N=$(gh issue create --title "..." --body "..." --json number --jq .number)
kanban_set "$N" "Backlog"                          # положить на доску
kb_meta "$N" type=story priority=high size=m component=backend   # метаданные = поля
```
Без `kanban_set` issue не попадёт на доску — у него не будет Status. Лейблы при создании
issue **не ставятся** — всё в поля.

### Роутинг по спринту при создании (авто-задачи)

Новая issue должна попасть в правильный спринт, иначе оркестратор её не увидит (или увидит не там):

- **Баг/регресс на задаче текущего спринта** (создаёт security-reviewer / java-reviewer /
  frontend-reviewer / qa-lead при FAIL) → **наследует спринт родителя**: `kb_sprint "$N" "$(current_sprint)"`.
  Баг блокирует цель спринта — чинить в этом же спринте.
- **Проактивный tech-debt** (postdeploy.sh / G9, ручные идеи) → **в бэклог**: `Sprint` не ставим
  (`kb_sprint "$N" ""` или просто не трогаем поле). Триаж — на планировании.
- Поле `Sprint` — единственный «писатель»-человек; это исключение (детерминированное наследование
  родителя авто-багом), а не «домысел» оркестратора о содержимом спринта.

## ЗАПРЕЩЕНО

- ❌ Ставить/читать любые state-лейблы (`security:*`, `java-review:*`, `qa:*`, `deployed:*`,
  `type:*`, `priority:*`, `size:*`, `component:*`) — их роль перенесена в поля доски.
- ❌ Менять состояние «вручную» через сырой `updateProjectV2ItemFieldValue` мимо хелперов.
- ❌ `gh issue close/reopen` как способ сменить стадию — используй `kanban_set`.
- ❌ Фильтровать задачи через `gh issue list --label …` — используй `kanban_query` / `kb_dump`.
- ❌ Добавлять на доску issue из других репозиториев — у каждого репо свой Project.

## Идентичность доски (моно-репо)

Доска содержит **только** issue из `$OWNER/$REPO`. Issue других репозиториев на неё не
добавляются — у них свои Projects. Поэтому номер issue уникален в пределах доски, и все
хелперы безопасно работают по номеру. Хелперы дополнительно фильтруют
`repository.nameWithOwner == "$OWNER/$REPO"` — защита от случайного попадания чужих items.

## Backstop

Детерминированный страховочный workflow `.github/workflows/kanban-reconcile.yml` на каждое
`issues:[closed,reopened,opened]` (и по `workflow_dispatch`) приводит Status↔open/closed в
порядок и доносит на доску issue без item. Это backstop на случай падения агента посреди
операции — не замена хелперам. Workflow фильтрует по репозиторию. Шаблон генерирует `/init`
(значения OWNER/REPO/PROJECT_ID берёт из `board.env`; нужен repo-secret `KANBAN_PROJECT_TOKEN`).

## ⚠️ СКРЫТЫЙ ТРЕТИЙ АКТОР: встроенные workflow GitHub Project

У GitHub Project есть **встроенные** автоматизации (Project Settings → Workflows):
`Item added to project`, `Auto-close issue`, `Auto-add to project` и др. Они АВТОНОМНО
меняют Status/open/closed мимо хелперов и их НЕЛЬЗЯ переключить через API (только UI).

**Требуемая настройка проекта (делается в UI, разово, проверяется на /init):**

| Встроенный workflow | Целевое состояние |
|---------------------|-------------------|
| `Auto-close issue` | ❌ ВЫКЛ — `kanban_set N "Done"` закрывает сам; авто-закрытие = гонка |
| `Auto-add sub-issues to project` | ✅ ВКЛ — stories автоматически попадают на доску |
| `Auto-add to project` | ✅ ВКЛ, но фильтр строго `repo:<REPO>` + `is:issue` (PR на доску не добавлять) |
| `Item added to project` | ✅ ВКЛ, target Status = **Backlog** (НЕ Done и не другой) |
| `Item closed` | ✅ ВКЛ, target Status = **Done** — ⚠️ ОБЯЗАТЕЛЬНО перепроверить target: неверный target (например «Ready for Dev») молча увозит закрытые issue не туда, reconcile исправляет вдогонку |
| `Pull request linked to issue` | ❌ ВЫКЛ — двигает Status мимо `kanban_set` |
| `Pull request merged` | ❌ ВЫКЛ — переводил бы в Done при merge, а Done ставит ops-lead после деплоя (G8) |

API (GraphQL `workflows`) показывает только name/enabled — target-статусы видны и меняются ТОЛЬКО в UI.

## Проверка инварианта (после серии переходов)

```bash
# Должно вернуть 0 / 0 / 0
gh api graphql --paginate -f query='query($endCursor:String){ node(id:"'"$PROJECT_ID"'"){ ... on ProjectV2 { items(first:100,after:$endCursor){ pageInfo{hasNextPage endCursor} nodes{ content{ ... on Issue { number state repository{nameWithOwner} } } fieldValueByName(name:"Status"){ ... on ProjectV2ItemFieldSingleSelectValue { name } } } } } } }' 2>/dev/null \
 | jq -s --arg repo "$OWNER/$REPO" '[.[].data.node.items.nodes[] | select(.content.repository.nameWithOwner==$repo)] | {closed_not_done:([.[]|select(.content.state=="CLOSED" and (.fieldValueByName.name//"")!="Done")]|length), open_done:([.[]|select(.content.state=="OPEN" and (.fieldValueByName.name//"")=="Done")]|length), no_status:([.[]|select(.content.number!=null and .fieldValueByName.name==null)]|length)}'
```
