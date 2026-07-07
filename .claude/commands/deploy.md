---
description: "Kanban: Deploy. Сборка + деплой на staging/production. Примеры: /deploy #96 | /deploy staging | /deploy all | /deploy production"
argument-hint: "<#N issue | staging | production | all>"
---

# KANBAN — Deploy: $ARGUMENTS

Запусти **Ops Team Lead** для деплоя.

## Алгоритм

### ШАГ 1 — Определи scope

```
Read(".claude/project-profile.md")  # ПЕРВЫМ: deploy-команды из commands.deploy.*, сервисы из topology.services; если initialized: false — Fallback Detect из профиля
Read("CLAUDE.md")
```

- Если номер → конкретный issue (должен быть Status="Ready to Deploy" + поле QA=passed)
- Если "staging" / "all" → все в колонке "Ready to Deploy"
- Если "production" → подготовка к ручному деплою

### ШАГ 2 — Запуск Ops Team Lead

Делегируй работу **ops-lead**, который координирует devops:

```
Agent(subagent_type="ops-lead", prompt="Deploy: $ARGUMENTS.
Read .claude/project-profile.md FIRST (deploy commands from commands.deploy.*, services from topology.services; if initialized: false — run its Fallback Detect), then CLAUDE.md and ARCHITECTURE.md (if exists) for project context.

Your team:
- devops: build, deploy, monitoring using project's infra from project-profile.md (commands.deploy, stack.infra, topology)

If '$ARGUMENTS' is a number:
  Get issue: mcp__github__get_issue(issue_number: {N})
  Verify: Status="Ready to Deploy" (kanban_query "Status" "Ready to Deploy") AND QA==passed (kb_get {N} QA)

If '$ARGUMENTS' is 'staging' or 'all':
  Get all: kanban_query "Status" "Ready to Deploy" (then keep only those with QA==passed via kb_get)

Steps:
1. Pre-deploy validation: run tests and build using commands from project-profile.md (commands.backend.test / commands.backend.build; for microservices — commands.backend.test_one_service per affected service)
   If tests fail → STOP, do NOT deploy

2. Spawn devops agent for staging deploy
   (flow: Ready to Deploy → (G7 pre-flight) → Deploy → (G8) → Done):
   - Quality Gate G7 pre-flight (QA=passed, Security=passed, build green); for production wait human APPROVE
   - For each issue being deployed: kanban_set {N} "Deploy"  (G7 passed)
   - Build artifacts / images according to commands.deploy (and commands.backend.build / commands.frontend[].build)
   - Deploy via commands.deploy.staging from project-profile.md — primary scenario is Kubernetes (helm upgrade --install / kustomize / kubectl apply); docker-compose is the alternative for non-k8s projects
   - For k8s: verify rollout via commands.deploy.status (kubectl rollout status) for EACH affected service; readiness/liveness probes must be green
   - Health check EACH affected service via topology.services[].health from profile
   - Smoke test via commands.smoke.staging
   - Quality Gate G8 (health/smoke/logs OK, rollback rehearsal: on staging ACTUALLY run commands.deploy.rollback — helm rollback / kubectl rollout undo — then roll forward again; + kill switch)
   - For each deployed issue: kanban_set {N} "Done" (auto-closes issue) + kb_set {N} Deploy staging
   - Close parent features if all stories done: kanban_set {F} "Done"

3. For production:
   - DO NOT auto-deploy
   - Prepare instructions for manual deploy (commands.deploy.production, namespace commands.deploy.namespaces.production, rollback plan via commands.deploy.rollback)
   - Reference project runbook if available

Change stages ONLY via kanban_set (helpers in .claude/agents/kanban-board-sync.md).

Report: deploy status, health checks, closed issues.")
```

### ШАГ 3 — Финальный отчёт

```
DEPLOY COMPLETE
Team Lead: ops-lead
Environment: {staging|production instructions}

Deployed:
  #{N} — deployed, closed

Health: {status}
Features closed: #{F1}
Next: production deploy (manual)
```
