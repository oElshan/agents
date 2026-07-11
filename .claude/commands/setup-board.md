---
description: "Kanban: Setup. Создание полей Project board (Status/Type/Priority/Size/Component/Security/JavaReview/FrontendReview/QA/Deploy/Coverage) + настройка. Запускать ОДИН раз. Пример: /setup-board"
argument-hint: ""
---

# KANBAN — Setup Board

Инициализируй GitHub Project board для Kanban-процесса. **Всё состояние задачи живёт в полях
доски, а не в лейблах.** Эта команда создаёт поля доски (идемпотентно — существующие пропускает).

> **Источник правды — поля GitHub Project board из `.claude/board.env`.** Лейблы как механизм
> синхронизации упразднены и здесь НЕ создаются. Состояние двигают хелперы `kb_set` / `kanban_set`
> из `.claude/agents/kanban-board-sync.md`.
> ```bash
> source .claude/board.env    # OWNER / REPO / PROJECT_NUMBER / PROJECT_ID
> ```
> Согласованность Status ↔ open/closed поддерживает страховочный workflow
> `.github/workflows/kanban-reconcile.yml` — требует secret **`KANBAN_PROJECT_TOKEN`**
> (classic PAT со scope `project`). Без него reconcile-backstop не работает.

## Алгоритм (АВТОНОМНО)

### 0. Загрузи идентичность доски (`.claude/board.env`)

```bash
if [ -f .claude/board.env ]; then
  source .claude/board.env
else
  # board.env ещё нет — создай его по алгоритму из /init (ШАГ 4):
  NWO=$(git remote get-url origin | sed -E 's#^(git@|ssh://git@|https://)([^/:]+)[:/]##; s#\.git$##')
  OWNER=${NWO%%/*} ; REPO=${NWO##*/}
  # существующая доска (номер уточни у человека, если досок несколько) …
  gh project list --owner "$OWNER" --format json --jq '.projects[] | "\(.number)\t\(.title)"'
  # … или новая:
  PROJECT_NUMBER=$(gh project create --owner "$OWNER" --title "$REPO" --format json --jq .number)
  PROJECT_ID=$(gh project view "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq .id)
  printf 'OWNER="%s"\nREPO="%s"\nPROJECT_NUMBER=%s\nPROJECT_ID="%s"\n' \
    "$OWNER" "$REPO" "$PROJECT_NUMBER" "$PROJECT_ID" > .claude/board.env
fi
echo "Доска: $OWNER/$REPO → Project $PROJECT_NUMBER"
```

### 1. Создай поля доски (идемпотентно)

```bash
# OWNER / PROJECT_NUMBER уже загружены из .claude/board.env (шаг 0)

# Имена уже существующих полей — чтобы не создавать повторно
EXISTING=$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --limit 50 --format json | jq -r '.fields[].name')

mkfield(){ # name datatype [options]
  local name="$1" dt="$2" opts="$3"
  if printf '%s\n' "$EXISTING" | grep -qxF "$name"; then echo "= поле '$name' уже есть"; return; fi
  if [ -n "$opts" ]; then
    gh project field-create "$PROJECT_NUMBER" --owner "$OWNER" --name "$name" --data-type SINGLE_SELECT --single-select-options "$opts" >/dev/null && echo "+ создано '$name' ($opts)"
  else
    gh project field-create "$PROJECT_NUMBER" --owner "$OWNER" --name "$name" --data-type "$dt" >/dev/null && echo "+ создано '$name' ($dt)"
  fi
}

# Status обычно уже есть; mkfield пропустит его. Опции на случай чистой доски.
# Порядок опций = поток агентов (agent-per-status): каждый Status — активный агент,
# Code Review = security-reviewer + java-reviewer + frontend-reviewer (по delta), Deploy = devops.
mkfield "Status"     SINGLE_SELECT "Backlog,Analysis,Ready for Dev,In Development,Code Review,Testing,Ready to Deploy,Deploy,Done"
mkfield "Type"       SINGLE_SELECT "feature,epic,story,bug,tech-debt,hotfix,spike"
mkfield "Priority"   SINGLE_SELECT "critical,high,medium,low"
mkfield "Size"       SINGLE_SELECT "xs,s,m,l,xl"
mkfield "Component"  TEXT          ""
mkfield "Security"   SINGLE_SELECT "pending,passed,failed"
mkfield "JavaReview" SINGLE_SELECT "pending,passed,warning,failed"
mkfield "FrontendReview" SINGLE_SELECT "pending,passed,warning,failed"
mkfield "QA"         SINGLE_SELECT "pending,in-progress,passed,failed"
mkfield "Deploy"     SINGLE_SELECT "none,staging,production"
mkfield "Coverage"   NUMBER        ""
mkfield "Parked"     SINGLE_SELECT "no,deps,human,oscillation,budget"
```

> `Parked` пишет ТОЛЬКО оркестратор (`/orchestrate`): помечает заклинившие/ждущие-человека
> issue, чтобы петля не крутила их вхолостую. Остальные агенты его не трогают.

### 1.5. Добавь недостающие Status-опции на СУЩЕСТВУЮЩЕЙ доске

