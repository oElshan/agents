---
description: "Подключить агентский фреймворк к ЭТОМУ проекту через git-сабмодуль (или обновить): submodule + refresh + setup-board + мёрдж профиля. Примеры: /adopt <url> | /adopt --path ~/agents | /adopt --update"
argument-hint: "<url> | --url <git-url> [--dir <d>] | --path <local> | --update | --dry-run"
---

# ADOPT — подключить/обновить агентский фреймворк: $ARGUMENTS

Одной командой ставит эту агентскую систему на **текущий проект** (в т.ч. мигрирует со старой
модели): git-сабмодуль → синк в `.claude/` → поля доски → мёрдж ключей профиля. Тяжёлую логику
делегирует в `/refresh-agents` и `/setup-board` (не дублирует). Полная модель — `.claude/DISTRIBUTION.md`.

> **Выполняется на ЦЕЛЕВОМ проекте**, не в репо-фреймворке. Проект-специфичное
> (`project-profile.md`, `board.env`, `memory/`) не затирается — см. правило синка в DISTRIBUTION §2.

> ⚠️ **Курица и яйцо:** эта команда доступна, только если новая версия фреймворка **уже стоит**
> на проекте (или `adopt.md` установлен глобально в `~/.claude/commands/`). На проекте со старой
> версией `/adopt` ещё нет — **первое** подключение bootstrap-ится вручную:
> `git submodule add <url> .agents-framework` → `/refresh-agents --source .agents-framework` →
> перезапуск Claude Code, и только дальше `/adopt --update`. Полный порядок — DISTRIBUTION §3.

---

## ШАГ 1 — Аргументы и режим

```
/adopt <url>                 → сабмодуль из <url> в .agents-framework, затем полный флоу
/adopt --url <url> [--dir d] → то же, каталог сабмодуля d (default .agents-framework)
/adopt --path <local>        → источник — локальный путь (сабмодуль по локальному пути; для настоящей раздачи нужен remote)
/adopt --update              → обновить уже подключённый фреймворк (submodule update --remote + синк)
/adopt --dry-run             → показать план, ничего не менять
```

Определи **режим** по состоянию проекта:
```bash
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "❌ не git-репозиторий"; exit 1; }
[ -d .claude/agents ] && echo "MIGRATION (старый фреймворк уже есть)" || echo "FRESH (чистый проект)"
```
- **MIGRATION** — на проекте уже был фреймворк: `/adopt` делает всё сам (профиль со стеком уже заполнен → достаточно мёрджа ключей).
- **FRESH** — фреймворка/профиля нет: `/adopt` принесёт фреймворк, но стек не детектит — в конце направит на `/init` (авто-детект стека + заполнение профиля).

### DIR = каталог сабмодуля (default `.agents-framework`).

---

## ШАГ 2 — Сабмодуль (source of truth)

```bash
DIR="${DIR:-.agents-framework}"
if [ -e "$DIR/.claude/agents/developer.md" ]; then
  echo "= сабмодуль уже подключён: $DIR"
elif [ -n "$URL" ]; then
  git submodule add "$URL" "$DIR"          # из remote
elif [ -n "$LOCAL_PATH" ]; then
  git submodule add "$LOCAL_PATH" "$DIR"   # из локального пути
else
  echo "❌ нужен <url> или --path (или --update для уже подключённого)"; exit 1
fi
git submodule update --init --recursive "$DIR"
```
`--update`: `git submodule update --remote "$DIR"` — подтянуть свежую версию фреймворка.
`--dry-run`: не выполнять мутирующие git-команды, только показать, что было бы сделано.

### Нет remote у фреймворка?
Сабмодуль требует URL/путь. Если у репо-фреймворка нет remote — сначала запушь его
(`git remote add origin … && git push`) или используй `--path <локальный-путь>`.

---

## ШАГ 3 — Синк фреймворка → `.claude/`

Выполни логику `/refresh-agents` c источником `$DIR` (см. `.claude/commands/refresh-agents.md`):
```
/refresh-agents --source $DIR            # (или + --dry-run)
```
Это принесёт agents/commands/system/доки (framework — overwrite, accumulator — seed-if-absent),
**не тронет** `project-profile.md`/`board.env`/`memory/` и **домёрджит недостающие ключи профиля**
(`orchestrator.*`, `current_sprint`, `sprint_*`, `disabled_stages`) с дефолтами.

## ШАГ 4 — Доска

Выполни логику `/setup-board` (см. `.claude/commands/setup-board.md`): создаст `board.env`, если
его нет (ШАГ 0), и **идемпотентно** добавит недостающие поля, включая **Parked** и **Sprint**
(существующие поля/данные не трогает). В `--dry-run` — только показать, чего не хватает.

## ШАГ 5 — Профиль (проверка)

Ключи уже домёрджены на ШАГ 3. Убедись:
- стек/команды/пороги (`stack.*`, `commands.*`, `quality.*`) — **проектные, остались как были**;
- добавлены `orchestrator:` и спринт-ключи с дефолтами.
- **FRESH-режим**: если `profile.initialized: false` — предупреди, что стек не детектился, и
  направь на `/init` (авто-детект стека, health-эндпоинты, реальные команды build/test/deploy).

---

## ШАГ 6 — Отчёт

```
ADOPT {MIGRATION|FRESH} {COMPLETE|DRY-RUN} — {date}
Framework: {url|path} @ {commit сабмодуля} → {DIR}

Synced:        {N обновлено, M добавлено} (agents/commands/system/доки)
Board fields:  +Parked +Sprint {или «уже были»}
Profile keys:  +orchestrator.* +sprint_* {или «уже были»}
Preserved:     project-profile значения, board.env, memory/

NEXT STEPS:
  {MIGRATION:}
  • /board — проверить доску
  • /sprint new "Sprint 1" && /sprint activate "Sprint 1"
  • /orchestrate dry-run — план автопилота по спринту
  • закоммить: git add .claude/ .gitmodules {DIR} && git commit -m "chore: подключить агентский фреймворк"
  {FRESH:}
  • /init — авто-детект стека + заполнить project-profile.md (стек не определялся)
  • затем /setup-board (если ещё не создана доска) и шаги MIGRATION выше

  Обновлять фреймворк потом: /adopt --update
```

Полный runbook и траблшутинг — `.claude/DISTRIBUTION.md`.
