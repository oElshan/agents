---
description: "Kanban: Sweep (алиас /orchestrate). Автопилот right-to-left, один проход, последовательно. Примеры: /sweep | /sweep testing | /sweep dry-run"
argument-hint: "<пусто=всё | sprint | ready-for-dev | testing | ready-to-deploy | dry-run>"
---

# SWEEP — алиас `/orchestrate` (один последовательный проход)

`/sweep` — это пресет единого оркестратора: **один тик, right-to-left, по очереди**
(`mode=once concurrency=seq`). Полное поведение, гейты, диспатч Team Leads, отчёт —
в `.claude/commands/orchestrate.md`. Здесь только маппинг аргументов.

## Маппинг `$ARGUMENTS` → политика оркестратора

| `/sweep …` | Политика `/orchestrate` |
|---|---|
| *(пусто)* | `mode=once concurrency=seq scope=board` |
| `dry-run` | `mode=once concurrency=seq scope=board dry_run=true` |
| `sprint` | `mode=once concurrency=seq scope=sprint` — приём новой работы из колонки `Sprint` |
| `ready-for-dev` | `mode=once concurrency=seq scope=ready-for-dev` |
| `testing` | `mode=once concurrency=seq scope=testing` |
| `ready-to-deploy` | `mode=once concurrency=seq scope=ready-to-deploy` |

**Действие:** разверни аргумент в политику выше и выполни `.claude/commands/orchestrate.md`
с ней (Шаги 1–8). Ничего здесь больше не дублируется.
