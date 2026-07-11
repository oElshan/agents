---
description: "Kanban: Init. Полная инициализация агентской системы на проекте (с нуля или существующем). Запускать ОДИН раз. Пример: /init"
argument-hint: ""
---

# KANBAN — Project Initialization

Однократный bootstrap агентской Kanban-системы на ЛЮБОМ проекте: Java-монолит или
микросервисы, Angular и/или React (в т.ч. несколько frontend-приложений), Kubernetes или
docker-compose. Эта команда — АДАПТЕР системы под проект. Её результат:
**заполненный `.claude/project-profile.md`** (единственный источник правды о стеке и
командах — его читают ВСЕ агенты) и **`.claude/board.env`** (идентичность GitHub Project
board — из него константы доски берут все хелперы).

Роли и команды системы — **все файлы из `.claude/agents/` и `.claude/commands/`** (в т.ч.
java-reviewer, frontend-reviewer, e2e-tester, test-case-writer, doc-sync); их количество
НЕ хардкодится — источник правды сами каталоги.

> **`/init` vs `/adopt`.** `/init` детектит стек и заполняет профиль/board.env — это адаптация
> под проект. **Доставка/обновление самого фреймворка** (через git-сабмодуль) и **миграция со
> старой модели** — команда **`/adopt`** (submodule + `/refresh-agents` + `/setup-board` + мёрдж
> ключей профиля); runbook — `.claude/DISTRIBUTION.md`. На чистом проекте порядок: `/adopt` →
> `/init` (детект стека) → `/sprint`. На проекте со старым фреймворком достаточно `/adopt`.

## Идемпотентность (повторный запуск)

- `.claude/project-profile.md` с `initialized: true` **НЕ перезаписывается без явного
  подтверждения человека**: покажи `updated:` и спроси «профиль уже заполнен — пересканировать
  и перезаполнить?». Без ответа «да» — профиль не трогать, продолжить с ШАГ 4.
- Существующие `.claude/board.env`, `CLAUDE.md`, `docs/adr/ADR-001-*` не перезаписываются —
  только валидируются/дополняются недостающими разделами.
- Поля доски, workflow, docs/-каталоги, issues создаются с проверкой существования — дублей нет.

## Алгоритм (АВТОНОМНО; вопросы человеку помечены явно)

### ШАГ 1 — Проверка окружения

```bash
# 1.1 git-репозиторий
git rev-parse --is-inside-work-tree || { echo "❌ Не git-репозиторий — сначала 'git init'"; exit 1; }

# 1.2 remote origin (owner/repo понадобятся на ШАГ 4)
git remote get-url origin || { echo "❌ Нет remote origin — 'gh repo create' или 'git remote add origin …'"; exit 1; }

# 1.3 gh CLI: авторизация + scopes (нужны: repo, project, read:org)
gh auth status || { echo "❌ gh не авторизован — 'gh auth login'"; exit 1; }
gh auth status 2>&1 | grep -i "token scopes" || true
# если среди scopes нет repo / project / read:org:
#   gh auth refresh -s repo -s project -s read:org

# 1.4 jq — на нём все хелперы доски
command -v jq >/dev/null || { echo "❌ Нет jq — brew install jq | apt-get install jq | scoop install jq"; exit 1; }

# 1.5 default branch (пойдёт в профиль как github.default_branch)
MAIN_BRANCH=$(git remote show origin 2>/dev/null | grep "HEAD branch" | awk '{print $NF}')
echo "Default branch: ${MAIN_BRANCH:-main}"
```

### ШАГ 2 — Скан стека

Просканируй репозиторий. Детект по артефактам, НЕ по догадкам. Правила команд:
**сначала wrapper** (`./gradlew`, `./mvnw`), только потом глобальные `gradle`/`mvn`;
npm-скрипты читать из реального `package.json` → `scripts` каждого приложения — НЕ угадывать.

