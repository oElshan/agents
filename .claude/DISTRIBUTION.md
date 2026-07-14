# Раздача фреймворка на другой проект (git submodule)

Как подключить эту агентскую систему к другому проекту (в т.ч. где работала **старая модель**),
держать её обновляемой через git и не затирать проект-специфичные данные.

> **Статус тулинга:** remote фреймворка есть (`https://github.com/oElshan/agents.git`, `main`==`develop`).
> Обёртка `/adopt` реализована, но у неё есть ограничение bootstrap'а (курица и яйцо) — см. §3:
> **первое** подключение со старой версии всегда делается вручную, `/adopt` берёт на себя апдейты.

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
| **Profile keys** (мёрдж) | новые ключи в `project-profile.md` (`orchestrator.*`, `disabled_stages`) | merge — добавляем недостающие ключи с дефолтами, существующие значения НЕ меняем (спринт — Status-колонка, не ключ) |

Профиль — особый случай: сам файл проект-специфичен (стек/команды/пороги), но при обновлении
фреймворка в нём появляются **новые ключи**. Их надо добавить, не тронув проектные значения.

---

## 3. Однократное подключение (в т.ч. миграция со старой модели)

> ⚠️ **Проблема курицы и яйца.** Команда `/adopt` живёт в самом фреймворке (`.claude/commands/adopt.md`).
> На проекте, где стоит **старая версия** (или фреймворка нет вообще), `/adopt` ещё **не существует** —
> значит первым шагом её вызвать нельзя. Поэтому **первое подключение всегда bootstrap вручную**
> (git + `/refresh-agents --source`), а `/adopt` берёт на себя все **последующие** обновления.
> Исключение: если `adopt.md` установлен на уровне пользователя (`~/.claude/commands/adopt.md`) —
> тогда `/adopt` доступен как first-touch в любом проекте.

### Bootstrap — первое подключение (обязательно вручную)

```bash
# 0. remote фреймворка уже есть → https://github.com/oElshan/agents.git (main == develop)

# --- в целевом проекте ---
git submodule add https://github.com/oElshan/agents.git .agents-framework   # 1. сабмодуль (source of truth)
git submodule update --init --recursive .agents-framework
/refresh-agents --source .agents-framework      # 2. синк СТАРОЙ командой (она уже умеет --source):
#    принесёт новые файлы, включая adopt.md/orchestrate.md/sprint.md/stage.md и новый refresh
```
→ **перезапусти Claude Code** (чтобы `.claude/commands/` перечитались и появились новые команды), далее:
```bash
/adopt --update        # 3. правильный синк: seed accumulator + мёрдж ключей профиля + поля доски
/setup-board           # 4. поля доски + колонка Sprint в Status (идемпотентно)
/init                  # 5. если project-profile.md нет — авто-детект стека
/sprint add #N …       # 6. взять задачи в работу (положить в колонку Sprint)
/board
```

> Нет даже старого `/refresh-agents --source`? Сделай шаг 2 руками: скопируй
> `.agents-framework/.claude/{agents,commands}` в `.claude/` (framework-файлы overwrite; `project-profile.md`,
> `board.env`, `settings*.json`, `memory/` — **не трогай**, см. §2), затем перезапуск и шаги 3–5.

### `/adopt` — одной командой (когда новая версия уже стоит / для апдейтов)

Доступно после bootstrap либо при глобальной установке `~/.claude/commands/adopt.md`:
```bash
/adopt https://github.com/oElshan/agents.git   # первое подключение одной командой (если /adopt уже доступен)
/adopt --update                                 # обновить уже подключённый фреймворк
/adopt <url> --dry-run                          # план без изменений
```
`/adopt` сам определит режим (MIGRATION — старый фреймворк уже есть / FRESH — чистый проект),
подключит сабмодуль, синкнет в `.claude/`, добавит поля доски и домёрджит ключи профиля.

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
