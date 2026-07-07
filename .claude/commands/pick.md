---
description: "Kanban: Pick. Взять следующую задачу по приоритету. Примеры: /pick ready-for-dev | /pick testing | /pick backlog | /pick ready-to-deploy"
argument-hint: "<backlog | ready-for-dev | testing | ready-to-deploy>"
---

# KANBAN — Pick Next Task: $ARGUMENTS

Автоматически выбери и начни работу над следующей задачей из указанной колонки через **Team Lead**.

## Алгоритм (АВТОНОМНО)

### 1. Получи задачи из колонки

Маппинг аргумента → имя колонки Status: backlog→"Backlog", ready-for-dev→"Ready for Dev", testing→"Testing", ready-to-deploy→"Ready to Deploy".

Один дамп доски + фильтр по полю Status — отсюда же берётся и поле Priority для сортировки
(хелпер `kb_dump` из `.claude/agents/kanban-board-sync.md`):

```bash
kb_dump > "${TMPDIR:-/tmp}/pick.json"
jq -r --arg s "<Status>" '.[] | select(.status==$s) | {number,title,priority}' "${TMPDIR:-/tmp}/pick.json"
```

### 2. Выбери по приоритету (поле Priority)

Сортируй по полю **Priority** из дампа, порядок critical > high > medium > low:

```bash
jq -r --arg s "<Status>" '
  def rank: {"critical":0,"high":1,"medium":2,"low":3}[.] // 9;
  [.[] | select(.status==$s)]
  | sort_by(.priority|rank, .number)
  | .[] | "#\(.number)\t\(.priority // "—")\t\(.title)"' "${TMPDIR:-/tmp}/pick.json"
```

1. Priority=critical — первым
2. Priority=high — после critical
3. Priority=medium — после high
4. Priority=low — последним

При одинаковом приоритете — самый старый (меньший номер).

### 3. Проверь WIP лимиты

Порог — `quality.wip_limit` из `.claude/project-profile.md` (default 5):

- Status="In Development" → max quality.wip_limit
- Status="Code Review" → max quality.wip_limit
- Status="Testing" → max quality.wip_limit

Если WIP превышен — сообщи и предложи завершить текущие.

> Статусы `Code Review` и `Deploy` — **транзитные, ими владеют агенты**: dev-lead
> автоматически ведёт задачу In Development → Code Review → Testing (в Code Review
> параллельно работают три reviewer'а по delta: security-reviewer — всегда,
> java-reviewer — при backend-delta, frontend-reviewer — при frontend-delta),
> ops-lead — Ready to Deploy → Deploy → Done. Поэтому `/pick` их не таргетит;
> допустимые аргументы — `backlog`, `ready-for-dev`, `testing`, `ready-to-deploy`.

### 4. Запусти через Team Lead

| Колонка | Team Lead | Команда |
|---------|-----------|---------|
| `backlog` | **analysis-lead** → analyst + architect | `/analyze #{N}` |
| `ready-for-dev` | **dev-lead** → developer | `/develop #{N}` |
| `testing` | **qa-lead** → tester | `/test #{N}` |
| `ready-to-deploy` | **ops-lead** → devops | `/deploy #{N}` |

Запусти соответствующий Team Lead:

```
Agent(subagent_type="{lead}", prompt="{action} #{N} '{title}'.
Read .claude/project-profile.md FIRST (commands/thresholds source of truth), then CLAUDE.md and ARCHITECTURE.md (if exists).
Follow full workflow.
Sync Project Board.
Report results.")
```

### 5. Отчёт

```
PICKED: #{N} — {title}
From: {column}
Priority: {priority}
Team Lead: {lead}
Agent: {agent}
Status: {result}
```