| Что ищем | Признак | Вывод в профиль |
|---|---|---|
| Build tool | `gradlew` / `build.gradle(.kts)` | `stack.backend.build_tool=gradle` |
| | `mvnw` / `pom.xml` | `maven` |
| Backend framework | `org.springframework.boot` starter'ы в build-файлах / аннотация `@SpringBootApplication` | `spring-boot-<major>` |
| | quarkus / micronaut зависимости | соответственно |
| **Микросервисы** | несколько модулей с main-классами (include в `settings.gradle` + `grep -rl "static void main"`), несколько `Dockerfile`, каталог `services/` | `topology.type=microservices` + таблица `topology.services` |
| **Frontend (может быть НЕСКОЛЬКО)** | `angular.json` вне node_modules | приложение `framework=angular` |
| | `react` в `dependencies` какого-либо `package.json` | приложение `framework=react` |
| БД / кэш / брокер | образы в `docker-compose*.yml` (postgres/mysql/mongo/redis/kafka/rabbitmq…), k8s-манифесты, `application*.yml` (`spring.datasource`, `spring.data.redis`, `spring.kafka`) | `stack.data.*` |
| Kubernetes | `Chart.yaml` | `k8s_tooling=helm` |
| | `kustomization.yaml` | `k8s_tooling=kustomize` |
| | `kind: Deployment` в `*.yaml` | `orchestration=kubernetes` + `k8s_manifests_path` |
| Миграции | каталог `**/src/main/resources/db/migration` | `migration_tool=flyway` |
| | `liquibase` в build-файле / changelog | `migration_tool=liquibase` |
| CI | `.github/workflows/` | `ci=github-actions` |
| | `.gitlab-ci.yml` / `Jenkinsfile` | `gitlab-ci` / `jenkins` |
| Мониторинг | prometheus в compose/k8s, `micrometer-registry-prometheus` | `monitoring=prometheus` (+ `metrics_url`, если известен) |

```bash
# примеры детект-команд (адаптируй под проект)
ls gradlew mvnw build.gradle build.gradle.kts pom.xml settings.gradle package.json angular.json 2>/dev/null
find . -maxdepth 4 -name Dockerfile -not -path '*/node_modules/*' -not -path '*/build/*'
find . -maxdepth 5 \( -name angular.json -o -name package.json \) -not -path '*/node_modules/*'
grep -rlE "kind:[[:space:]]*Deployment" --include='*.y*ml' . 2>/dev/null | grep -vE 'node_modules|\.github'
find . -type d -path '*src/main/resources/db/migration' -not -path '*/build/*'
ls docker-compose*.yml compose*.yml .github/workflows .gitlab-ci.yml Jenkinsfile 2>/dev/null
```

### ШАГ 3 — Заполни `.claude/project-profile.md`

Открой `.claude/project-profile.md` (шаблон — контракт ключей) и заполни ВСЕ секции
результатами ШАГ 2:

- `profile.initialized: true`, `profile.updated: <сегодня YYYY-MM-DD>`;
- `github.*`: owner/repo/default_branch — из ШАГ 1; `project_number`/`project_id` дозаполнишь на ШАГ 4;
- `stack.*`: backend (language/framework/build_tool/java_version), frontend — **запись на
  КАЖДОЕ найденное приложение**, data (databases/caches/brokers/migration_tool), infra;
- `topology.*`: type, shared_contracts (модуль общих DTO/Events, если есть), `services` —
  таблица по строке на сервис (name/path/kind/port/health; порт — из `application*.yml`
  `server.port` / `EXPOSE` в Dockerfile / k8s Service; health — для Spring Boot обычно
  `/actuator/health`);
- `commands.*`: **реальные команды проекта**. Для npm-скриптов прочитай `scripts` из
  `package.json` каждого приложения и подставь существующие (например `npm run build` —
  только если script `build` реально есть). Wrapper first. Для multi-module — плейсхолдер
  `{service}` в `test_one_service`;
- `quality.*`: дефолты — `unit_coverage_min: 95`, `hotfix_coverage_min: 50`, `wip_limit: 5`,
  `fix_loop_max: 3`. **СПРОСИ человека**, хочет ли иные пороги (ответ «дефолты» — оставить как есть).
