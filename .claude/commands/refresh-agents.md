---
description: "Kanban: Refresh. Синк фреймворка из источника (проект/сабмодуль): agents, commands, system, доки + мёрдж новых ключей профиля. Примеры: /refresh-agents --source .agents-framework | --dry-run"
argument-hint: "[--source <path>] [--dry-run] [--agents-only] [--commands-only]"
---

# REFRESH — синк агентского фреймворка из источника: $ARGUMENTS

Обновляет агентскую систему в `.claude/` из источника (другой проект или git-сабмодуль,
напр. `.agents-framework`). Применяет обновления фреймворка, **не затирая проект-специфичные
данные** и **не теряя заполненное**. Правила распределения — `.claude/DISTRIBUTION.md §2`.

---

## Правило синка (безопасность — соблюдать строго)

| Категория | Файлы | Действие |
|---|---|---|
| **Framework** | `agents/*.md`, `commands/*.md`, `system/sdc.md`, `system/postdeploy.sh`, `AGENTS_FRAMEWORK.md`, `*_DESIGN.md`, `DISTRIBUTION.md`, `board.env.example`, `memory/stories/_template.md` | **overwrite** (берём из источника при CHANGED/NEW) |
| **Accumulator** | `system/budget.md`, `system/ownership-map.md` | **seed-if-absent** (копировать ТОЛЬКО если файла нет; заполненный не трогать) |
| **Project config** | `project-profile.md`*, `board.env`, `settings.json`, `settings.local.json`, `memory/*` (кроме `stories/_template.md`) | **preserve** (не трогать) |

\* `project-profile.md` сам не перезаписывается, но его **ключи мёрджатся** — см. ШАГ 3.5.
LOCAL-файлы (есть только у проекта) не удаляются никогда.

---

## Алгоритм (АВТОНОМНО)

### ШАГ 1 — Аргументы

- `--source <path>` — корень источника (проект или сабмодуль; читаем `<path>/.claude/…`).
- `--dry-run` — только показать план, ничего не менять.
- `--agents-only` / `--commands-only` — сузить синк до соответствующей папки.

Если `--source` не указан — поищи источник (сначала сабмодуль, потом соседние проекты):
```bash
# git-сабмодуль с агентской системой?
git config --file .gitmodules --get-regexp path 2>/dev/null | awk '{print $2}' \
  | while read p; do [ -f "$p/.claude/agents/developer.md" ] && echo "$p"; done
# иначе — соседние проекты:
find "$(dirname "$(pwd)")" -maxdepth 2 -name developer.md -path "*/.claude/agents/*" 2>/dev/null | grep -v "$(pwd)"
```
Ровно один кандидат → используй (подтверди у человека). Несколько → покажи список, попроси `--source`. Ноль → ошибка.

### ШАГ 2 — Чтение источника

Собери файлы источника по категориям (см. правило синка):
```bash
S="<source>/.claude"
ls "$S"/agents/*.md "$S"/commands/*.md "$S"/system/* "$S"/*.md 2>/dev/null
```
Прочитай каждый **Framework**- и **Accumulator**-файл. `project-profile.md`, `board.env`,
`settings*.json`, содержимое `memory/` (кроме `stories/_template.md`) из источника **игнорируй**.

### ШАГ 3 — Diff по категориям

Для каждого файла определи статус: `NEW` / `CHANGED` / `SAME` / `LOCAL`. Для Accumulator-файлов,
которые уже есть локально → `SEED-SKIP` (не трогаем заполненное). Построй отчёт:

```
DIFF REPORT — source: <source>

FRAMEWORK (overwrite):
  ↑ CHANGED  commands/orchestrate.md   (+40 lines)
  + NEW      commands/sprint.md
  + NEW      commands/stage.md
  ↑ CHANGED  agents/kanban-board-sync.md
  + NEW      AGENTS_FRAMEWORK.md / ORCHESTRATOR_DESIGN.md / SPRINT_MODEL_DESIGN.md / DISTRIBUTION.md
  ✓ SAME     agents/analyst.md …
  ~ LOCAL    agents/<кастомный>.md   (только у проекта — сохраняем)

ACCUMULATOR (seed-if-absent):
  + SEED     system/budget.md        (нет локально → засеять)
  ⊘ SEED-SKIP system/ownership-map.md (уже заполнен → не трогаем)

PROFILE KEYS: {N новых ключей к добавлению — см. ШАГ 3.5}
```

### ШАГ 3.5 — Мёрдж ключей профиля (миграция старого проекта)

Сравни `orchestrator:`-блок и спринт-ключи в шаблоне источника (`<source>/.claude/project-profile.md`)
с локальным `project-profile.md`. Найди **отсутствующие локально** ключи и добавь их с дефолтами
из шаблона, **не меняя существующих значений** (стек/команды/пороги — проектные, остаются):

- `orchestrator:` целиком (`mode/concurrency/max_ticks/stall_rounds/budget_tokens/pace_seconds/stop_on_human_gate/disabled_stages`).
  Ключей `current_sprint`/`sprint_model`/`sprint_carryover` больше нет — спринт стал Status-колонкой
  `Sprint`. Если они остались в локальном профиле от старой версии — можно удалить (не обязательно).

Покажи, что будет добавлено; в `--dry-run` — только показать. При отсутствии блока `orchestrator:`
целиком — добавить его после блока `quality:`.

### ШАГ 4 — Применение (если не --dry-run)

- **Framework** `CHANGED`/`NEW` → записать из источника. `SAME`/`LOCAL` → пропустить.
- **Accumulator** → записать ТОЛЬКО если `NEW` (нет локально). `SEED-SKIP` → пропустить.
- **Profile keys** → дописать недостающие (ШАГ 3.5), значения не менять.
- **Никогда**: не удалять локальные файлы; не трогать `project-profile.md` (кроме добавления
  ключей), `board.env`, `settings*.json`, содержимое `memory/`.

### ШАГ 5 — Отчёт + следующие шаги

```
REFRESH COMPLETE — {date} · source: <source>

Framework applied:  {N} обновлено, {M} добавлено
Accumulator seeded: {k} (пропущено заполненных: {s})
Profile keys added: {список или «нет»}
Preserved:          project-profile.md (значения), board.env, settings*, memory/*
Local-only kept:    {файлы}

NEXT STEPS:
  • /setup-board — добавить новые поля доски (Parked, Sprint), если их ещё нет (идемпотентно)
  • сверь профиль: значения стека/команд — твои; добавлены только новые ключи
  • /board — проверить, что доска читается
  • закоммить: git add .claude/ && git commit -m "chore: обновить агентский фреймворк"

{if dry-run}  DRY RUN — ничего не применено. Запусти без --dry-run.  {endif}
```

Подробный сценарий подключения/миграции на новый проект — `.claude/DISTRIBUTION.md`.
