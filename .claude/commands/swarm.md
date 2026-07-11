---
description: "Kanban: Swarm (алиас /orchestrate). Один проход, все Team Leads параллельно. Примеры: /swarm | /swarm develop #97 #98 | /swarm test | /swarm dry-run"
argument-hint: "<пусто=вся доска | analyze|develop|test|deploy [#N …] | dry-run>"
---

# SWARM — алиас `/orchestrate` (один параллельный проход)

`/swarm` — это пресет единого оркестратора: **один тик, все Team Leads параллельно**
(`mode=once concurrency=parallel`, `run_in_background=true`). Полное поведение, гейты,
диспатч, отчёт, известное ограничение по гонкам — в `.claude/commands/orchestrate.md`.

## Маппинг `$ARGUMENTS` → политика оркестратора

Stage → колонка Status: `analyze`→Backlog, `develop`→Ready for Dev, `test`→Testing, `deploy`→Ready to Deploy.

| `/swarm …` | Политика `/orchestrate` |
|---|---|
| *(пусто)* | `mode=once concurrency=parallel scope=board` |
| `dry-run` | `mode=once concurrency=parallel scope=board dry_run=true` |
| `analyze [#N …]` | `mode=once concurrency=parallel scope=backlog [#N …]` |
| `develop [#N …]` | `mode=once concurrency=parallel scope=ready-for-dev [#N …]` |
| `test [#N …]` | `mode=once concurrency=parallel scope=testing [#N …]` |
| `deploy [#N …]` | `mode=once concurrency=parallel scope=ready-to-deploy [#N …]` |
| `<stage> dry-run` | как выше + `dry_run=true` |

`#N …` (если указаны) — обрабатывать только эти issue в колонке.

**Действие:** разверни аргумент в политику выше и выполни `.claude/commands/orchestrate.md`
с ней (Шаги 1–8).
