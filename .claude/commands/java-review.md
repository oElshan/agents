---
description: Запуск java-reviewer — Senior Java + System Design ревью изменённого кода (delta)
argument-hint: "[#N | #N #M #K | пусто = ad-hoc diff]"
---

# JAVA REVIEW: $ARGUMENTS

Запусти субагента `java-reviewer`. Полный алгоритм ревью (pipeline, чек-листы
SEC/CA/SOL/CC/ERR/SPR/JPA/VT/API/LOAD/CONC/OBS/MJ/TEST, severity, формат отчёта,
GitHub-actions, memory) описан в самом агенте — **не дублируй его в prompt'е**.
Команда только определяет режим и передаёт контекст.

## ШАГ 1 — Режим

- `$ARGUMENTS` пустой → **ad-hoc**: ревью текущего diff, без GitHub-действий
- Один `#N` → **single story**
- Несколько `#N #M ...` → **swarm**: параллельный запуск по каждой story (max
  quality.wip_limit из `.claude/project-profile.md`, default 5, одновременно; больше — батчами)

## ШАГ 2 — Pre-flight (быстрая проверка, не подменяет работу агента)

```
git rev-parse --is-inside-work-tree   # не git-репозиторий → стоп, сообщи
ls build.gradle build.gradle.kts pom.xml 2>/dev/null | head -1   # нет build-файла → стоп
# DEFAULT_BRANCH = github.default_branch из .claude/project-profile.md;
# фолбэк: git remote show origin | sed -n 's/.*HEAD branch: //p'
```

Для каждого `#N` проверь наличие `.claude/memory/stories/story-{N}.md` — передай
результат агенту, чтобы он не искал вслепую.

## ШАГ 3 — Запуск

**Single** (`/java-review #97`):

```
Agent(subagent_type="java-reviewer", prompt="
Mode: story
Story: #97
Story-файл: {есть → .claude/memory/stories/story-97.md | нет → возьми scope из
mcp__github__get_issue(97) + git diff ${DEFAULT_BRANCH}...HEAD -- '*.java'}
Выполни свой полный pipeline. GitHub-actions и memory-write — включены.")
```

**Swarm** (`/java-review #97 #98 #99`) — тот же prompt на каждую story,
`run_in_background=true`, дождись всех:

```
Agent(subagent_type="java-reviewer", prompt="Mode: story\nStory: #97\n...", run_in_background=true)
Agent(subagent_type="java-reviewer", prompt="Mode: story\nStory: #98\n...", run_in_background=true)
Agent(subagent_type="java-reviewer", prompt="Mode: story\nStory: #99\n...", run_in_background=true)
```

⚠️ Swarm-ограничение: если несколько story в одном branch/одних файлах — запускай
последовательно, иначе агенты будут флагать чужие изменения.

**Ad-hoc** (`/java-review`):

```
Agent(subagent_type="java-reviewer", prompt="
Mode: ad-hoc
Scope: на feature-branch → git diff ${DEFAULT_BRANCH}...HEAD -- '*.java';
на default branch → git diff HEAD~1 -- '*.java'
(DEFAULT_BRANCH — github.default_branch из .claude/project-profile.md)
Выполни свой полный pipeline, НО: отчёт в stdout, без mcp__github__* вызовов,
без создания issues, без memory-write. Только findings (ID, severity, confidence,
file:line, рекомендация) + Quality Gate + Verdict.")
```

## ШАГ 4 — Финальный отчёт (агрегируй ответы агентов, не пересчитывай findings сам)

```
JAVA REVIEW COMPLETE
Mode: {ad-hoc | single | swarm}

PASSED:
  #{N} — findings: {crit}/{high}/{med}/{low}
WARNING:
  #{N} — MEDIUM/LOW: {count}
FAILED:
  #{N} — блокирующие: {ID, ID, ...} | bug-issues: #{X} #{Y}

Summary: {passed}/{warning}/{failed} из {total}
Next steps:
  - FAIL → /develop #{N} (fix в том же branch feature/{N}-*, затем повторный
    /java-review #{N}; max quality.fix_loop_max циклов (default 3), дальше — эскалация человеку)
  - PASS/WARNING → продолжай pipeline (/test #{N} или /deploy)
  - Был SEC-* → убедись, что эскалация в security-reviewer состоялась
```

## Правила

1. Не дублируй чек-листы и формат отчёта агента — единственный источник истины
   это `.claude/agents/java-reviewer.md`.
2. Не запускай ревью повторно при таймауте агента — спроси пользователя.
3. Swarm по пересекающимся файлам → последовательно.
4. Ad-hoc никогда не пишет в GitHub и memory.
