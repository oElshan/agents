---
description: "Оркестратор: вкл/выкл стадии. Отключённая стадия не запускается — задачи ждут в буфере, токены экономятся. Примеры: /stage off deploy | /stage on testing | /stage"
argument-hint: "<пусто=статус | off <стадия…> | on <стадия…|all>>"
---

# STAGE — пауза/возобновление стадий оркестратора: $ARGUMENTS

Постоянно включает/выключает стадии конвейера для `/orchestrate` (и его алиасов
`/sweep`/`/swarm`/`/pick`). **Отключённая стадия = пауза, а не пропуск:** её Team Lead не
запускается (ноль токенов), задачи копятся в буфере перед стадией и ждут. Включишь обратно —
накопленное потечёт дальше. Ничего не деградирует и не пропускается.

Состояние хранится в `.claude/project-profile.md` → `orchestrator.disabled_stages`
(единый источник правды; коммитится — вся команда видит, что на паузе).

Для **разового** отключения на один запуск (без записи в профиль) — токен `skip:` прямо в
оркестраторе: `/orchestrate skip:deploy,testing`.

---

## Стадии

| Стадия | Синонимы | Team Lead (не запускается) | Задачи ждут в |
|---|---|---|---|
| `analysis` | `analyze` | analysis-lead | `Sprint` (feature/epic) |
| `develop` | `dev` | dev-lead | Ready for Dev (+ dev-ready в `Sprint`) |
| `testing` | `qa`, `test` | qa-lead | Testing |
| `deploy` | `ops` | ops-lead | Ready to Deploy |

> **Нельзя отключить security-ревью** — это защитный гейт внутри `develop` (Code Review),
> не отдельная стадия. Отключение `develop` останавливает приём новых в разработку целиком.
>
> **Пауза дорабатывает in-flight (drain):** уже начатые задачи в активных статусах стадии
> доводятся до выхода — worktree/деплой не бросаются на полдороге. Пауза стопит только **приём новых**.

---

## Алгоритм

### 1. Разбери `$ARGUMENTS`

```
(пусто)                 → показать статус (Шаг 3), ничего не менять
off  <стадия> [<…>]     → добавить стадии в disabled_stages
on   <стадия> [<…>]     → убрать стадии из disabled_stages
on   all | reset        → очистить disabled_stages (включить всё)
```

Синонимы (Шаг «Стадии») нормализуй к каноническому имени. Глаголы-синонимы:
`off`=`disable`=`pause`, `on`=`enable`=`resume`. Неизвестную стадию — отвергни со списком допустимых.

### 2. Обнови профиль

Прочитай текущий `orchestrator.disabled_stages` из `.claude/project-profile.md`, применни
изменение (множество без дублей, канонические имена) и запиши обратно. Пример результата:

```yaml
  disabled_stages: [testing, deploy]
```

`on all` / `reset` → `disabled_stages: []`.

### 3. Покажи статус + размер буферов

Один дамп доски — чтобы показать, сколько задач сейчас ждёт из-за каждой паузы:

```bash
source .claude/board.env 2>/dev/null && kb_dump > "${TMPDIR:-/tmp}/stage.json" 2>/dev/null
# буферы: analysis→Sprint, develop→Ready for Dev, testing→Testing, deploy→Ready to Deploy
jq -r '[.[]|.status] | {
  "Sprint":          ([.[]|select(.=="Sprint")]|length),
  "Ready for Dev":   ([.[]|select(.=="Ready for Dev")]|length),
  "Testing":         ([.[]|select(.=="Testing")]|length),
  "Ready to Deploy": ([.[]|select(.=="Ready to Deploy")]|length)
}' "${TMPDIR:-/tmp}/stage.json" 2>/dev/null
```

Вывод (буферы показывай только для отключённых стадий; если доски нет — просто статус):

```
СТАДИИ ОРКЕСТРАТОРА — {date}
  analysis  ✅ вкл
  develop   ✅ вкл
  testing   ⛔ ВЫКЛ — 3 задачи ждут в Testing
  deploy    ⛔ ВЫКЛ — 2 задачи ждут в Ready to Deploy

Отключённые не запускаются (0 токенов), задачи копятся в буфере.
Включить: /stage on testing deploy   ·   Включить всё: /stage on all
```

---

## Примеры

```bash
/stage                     # статус всех стадий + сколько ждёт в буферах
/stage off deploy          # пока не деплоим — задачи копятся в Ready to Deploy
/stage off testing         # не пишем TC — qa-lead не запускается, экономим токены
/stage off testing deploy  # выключить обе
/stage on deploy           # вернуть деплой — накопленное поедет
/stage on all              # включить всё
```

Разово, без записи в профиль: `/orchestrate skip:deploy`  ·  `/orchestrate once skip:testing`
