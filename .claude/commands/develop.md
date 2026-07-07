---
description: "Kanban: Develop. Реализация story по spec. Примеры: /develop #97 | /develop #97 #98 #99 (параллельно) | /develop #97,#98"
argument-hint: "<#N story или несколько через пробел/запятую>"
---

# KANBAN — Develop: $ARGUMENTS

Запусти **Dev Team Lead** для реализации story/stories.

## Алгоритм

### ШАГ 1 — Подготовка

```
Read(".claude/project-profile.md")  # ПЕРВЫМ: команды из commands.*; если initialized: false — Fallback Detect из профиля
Read("CLAUDE.md")
```

Определи scope:
- Если один номер → single mode
- Если несколько номеров через запятую → swarm mode

### ШАГ 2 — Запуск Dev Team Lead

Делегируй работу **dev-lead**, который координирует developer(ов):

```
Agent(subagent_type="dev-lead", prompt="Develop stories: $ARGUMENTS.
Read .claude/project-profile.md FIRST (commands from commands.*, stack from stack.*; if initialized: false — run its Fallback Detect), then CLAUDE.md and ARCHITECTURE.md (if exists) for project context.

Your team:
- developer (opus): implements code per project stack from project-profile.md (stack.*) and CLAUDE.md

Steps for EACH story:
1. Get issue: mcp__github__get_issue(issue_number: {N})
2. Check WIP limit: max quality.wip_limit (default 5) stories with Status="In Development" (kanban_query "Status" "In Development")
3. Read linked spec and arch docs from docs/specs/ and docs/arch/
4. Spawn developer agent:
   - Transition: kanban_set {N} "In Development"
   - Create branch: story/{N}-{short-name} from the feature branch (feature branch itself is created from github.default_branch per profile)
   - Implement backend and/or frontend per spec
   - Write basic unit tests (coverage >= quality.unit_coverage_min, default 95%)
   - Verify build (commands.backend.build / commands.frontend[].build from profile)
   - Commit: feat(#{N}): {description}
   - developer COMMITS and STAYS in "In Development" (does NOT move to Testing)
   - Comment on issue with file list and build status
5. dev-lead runs Quality Gate G4 (build+test SUCCESS via commands.* from profile, story-branch merged into feature, handoff + coverage >= quality.unit_coverage_min, clean git status)
   → kanban_set {N} "Code Review"
6. dev-lead spawns reviewers IN PARALLEL by delta: security-reviewer (ALWAYS) + java-reviewer (only if backend-delta: *.java/*.kt) + frontend-reviewer (only if frontend-delta: *.ts/*.tsx/*.jsx/*.html/*.scss in frontend app paths from profile). They set fields Security / JavaReview / FrontendReview; a non-applicable reviewer is NOT spawned, its field stays pending, dev-lead notes 'N/A — no matching files in delta' in Gate Report
7. dev-lead runs Quality Gate G5: Security=passed AND (JavaReview in {passed,warning} IF backend-delta) AND (FrontendReview in {passed,warning} IF frontend-delta); warning does not block (tech-debt)
   → kanban_set {N} "Testing"

For MULTIPLE stories:
- Analyze dependencies between stories
- Independent stories (different components) → run developers in PARALLEL
- Dependent stories (shared entities) → run SEQUENTIALLY
- Never exceed WIP limit quality.wip_limit (default 5)

Change stages ONLY via kanban_set (helpers in .claude/agents/kanban-board-sync.md).

Report consolidated results: branch names, files changed, build status per story.")
```

### ШАГ 3 — Финальный отчёт

```
DEVELOPMENT COMPLETE
Team Lead: dev-lead
Mode: {single|swarm}

Stories:
  #{N} — {title}
  Branch: story/{N}-{short-name}
  Files: {count} changed
  Build: {status}
  Tests: {passed}/{total}
  Column: Testing (через Code Review)

WIP: {count}/{quality.wip_limit}
Next step: /test #{N}
```
