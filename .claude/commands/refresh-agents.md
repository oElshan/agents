---
description: "Kanban: Refresh Agents. Синхронизирует агентов и команды из источника (другой проект). Примеры: /refresh-agents | /refresh-agents --source ~/other-project | /refresh-agents --dry-run"
argument-hint: "[--source <path>] [--dry-run] [--agents-only] [--commands-only]"
---

# REFRESH AGENTS — $ARGUMENTS

Обновляет агентскую систему (`.claude/agents/` и `.claude/commands/`) из источника.
Применяет изменения, которые ты внёс в агентов, не перезаписывая файлы проекта вручную.

---

## Алгоритм (АВТОНОМНО)

### ШАГ 1 — Разбор аргументов

Определи из `$ARGUMENTS`:
- `--source <path>` — путь к проекту-источнику
- `--dry-run` — только показать diff, ничего не изменять
- `--agents-only` — обновить только `.claude/agents/`
- `--commands-only` — обновить только `.claude/commands/`

Если `--source` не указан:
```bash
# Поищи другие проекты с агентской системой
PROJECTS_DIR=$(dirname $(pwd))
find "$PROJECTS_DIR" -maxdepth 2 -name "developer.md" -path "*/.claude/agents/*" 2>/dev/null | grep -v "$(pwd)"
```

Если найден ровно один другой проект — использовать его как источник (спроси пользователя подтверждение).
Если найдено несколько — покажи список и попроси указать `--source`.
Если не найдено — сообщи об ошибке и попроси `--source`.

---

### ШАГ 2 — Чтение источника

```bash
SOURCE_AGENTS="<source>/.claude/agents"
SOURCE_COMMANDS="<source>/.claude/commands"

# Список файлов в источнике
ls "$SOURCE_AGENTS"/*.md 2>/dev/null
ls "$SOURCE_COMMANDS"/*.md 2>/dev/null
```

Прочитай КАЖДЫЙ файл из источника (agents + commands). `.claude/board.env` и
`.claude/project-profile.md` источника ИГНОРИРУЙ — они проект-специфичны
(идентичность доски и профиль стека) и НИКОГДА не синхронизируются между проектами.

---

### ШАГ 3 — Сравнение с текущим проектом

Для каждого файла из источника:

```
CURRENT: .claude/agents/{file}.md
SOURCE:  <source>/.claude/agents/{file}.md

Статусы:
  NEW      — файл есть в источнике, нет в текущем проекте
  CHANGED  — файл отличается (сравни содержимое построчно)
  SAME     — файлы идентичны
  LOCAL    — файл есть только в текущем проекте (источник не имеет)
```

Построй таблицу diff:

```
DIFF REPORT
Source: <source_path>

AGENTS (.claude/agents/):
  ✓ SAME     analyst.md
  ↑ CHANGED  developer.md        (+15 lines, description updated)
  ✓ SAME     architect.md
  + NEW      performance-agent.md
  ~ LOCAL    doc-sync.md         (only in current project, keep)
  ~ LOCAL    integration-tester.md (only in current project, keep)
  ~ LOCAL    frontend-reviewer.md (only in current project, keep)

COMMANDS (.claude/commands/):
  ✓ SAME     develop.md
  ↑ CHANGED  test.md             (+8 lines)
  ✓ SAME     board.md
  + NEW      refresh-agents.md   (this file)

Summary: 2 changed, 1 new, 0 deleted, 3 local-only
```

---

### ШАГ 4 — Применение (если не --dry-run)

Для каждого файла со статусом `CHANGED` или `NEW`:
1. Прочитай файл из источника
2. Запиши в `.claude/agents/` или `.claude/commands/`
3. Логируй: `Updated: .claude/agents/developer.md`

**ВАЖНО:**
- Файлы со статусом `LOCAL` (есть только в текущем проекте) — НЕ удалять
- Файлы `SAME` — пропустить
- Никогда не удалять файлы из текущего проекта
- `.claude/board.env` и `.claude/project-profile.md` — НИКОГДА не синхронизируются между
  проектами (они проект-специфичны: идентичность доски и профиль стека). Исключи их из
  копирования, даже если они есть в источнике; локальные версии не перезаписывать

---

### ШАГ 5 — Финальный отчёт

```
REFRESH AGENTS COMPLETE
{date}

Source: <source_path>

Applied:
  ↑ .claude/agents/developer.md   — updated (был: v1.2, стал: v1.3)
  + .claude/agents/new-agent.md   — added
  ↑ .claude/commands/test.md      — updated

Skipped (identical):
  ✓ analyst.md, architect.md, devops.md, ... (N files)

Preserved (local-only):
  ~ doc-sync.md, integration-tester.md, frontend-reviewer.md

Excluded (project-specific, never synced):
  ⊘ .claude/board.env, .claude/project-profile.md

{if dry-run}
DRY RUN — изменения не применены. Запусти без --dry-run чтобы применить.
{endif}

NEXT STEPS:
  • Изменения активны с текущей сессии (агенты читаются из файлов)
  • Закоммить обновления: git add .claude/ && git commit -m "chore: refresh agent system"
  • Запусти /board чтобы проверить что всё работает
```