- `orchestrator.*`: дефолты петли `/orchestrate` — `mode: continuous`, `concurrency: auto`,
  `max_ticks: 20`, `stall_rounds: 2`, `budget_tokens: null`, `pace_seconds: 1200`,
  `stop_on_human_gate: true`, `disabled_stages: []`. Обычно оставить как есть.
- Спринтовая модель: `current_sprint: ""` (оркестратор работает только по текущему спринту,
  бэклог не трогает — ставится позже через `/sprint activate`), `sprint_model: stories`,
  `sprint_carryover: next`.

⚠️ Если профиль уже `initialized: true` — см. раздел «Идемпотентность» (подтверждение обязательно).

### ШАГ 4 — Создай `.claude/board.env`

По образцу `.claude/board.env.example` (board.env коммитится — секретов в нём нет):

```bash
# OWNER/REPO — из origin; при неоднозначности (несколько remote, форк) уточни у человека
NWO=$(git remote get-url origin | sed -E 's#^(git@|ssh://git@|https://)([^/:]+)[:/]##; s#\.git$##')
OWNER=${NWO%%/*} ; REPO=${NWO##*/}

# PROJECT_NUMBER: существующая доска …
gh project list --owner "$OWNER" --format json --jq '.projects[] | "\(.number)\t\(.title)"'
# (если у owner'а уже есть подходящий Project — СПРОСИ человека, какой номер использовать)

# … или новая:
PROJECT_NUMBER=$(gh project create --owner "$OWNER" --title "$REPO" --format json --jq .number)

# PROJECT_ID — node-id доски:
PROJECT_ID=$(gh project view "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq .id)

printf 'OWNER="%s"\nREPO="%s"\nPROJECT_NUMBER=%s\nPROJECT_ID="%s"\n' \
  "$OWNER" "$REPO" "$PROJECT_NUMBER" "$PROJECT_ID" > .claude/board.env
```

Дозаполни `github.project_number` / `github.project_id` в project-profile.md этими же
значениями. Если `.claude/board.env` уже существует и `gh project view "$PROJECT_NUMBER"
--owner "$OWNER"` отвечает — файл не трогать.

### ШАГ 5 — Поля доски (логика /setup-board)

Выполни `.claude/commands/setup-board.md` целиком (идемпотентно — существующие поля
пропускаются): 13 полей — Status, Type, Priority, Size, Component, Security, JavaReview,
FrontendReview, QA, Deploy, Coverage, Parked, Sprint; Status-опции с цветами и описаниями agent-per-status;
UI-настройка встроенных workflows проекта; напоминание о секрете `KANBAN_PROJECT_TOKEN`.
Setup-board сам читает `.claude/board.env` из ШАГ 4.

### ШАГ 6 — Backstop workflow `.github/workflows/kanban-reconcile.yml`

Сгенерируй файл по шаблону ниже, **подставив реальные значения из `.claude/board.env`**
вместо `__OWNER__` / `__REPO__` / `__PROJECT_ID__` (если файл уже существует — сверь значения,
не дублируй). Workflow — детерминированный backstop: на `issues: closed/reopened/opened`
приводит Status ↔ open/closed в порядок и доносит на доску issue без item (см. раздел
Backstop в `.claude/agents/kanban-board-sync.md`).

