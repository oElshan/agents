---
description: "Kanban: Pick (алиас /orchestrate). Взять ОДНУ следующую задачу по приоритету. Примеры: /pick sprint | /pick ready-for-dev | /pick testing | /pick ready-to-deploy"
argument-hint: "<sprint | ready-for-dev | testing | ready-to-deploy | backlog>"
---

# PICK — алиас `/orchestrate` (одна задача из колонки)

`/pick <колонка>` — это пресет единого оркестратора: **один тик, одна верхняя по приоритету
задача из указанной колонки** (`mode=once concurrency=seq take=1`). Выбор по полю Priority
(`critical → high → medium → low`, при равенстве — меньший #), WIP-проверка, dependency-check —
всё в `.claude/commands/orchestrate.md`.

## Маппинг `$ARGUMENTS` → политика оркестратора

| `/pick …` | Политика `/orchestrate` |
|---|---|
| `sprint` | `mode=once concurrency=seq scope=sprint take=1` — взять одну из очереди `Sprint` → Analysis |
| `ready-for-dev` | `mode=once concurrency=seq scope=ready-for-dev take=1` |
| `testing` | `mode=once concurrency=seq scope=testing take=1` |
| `ready-to-deploy` | `mode=once concurrency=seq scope=ready-to-deploy take=1` |
| `backlog` | `mode=once concurrency=seq scope=backlog take=1` — ⚠️ ручной escape к интейку (автопилот бэклог не трогает) |

Транзитные `Code Review`/`Deploy` не таргетятся — ими владеют dev-lead/ops-lead.

**Действие:** разверни аргумент в политику выше и выполни `.claude/commands/orchestrate.md`
с ней (Шаги 1–8).
