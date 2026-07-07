---
description: "Kanban: Analysis. Декомпозиция фичи → User Stories + spec + arch. Примеры: /analyze #50 | /analyze #19 #20 (несколько параллельно)"
argument-hint: "<#N issue или несколько через пробел>"
---

# KANBAN — Analysis: $ARGUMENTS

Запусти **Analysis Team Lead** для полного анализа Feature Request.

## Алгоритм

### ШАГ 1 — Сбор контекста

```
Read(".claude/project-profile.md")  # ПЕРВЫМ: стек и команды из commands.*; если initialized: false — Fallback Detect из профиля
Read("CLAUDE.md")
Read("ARCHITECTURE.md")  # если есть
Glob("docs/specs/**/*.md")
Glob("docs/arch/**/*.md")
```

Получи Feature Request:
```
mcp__github__get_issue(issue_number: {N})
```

Переведи issue в колонку Analysis:
```
kanban_set {N} "Analysis"   # хелпер из .claude/agents/kanban-board-sync.md
```

### ШАГ 2 — Запуск Analysis Team Lead

Делегируй работу **analysis-lead**, который координирует analyst + architect:

```
Agent(subagent_type="analysis-lead", prompt="Analyze feature $ARGUMENTS.
Read .claude/project-profile.md FIRST (stack/topology/commands source of truth; if initialized: false — run its Fallback Detect), then CLAUDE.md and ARCHITECTURE.md (if exists) for project context.

Your team:
- analyst: decompose feature into User Stories, write spec
- architect: create architecture design, stub files

Steps:
1. Run analyst first:
   - Get issue from GitHub
   - Decompose into User Stories (separate issues)
   - Each story: board fields, NO labels — kb_meta {story} type=story priority={level} size={est} component={csv}; then kanban_set {story} "Ready for Dev"
   - Write spec: docs/specs/feature-{N}-{name}.md

2. After analyst completes, run architect:
   - Read the spec created by analyst
   - Create arch doc: docs/arch/feature-{N}-{name}.md
   - Define entities, services, controllers, DTOs per project stack from project-profile.md (stack.*, topology.services)
   - Create stub files with TODO markers
   - Comment on issue with arch design summary

3. Update parent feature issue:
   - Add links to all created stories
   - Add links to spec and arch docs

4. Change stages ONLY via kanban_set; story metadata ONLY via kb_meta — NO labels (helpers in .claude/agents/kanban-board-sync.md).

Report consolidated results.")
```

### ШАГ 3 — Финальный отчёт

```
ANALYSIS COMPLETE
Feature: #{N} — {title}
Team Lead: analysis-lead
  → analyst: {count} stories created
  → architect: arch doc ready

Stories: #{s1}, #{s2}, #{s3}
Spec: docs/specs/feature-{N}-{name}.md
Arch: docs/arch/feature-{N}-{name}.md
Stories in: ready-for-dev
Next step: /develop #{story_number} или /pick ready-for-dev
```
