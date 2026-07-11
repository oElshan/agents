# Раздача фреймворка на другой проект (git submodule)

Как подключить эту агентскую систему к другому проекту (в т.ч. где работала **старая модель**),
держать её обновляемой через git и не затирать проект-специфичные данные.

> **Статус тулинга:** runbook работает уже сейчас — вручную и через `/refresh-agents`
> (расширен под этот сценарий). Обёртка-одной-командой (`/adopt`) — на согласовании.

---

## 1. Модель: сабмодуль в подпапке + синк в `.claude/`

Claude Code читает `<корень>/.claude/`, а сабмодуль живёт в подпапке. Поэтому:

- **Сабмодуль** (напр. `.agents-framework/`) — источник правды фреймворка, обновляется через git.
- Его содержимое **синкается** в реальный `.claude/` проекта командой `/refresh-agents`.
- `project-profile.md` и `board.env` остаются **проект-локальными** (в сабмодуль не входят).

**Почему не сделать `.claude/` самим сабмодулем:** тогда проект-специфичные `project-profile.md`
и `board.env` оказались бы внутри сабмодуля — «грязный» сабмодуль и конфликты при `update`.

---

## 2. Что синкается, что сохраняется, что засевается

Единственное правило безопасности синка:

| Категория | Файлы | Поведение при синке |
|---|---|---|
| **Framework** (перезаписывать) | `agents/*.md`, `commands/*.md`, `system/sdc.md`, `system/postdeploy.sh`, `AGENTS_FRAMEWORK.md`, `*_DESIGN.md`, `DISTRIBUTION.md`, `board.env.example`, `memory/stories/_template.md` | overwrite — берём версию из источника |
| **Accumulator** (засеять, если нет) | `system/budget.md`, `system/ownership-map.md` | seed-if-absent — копируем только если файла нет; заполненный НЕ трогаем |
| **Project config** (никогда) | `project-profile.md`, `board.env`, `settings.json`, `settings.local.json`, `memory/` (кроме шаблонов) | preserve — не трогаем совсем |
| **Profile keys** (мёрдж) | новые ключи в `project-profile.md` (`orchestrator.*`, `current_sprint`, `sprint_*`, `disabled_stages`) | merge — добавляем недостающие ключи с дефолтами, существующие значения НЕ меняем |

Профиль — особый случай: сам файл проект-специфичен (стек/команды/пороги), но при обновлении
фреймворка в нём появляются **новые ключи**. Их надо добавить, не тронув проектные значения.

---

## 3. Однократное подключение (в т.ч. миграция со старой модели)

### Одной командой — `/adopt` (рекомендуется)

```bash
# 0. (однократно у фреймворка) запушить репо на remote — сейчас remote'а нет:
#    git remote add origin git@github.com:<you>/claude-agents.git && git push -u origin main

# --- в целевом проекте: всё за раз (submodule + refresh + setup-board + мёрдж профиля) ---
/adopt <url-фреймворка>          # или /adopt --path /локальный/путь/agents
/sprint new "Sprint 1" && /sprint activate "Sprint 1"
/board
```
`/adopt` сам определит режим (MIGRATION — старый фреймворк уже есть / FRESH — чистый проект),
подключит сабмодуль, синкнет в `.claude/`, добавит поля доски и домёрджит ключи профиля.
Обновлять потом: `/adopt --update`. План без изменений: `/adopt <url> --dry-run`.

### Вручную (fallback, если не через /adopt)

```bash
git submodule add <url-фреймворка> .agents-framework   # 1. сабмодуль (source of truth)
/refresh-agents --source .agents-framework              # 2. синк + мёрдж ключей профиля (§2)
/setup-board                                            # 3. поля доски (Parked, Sprint) — идемпотентно
/sprint new "Sprint 1" && /sprint activate "Sprint 1"   # 4. включить спринт
/board
```

### Что именно меняется при миграции со старой модели

- **Команды**: появляются `/orchestrate`, `/stage`, `/sprint` (старые `/sweep`/`/swarm`/`/pick` становятся их алиасами).
- **Доска**: `/setup-board` добавляет поля **Parked** и **Sprint** к существующей доске (идемпотентно — что было, не трогает).
- **Профиль**: `/refresh-agents` дописывает блок `orchestrator:` и ключи спринта; стек/команды/пороги остаются как были.
- **Данные не теряются**: issue, их поля, история — на месте; добавляются только новые поля/ключи/команды.

---

## 4. Обновление фреймворка потом

```bash
/adopt --update        # одной командой: submodule update --remote + refresh + setup-board
git add .claude/ .gitmodules .agents-framework && git commit -m "chore: обновить агентский фреймворк"
```
План без изменений: `/adopt --update --dry-run`.

Вручную (fallback):
```bash
git submodule update --remote .agents-framework
/refresh-agents --source .agents-framework          # framework overwrite, ключи профиля merge
/setup-board                                         # если добавились новые поля доски
```

---

## 5. Закрепить версию фреймворка

Сабмодуль пинится на конкретный коммит (в `.gitmodules` + gitlink). Проект «видит» ровно ту
версию, которую закоммитил — обновление осознанное (`update --remote`), не самопроизвольное.
Хочешь конкретную ветку — `git config -f .gitmodules submodule..agents-framework.branch <ветка>`.

---

## 6. Без remote (локальный источник)

Пока фреймворк не запушен, можно подключить по локальному пути:
```bash
git submodule add /Users/<you>/CTSG/agenst/agents .agents-framework
```
или синкать напрямую без сабмодуля: `/refresh-agents --source /path/to/agents`. Для настоящей
раздачи между машинами/командой — всё же нужен remote (§3, шаг 0).

---

## 7. Траблшутинг

- **Грязный сабмодуль / конфликт при update** — не редактируй файлы внутри `.agents-framework/`;
  все правки фреймворка делай в самом репо-фреймворке, сюда — только `update --remote`.
- **Detached HEAD в сабмодуле** — норма для сабмодулей; версия задаётся из родителя.
- **Команды не видны в целевом проекте** — они читаются из `.claude/commands/`, а не из
  `.agents-framework/`. Значит не прошёл шаг синка — запусти `/refresh-agents --source .agents-framework`.
- **Профиль перезаписался** — не должно быть: `/refresh-agents` профиль не overwrite'ит, только
  мёрджит недостающие ключи. Если сомнения — `--dry-run` покажет план без изменений.