```yaml
# Генерируется /init: __OWNER__/__REPO__/__PROJECT_ID__ заменены значениями из .claude/board.env
name: kanban-reconcile

on:
  issues:
    types: [opened, closed, reopened]
  workflow_dispatch:

jobs:
  reconcile:
    runs-on: ubuntu-latest
    if: github.repository == '__OWNER__/__REPO__'
    env:
      GH_TOKEN: ${{ secrets.KANBAN_PROJECT_TOKEN }}
      OWNER: '__OWNER__'
      REPO: '__REPO__'
      PROJECT_ID: '__PROJECT_ID__'
      ISSUE: ${{ github.event.issue.number }}
    steps:
      - name: Reconcile Status <-> issue state
        run: |
          set -euo pipefail
          # поле Status: id + опции (резолв по имени, без хардкода id)
          F=$(gh api graphql -f query='{ node(id:"'"$PROJECT_ID"'"){ ... on ProjectV2 { field(name:"Status"){ ... on ProjectV2SingleSelectField { id options{ id name } } } } } }')
          FID=$(echo "$F" | jq -r '.data.node.field.id')
          opt(){ echo "$F" | jq -r --arg n "$1" '.data.node.field.options[]|select(.name==$n)|.id'; }
          set_status(){ gh api graphql -f query="mutation{ updateProjectV2ItemFieldValue(input:{ projectId:\"$PROJECT_ID\" itemId:\"$1\" fieldId:\"$FID\" value:{ singleSelectOptionId:\"$2\" } }){ projectV2Item{ id } } }" >/dev/null; }
          reconcile(){ local n="$1" D item status state cid
            D=$(gh api graphql -f query='{ repository(owner:"'"$OWNER"'",name:"'"$REPO"'"){ issue(number:'"$n"'){ id state projectItems(first:10){ nodes{ id project{ id } fieldValueByName(name:"Status"){ ... on ProjectV2ItemFieldSingleSelectValue{ name } } } } } } }')
            state=$(echo "$D" | jq -r '.data.repository.issue.state')
            item=$(echo "$D" | jq -r '.data.repository.issue.projectItems.nodes[]|select(.project.id==env.PROJECT_ID)|.id' | head -1)
            status=$(echo "$D" | jq -r '.data.repository.issue.projectItems.nodes[]|select(.project.id==env.PROJECT_ID)|.fieldValueByName.name // ""' | head -1)
            if [ -z "$item" ]; then   # issue без item → добавить на доску
              cid=$(echo "$D" | jq -r '.data.repository.issue.id')
              item=$(gh api graphql -f query="mutation{ addProjectV2ItemById(input:{ projectId:\"$PROJECT_ID\" contentId:\"$cid\" }){ item{ id } } }" --jq '.data.addProjectV2ItemById.item.id')
              status=""
            fi
            if [ "$state" = "CLOSED" ] && [ "$status" != "Done" ]; then
              set_status "$item" "$(opt Done)"; echo "issue $n -> Done (closed)"
            elif [ "$state" = "OPEN" ] && { [ "$status" = "Done" ] || [ -z "$status" ]; }; then
              set_status "$item" "$(opt Backlog)"; echo "issue $n -> Backlog (open)"
            fi
          }
          if [ -n "${ISSUE:-}" ]; then reconcile "$ISSUE"
          else  # workflow_dispatch: полная сверка
            gh issue list -R "$OWNER/$REPO" --state all --limit 500 --json number --jq '.[].number' \
              | while read -r n; do reconcile "$n"; done
          fi
```

⚠️ **НАПОМНИ человеку создать repo-secret `KANBAN_PROJECT_TOKEN`** — classic PAT со scope
`project` (+ `repo`): Settings → Secrets and variables → Actions → New repository secret.
Без него workflow не работает.

### ШАГ 7 — Инициализируй `.claude/system/`

`sdc.md` — **НЕ трогать** (универсальный чек-лист). `postdeploy.sh` — не менять; для G9 ему
нужен `infra.metrics_url` в профиле — заполни, если мониторинг найден на ШАГ 2.

**budget.md** — заполни таблицу «Текущий учёт» результатами скана:

```bash
# микросервисы/модули — из topology.services профиля (ШАГ 3)
# external calls (HTTP/gRPC-клиенты к другим сервисам / третьим сторонам):
grep -rlE "WebClient|RestTemplate|RestClient|@FeignClient|@HttpExchange" \
  --include='*.java' --include='*.kt' . 2>/dev/null | grep -vE 'build/|/test/'
# очереди / topics (consumers + producers):
grep -rhoE '@(Kafka|Rabbit|Jms|Sqs)Listener\([^)]*\)|KafkaTemplate|RabbitTemplate' \
  --include='*.java' --include='*.kt' . 2>/dev/null | sort -u
# БД/схемы — из stack.data.databases + application*.yml
# cron / workers:
grep -rlE "@Scheduled|@EnableScheduling" --include='*.java' --include='*.kt' . 2>/dev/null
grep -rlE "kind:[[:space:]]*CronJob" --include='*.y*ml' . 2>/dev/null
```