`mkfield` пропускает уже существующее поле `Status` целиком — поэтому на действующей доске
две новые опции (`Code Review`, `Deploy`) НЕ появятся автоматически. Опции обновляются
мутацией `updateProjectV2Field` (поле `singleSelectOptions`) — она **заменяет весь набор
опций**. Мутации «добавить одну опцию» в публичном API нет.

> 🛑 **КРИТИЧНО:** каждую СУЩЕСТВУЮЩУЮ опцию присылай **с её `id`** — иначе GitHub пересоздаст
> её с новым id и **осиротит `Status` у ВСЕХ items** (сотни задач потеряют колонку). Новые
> опции (`Code Review`, `Deploy`) — БЕЗ `id` (создадутся). Сначала считай текущие опции с id,
> потом пошли полный набор. Альтернатива без риска — UI: Project → Settings → Status → + Add option.

```bash
STATUS_FIELD_ID=$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --limit 50 --format json \
  | jq -r '.fields[]|select(.name=="Status")|.id')

# 1) считай текущие опции с id (нужно вставить их id в мутацию ниже):
gh api graphql -f query='{ node(id:"'"$PROJECT_ID"'"){ ... on ProjectV2 {
  field(name:"Status"){ ... on ProjectV2SingleSelectField { options{ id name color } } } } } }' \
  --jq '.data.node.field.options[] | "\(.id)\t\(.name)"'

# 2) пошли полный набор: существующие — С id (сохраняют значения у items),
#    Code Review после In Development, Deploy после Ready to Deploy — БЕЗ id:
gh api graphql -f query='mutation($f:ID!){
  updateProjectV2Field(input:{ fieldId:$f, singleSelectOptions:[
    {id:"<Backlog-id>",        name:"Backlog",         color:GRAY,   description:""},
    {id:"<Analysis-id>",       name:"Analysis",        color:PURPLE, description:"analyst + architect"},
    {id:"<Ready for Dev-id>",  name:"Ready for Dev",   color:BLUE,   description:""},
    {id:"<In Development-id>", name:"In Development",  color:YELLOW, description:"developer"},
    {name:"Code Review",     color:ORANGE, description:"security-reviewer + java-reviewer + frontend-reviewer (по delta)"},
    {id:"<Testing-id>",        name:"Testing",         color:PINK,   description:"test-case-writer"},
    {id:"<Ready to Deploy-id>",name:"Ready to Deploy", color:GREEN,  description:""},
    {name:"Deploy",          color:GREEN,  description:"devops"},
    {id:"<Done-id>",           name:"Done",            color:GREEN,  description:""}
  ]}){ projectV2Field{ ... on ProjectV2SingleSelectField { options{ id name } } } }
}' -f f="$STATUS_FIELD_ID"
```

> На **чистой** доске этот шаг не нужен: `mkfield` из шага 1 уже создаст Status с 9 опциями.

### 2. Проверь поля

```bash
# должны присутствовать все 12 полей системы (плюс встроенные Title/Assignees/…)
gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --limit 50 --format json \
 | jq -r '.fields[] | "\(.name) [\(.type)]\(if .options then "  " + ([.options[].name]|join("|")) else "" end)"'
```

### 3. Встроенные автоматизации Project (UI, разово)

Открой Project (`gh project view "$PROJECT_NUMBER" --owner "$OWNER" --web`) → Settings → Workflows и приведи к виду:
- **`Auto-close issue` — ВЫКЛЮЧИТЬ** (иначе гонка с `kanban_set`).
- `Item added to project`: default Status = `Backlog` (НЕ Done), либо выключить.
- `Item closed` → Done — оставить.
- `Auto-add to project` — выключить или ограничить `repo:$REPO` + `is:issue` (значение REPO — из board.env; чужие issue и PR на доску не попадают).

### 4. Backstop workflow + secret

```bash
echo "Required: repo secret KANBAN_PROJECT_TOKEN
  - classic PAT со scope 'project' (+ 'repo')
  - Settings → Secrets and variables → Actions → New repository secret
  - Без него .github/workflows/kanban-reconcile.yml не работает."
```

### 5. (опц.) Снести старые лейблы

Если на репозитории остались старые state/metadata-лейблы (`type:*`, `priority:*`, `size:*`,
`component:*`, `security:*`, `qa:*`, `deployed:*` и т.п.) — после переноса их значений в поля
доски лейблы можно удалить. На свежем репозитории лейблы вообще не нужны.

## Финальный отчёт
```
KANBAN BOARD INITIALIZED (field-based)

Project {PROJECT_NUMBER} ({OWNER}/{REPO} из .claude/board.env) — единственный источник правды.
Поля (12): Status, Type, Priority, Size, Component, Security, JavaReview, FrontendReview, QA, Deploy, Coverage, Parked
Status (agent-per-status, 9): Backlog → Analysis → Ready for Dev → In Development
  → Code Review → Testing → Ready to Deploy → Deploy → Done
Состояние двигают: kb_set / kanban_set (.claude/agents/kanban-board-sync.md)
Backstop: .github/workflows/kanban-reconcile.yml (secret KANBAN_PROJECT_TOKEN)
Лейблы: НЕ используются для состояния.

Ready: /feature /analyze /develop /test /deploy /kanban /board /orchestrate /stage (/pick /sweep /swarm — алиасы)
```