**ownership-map.md** — заполни стартовое состояние (owner = модуль/сервис, где лежит артефакт):

- Таблицы БД: `CREATE TABLE` из Flyway-миграций (`**/src/main/resources/db/migration/*.sql`)
  или `createTable` из Liquibase changelog (по `stack.data.migration_tool`);
- Очереди/topics: producers и consumers из скана budget выше;
- API endpoints: `@RestController` + `@RequestMapping`/`@GetMapping`/… по модулям;
- Shared contracts: содержимое модуля `topology.shared_contracts` (если задан).

### ШАГ 8 — Инициализируй `.claude/memory/project-summary.md`

Сожми `ARCHITECTURE.md` / `README.md` (что есть) + результаты скана в **~500 токенов** по
секциям из шаблона самого файла: назначение системы, топология и зоны ответственности,
ключевые потоки данных, основные таблицы/агрегаты и владельцы, внешние интеграции,
нестандартные решения. Убери строку «Статус: не инициализирован».
`active-sprint.md` / `decisions.md` / `stories/` — не трогать (рабочие шаблоны).

### ШАГ 9 — CLAUDE.md проекта

Если `CLAUDE.md` НЕТ — создай. Если ЕСТЬ — **не перезаписывай**, только дополни недостающие
обязательные разделы. Значения НЕ дублировать — **ссылки на project-profile.md**:

```markdown
## Стек и команды
Источник правды — `.claude/project-profile.md`: стек — `stack.*`, топология сервисов —
`topology.services`, build/test/coverage — `commands.backend.*` и `commands.frontend[]`,
деплой/rollback — `commands.deploy.*`. Агенты берут команды ТОЛЬКО из профиля —
здесь они не дублируются.

## Структура проекта
{дерево корневых директорий, 1-2 уровня, с назначением каждого каталога}

## Конвенции
- Ветки: `feature/{N}-{slug}` от `github.default_branch`; `story/{M}-{slug}` от feature-ветки
- Коммиты: `feat(#{issue}): описание`
- Состояние задач — поля GitHub Project board из `.claude/board.env`
  (протокол: `.claude/agents/kanban-board-sync.md`; гейты: `.claude/agents/quality-gates.md`)
```

### ШАГ 10 — docs/ структура + ADR-001

```bash
mkdir -p docs/specs docs/arch docs/adr docs/test-cases
```

Создай `docs/adr/ADR-001-kanban-agent-system.md`, если не существует:

```markdown
# ADR-001: Kanban Agent System

**Status:** Accepted
**Date:** {YYYY-MM-DD}

## Context
Проект использует Claude Code с многоагентной Kanban-системой для автоматизированного
pipeline разработки: от идеи до production-деплоя, с quality gates на каждом переходе.

## Decision
Принят agent-per-status Kanban-флоу (9 статусов) с гейтами G1–G9. Роли и команды —
все файлы из `.claude/agents/` и `.claude/commands/` (источник правды — сами каталоги):
- Team Leads: analysis-lead, dev-lead, qa-lead, ops-lead
- ICs: analyst, architect, developer, devops, security-reviewer, java-reviewer,
  frontend-reviewer, test-case-writer, e2e-tester, integration-tester, doc-sync
- Протоколы: quality-gates, kanban-board-sync, dependency-resolver

## Stages (agent-per-status)
1. Backlog → заявка (/feature)
2. Analysis → analyst + architect (/analyze)
3. Ready for Dev → буфер (dev-lead берёт)
4. In Development → developer
5. Code Review → security-reviewer + java-reviewer + frontend-reviewer (по delta)
6. Testing → test-case-writer (/test)
7. Ready to Deploy → буфер + prod-approve (ops-lead)
8. Deploy → devops
9. Done

## Consequences
- Все фичи проходят структурированный pipeline; evidence-driven гейты на переходах
- Состояние задач — поля GitHub Project board из `.claude/board.env` (лейблы упразднены)
- WIP-лимит `quality.wip_limit` (default 5) предотвращает перегрузку
- Circuit breaker: `quality.fix_loop_max` (default 3) циклов исправлений → эскалация человеку
- Параллелизм через /swarm
```

### ШАГ 11 — Валидация + следующие шаги

Проверь чек-листом (каждый пункт — реальной командой, не «по памяти»):

- [ ] `.claude/project-profile.md` — `initialized: true`, `updated` = сегодня, `commands.*` — реальные команды
- [ ] `.claude/board.env` — OWNER/REPO/PROJECT_NUMBER/PROJECT_ID заполнены; `gh project view "$PROJECT_NUMBER" --owner "$OWNER"` отвечает
- [ ] Поля доски — все 11 (Status, Type, Priority, Size, Component, Security, JavaReview, FrontendReview, QA, Deploy, Coverage): `gh project field-list "$PROJECT_NUMBER" --owner "$OWNER"`
- [ ] `.github/workflows/kanban-reconcile.yml` — создан, значения совпадают с board.env; человек предупреждён про секрет `KANBAN_PROJECT_TOKEN`
- [ ] `.claude/system/budget.md` — таблица «Текущий учёт» заполнена
- [ ] `.claude/system/ownership-map.md` — стартовые таблицы заполнены
- [ ] `.claude/memory/project-summary.md` — заполнен (~500 токенов)
- [ ] `CLAUDE.md` — обязательные разделы на месте (ссылки на профиль, не копии значений)
- [ ] `docs/specs|arch|adr|test-cases` — созданы; ADR-001 на месте
- [ ] `.claude/agents/` и `.claude/commands/` — все файлы системы на месте (`ls`; при расхождении — `/refresh-agents`)
- [ ] `.claude/settings.json` — существует; если нет — создай минимальный (permissions.allow: Bash, Read, Write, Edit, Glob, Grep, Agent, `mcp__github__*`; deny: разрушительные команды)
- [ ] Существующие issues без Status на доске: `kb_dump | jq '[.[]|select(.status==null)]|length'` — двинь их в Backlog через `kanban_set` (хелперы из kanban-board-sync.md)

## Финальный отчёт

```
PROJECT INITIALIZED
{date}

Repository: {owner}/{repo} (default branch: {main_branch})
Board:      GitHub Project board из .claude/board.env (Project {N})
Stack:      {однострочная выжимка: build tool, backend framework, frontend-приложения, БД/кэш/брокер, k8s, CI}
Topology:   {monolith | modular-monolith | microservices; N сервисов}

Артефакты:
  .claude/project-profile.md            — initialized: true ✓
  .claude/board.env                     — ✓
  Поля доски                            — 11/11 ✓
  .github/workflows/kanban-reconcile.yml — ✓  ⚠️ создай секрет KANBAN_PROJECT_TOKEN
  .claude/system/budget.md              — «Текущий учёт» заполнен ✓
  .claude/system/ownership-map.md       — стартовое состояние ✓
  .claude/memory/project-summary.md     — ✓
  CLAUDE.md                             — {создан | дополнен | уже был полон}
  docs/{specs,arch,adr,test-cases}/ + ADR-001 — ✓

Следующие шаги:
  /feature <описание>  — создать первый Feature Request
  /kanban <описание>   — полный pipeline (идея → деплой)
  /sprint add #N       — утвердить задачу в текущий спринт (оркестратор работает по спринту)
  /orchestrate         — автопилот: петля крутит текущий спринт до готовности
  /stage off deploy    — поставить стадию на паузу (экономия токенов; задачи ждут)
  /board               — доска текущего спринта (/board backlog — интейк)
  /analyze, /develop, /test, /deploy — отдельные этапы
  /orchestrate once|swarm|<колонка> (алиасы /sweep, /swarm, /pick) — режимы оркестратора
```
