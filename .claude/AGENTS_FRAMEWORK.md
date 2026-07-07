# Agents Framework

Мультиагентная система разработки на базе Claude Code. Иерархия Team Leads + рабочих агентов, Kanban-процесс **agent-per-status** (каждый статус доски = активный агент) с 8 Quality Gates (+ post-deploy G9), Security Review, DAG-зависимостями и автосинхронизацией GitHub Project board.

**Стек-агностична.** Система работает на любом проекте класса Java/микросервисы/Kubernetes/high-load с Angular и/или React фронтендом. Всё проект-специфичное (build/test/deploy команды, топология сервисов, порты, пороги качества) живёт в **`.claude/project-profile.md`** и **`.claude/board.env`** — их заполняет `/init` авто-детектом. Агенты не хардкодят команды — читают профиль.

---

## Как это работает (в двух минутах)

**Идея.** Команда AI-агентов разной специализации работает над фичей по Kanban-доске GitHub Issues. Человек ставит задачу — агенты сами проходят все этапы: анализ → проектирование → разработка → ревью → тесты → деплой. На каждом переходе между колонками срабатывает Quality Gate — чек-лист с реальными доказательствами (вывод команд, метрики), а не «всё ок».

**Роли.** Два уровня:
- **Team Leads** (analysis-lead, dev-lead, qa-lead, ops-lead) — координируют свою фазу, валидируют output, держат WIP-лимиты, делают Quality Gate.
- **Рабочие агенты** (analyst, architect, developer, security-reviewer, java-reviewer, frontend-reviewer, test-case-writer, devops, e2e-tester) — выполняют конкретную работу.

**Поток.** Issue идёт по колонкам: `Backlog → Analysis → Ready for Dev → In Development → Code Review → Testing → Ready to Deploy → Deploy → Done`. **Каждый статус = активный агент** (agent-per-status) — доска показывает, кто именно сейчас держит задачу; два статуса держат группу агентов (Analysis: analyst+architect; Code Review: security + java + frontend reviewers — по delta). Каждое перетаскивание = Quality Gate (G1..G8). Через 72 часа после прод-деплоя — G9: cron-скрипт сверяет реальные метрики с тем, что обещали в spec.

**Управление человеком.** Через slash-команды:
- `/feature <описание>` — создать Feature Request
- `/analyze #N` — декомпозировать на User Stories + написать spec + arch doc
- `/develop #N` — реализовать story
- `/test #N` — написать TC-документацию
- `/deploy staging` / `/deploy production` — задеплоить
- `/kanban <описание>` — полный пайплайн одной командой (всё выше подряд)
- `/board` — посмотреть состояние доски, WIP, блокировки

**Память и контекст.** Чтобы не жечь токены — четыре слоя shared-памяти:
0. `.claude/project-profile.md` — стек, топология сервисов, канонические команды (build/test/deploy), пороги качества. Читается ЛЮБЫМ агентом первым.
1. `.claude/memory/` — `story-N.md` накапливается по pipeline (📋🏗️💻🔒☕✅), каждый агент дописывает свой раздел вместо перечитывания spec+arch+ARCHITECTURE.
2. `.claude/system/` — System Design Discipline (TRIZ-слой): один файл-чеклист `sdc.md` с 8 системными вопросами (ownership, идемпотентность, транзакции, откат миграции, таймауты, blast radius, прод-AC, anti-scope) заполняется в spec и сверяется на gates. Без отдельных «системных» агентов.
3. `.claude/agents/quality-gates.md` + `dependency-resolver.md` + `kanban-board-sync.md` — shared-протоколы, читаются Team Leads напрямую.

**Качество.** Защита от «AI сгенерировал кучу кода, а система плохая» — встроена:
- analyst заполняет 8 SDC-слотов в spec (ownership, идемпотентность, …) перед декомпозицией.
- architect детализирует слоты в arch doc (rollback SQL, timeouts table, ADR при threshold из `budget.md`).
- developer пишет код и unit-тесты (coverage ≥ 95%).
- security-reviewer + java-reviewer (включая SDC-Conformance чек) — параллельно в статусе Code Review (гейт выхода G5).
- ops-lead на G8 проверяет rollback rehearsal на staging + kill switch.
- `postdeploy.sh` через 72ч сверяет реальный latency/error rate с обещаниями из spec.

**Что НЕ происходит автоматически.** Production-деплой требует явного `APPROVE PRODUCTION DEPLOY` от человека в комментарии к issue. До этого ops-lead ждёт.

---

## Архитектура

### Иерархия агентов

```
                        ┌─────────────────┐
                        │    ЧЕЛОВЕК      │
                        │  (PM / Owner)   │
                        └────────┬────────┘
                                 │  /kanban  /swarm  /sweep  /feature  ...
                                 ▼
                  ┌──────────────────────────────────┐
                  │        Claude Code (оркестр)      │
                  │  Парсит команды → запускает       │
                  │  Team Leads.                      │
                  │  Shared: quality-gates,           │
                  │  dependency-resolver, board-sync  │
                  └──┬──────────┬──────────┬──────┬──┘
                     │          │          │      │
          ┌──────────┘ ┌────────┘  ┌───────┘  ┌──┘
          ▼            ▼           ▼           ▼
  ┌──────────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐
  │analysis-lead │ │ dev-lead │ │ qa-lead │ │ ops-lead │
  │  [G1,G2]     │ │[G3,G4,G5]│ │  [G6]   │ │ [G7,G8]  │
  │  WIP: 5      │ │  WIP: 5  │ │ WIP: 5  │ │          │
  └──┬───────┬───┘ └────┬─────┘ └───┬────┘ └────┬─────┘
     │       │          │           │             │
     ▼       ▼          ▼           ▼             ▼
 analyst architect  developer  test-case-writer devops
 (sonnet) (opus)    (opus)        (sonnet)     (sonnet)
                   [worktree]
                        │
                   [статус Code Review — параллельно, по delta]
                   ├── security-reviewer  (sonnet) — всегда
                   ├── java-reviewer      (sonnet) — если backend-delta
                   └── frontend-reviewer  (sonnet) — если frontend-delta (Angular/React)
                   ↑ запускает dev-lead в статусе Code Review (после G4, гейт выхода G5)

  Отдельный поток (через /e2e — ручной запуск):
  e2e-tester (opus) → e2e-tests/
```

### Два уровня

| Уровень | Агенты | Роль |
|---------|--------|------|
| **Координация** | analysis-lead, dev-lead, qa-lead, ops-lead | Управляют рабочими агентами, валидируют output, следят за WIP, enforc'ят Quality Gates |
| **Исполнение** | analyst, architect, developer, security-reviewer, java-reviewer, test-case-writer, e2e-tester, devops | Автономно выполняют задачи в своей компетенции |

**Shared-протоколы** — `quality-gates.md`, `dependency-resolver.md`, `kanban-board-sync.md` — читаются Team Leads напрямую, не являются агентами (~60K токенов экономии).

---

## Каталог агентов

### Team Leads (координация, модель: sonnet)

| Агент | Команда | Kanban-переход | Gates |
|-------|---------|----------------|-------|
| **analysis-lead** | analyst + architect | Backlog → Analysis → Ready for Dev | G1, G2 |
| **dev-lead** | developer(s) + security-reviewer + java-reviewer + frontend-reviewer + doc-sync | Ready for Dev → In Development → Code Review → Testing | G3, G4, G5 |
| **qa-lead** | test-case-writer(s) | Testing → Ready to Deploy | G6 |
| **ops-lead** | devops | Ready to Deploy → Deploy → Done | G7, G8 |

### Рабочие агенты (исполнение)

| Агент | Модель | Задача | Isolation |
|-------|--------|--------|-----------|
| **analyst** | sonnet | Декомпозиция фич → User Stories + спецификации. SD-1..SD-5 правила. Status на доске. | — |
| **architect** | **opus** | ADR, ERD, API contracts, code stubs. Высокое качество архитектурных решений. | — |
| **developer** | **opus** | Backend + Frontend (Angular/React — из профиля) по spec/arch. Unit-тесты (coverage ≥ quality.unit_coverage_min, default 95%). Build-verification. | **worktree** |
| **security-reviewer** | sonnet | OWASP Top 10, AI-specific (prompt injection, RAG), JWT/RBAC, k8s-секреты. Delta-scope. Всегда. | — |
| **java-reviewer** | sonnet | Java Senior + System Design. Architecture, JPA, Modern Java, Scalability, микросервисы, high-load. Если backend-delta. | — |
| **frontend-reviewer** | sonnet | Angular/React ревью: архитектура, типизация, state, perf, a11y. Если frontend-delta. | — |
| **test-case-writer** | sonnet | TC-документация из specs/arch. Cross-reference sync. Обновляет traceability-tc.md. | — |
| **e2e-tester** | **opus** | Java Playwright + JUnit 5 + Page Object. Из TC-docs → E2E тесты в `e2e-tests/`. Только `/e2e` (ручной). | — |
| **devops** | sonnet | Docker build, CI/CD pipeline, staging/production deploy, health checks, monitoring. | — |
| **doc-sync** | sonnet | Traceability matrix. Spec↔code consistency. Запускается dev-lead после каждой разработки. | — |

> **Модель-стратегия:** opus — где максимальное качество кода/дизайна (architect, developer, e2e-tester). sonnet — где скорость важнее (координация, review, тесты, deploy).

---

## Kanban Flow

### Колонки — agent-per-status

**Ключевой принцип:** каждый Status на доске = конкретный агент, который сейчас владеет
задачей. Задача в момент времени находится ровно в одном статусе → ровно один агент (или
одна пара) её держит. Это делает доску **синхронной и последовательной**: следующий агент
берёт задачу, только когда предыдущий передал её через Quality Gate. «Ожидающие» статусы
(Ready for Dev, Ready to Deploy) — буферы между Team Lead'ами; в них активного агента нет.

```
Backlog → Analysis → Ready for Dev → In Development → Code Review → Testing → Ready to Deploy → Deploy → Done
        G1        G2               G3               G4           G5        G6                G7       G8
```

| Status | Активный агент(ы) | Team Lead | Что здесь |
|--------|-------------------|-----------|-----------|
| **Backlog** | — (заявка) | analysis-lead | Новые фичи, баги, идеи |
| **Analysis** | analyst + architect `[2]` | analysis-lead | Декомпозиция + проектирование (spec + arch) |
| **Ready for Dev** | — (буфер) | dev-lead берёт | Stories с spec + arch doc, ждут разработки |
| **In Development** | developer | dev-lead | Реализация backend/frontend + unit-тесты |
| **Code Review** | security + java + frontend reviewers `[2..3]` | dev-lead | OWASP/JWT/RBAC + Java/System Design/SDC + Angular/React, параллельно по delta |
| **Testing** | test-case-writer | qa-lead | TC docs + верификация unit coverage |
| **Ready to Deploy** | — (буфер, prod-approve) | ops-lead | QA пройден, ждёт деплоя (prod — ждёт `APPROVE`) |
| **Deploy** | devops | ops-lead | Build + деплой + health/smoke/rollback rehearsal |
| **Done** | — (терминал) | — | Задеплоено, issue закрыт |

`[2]`/`[2..3]` — статус, где допускается группа агентов: они работают **параллельно** над одной
задачей и обязаны все пройти гейт выхода (Analysis → G2; Code Review → G5). В Code Review
состав группы зависит от delta: security-reviewer всегда, java-reviewer при backend-изменениях,
frontend-reviewer при frontend-изменениях. Остальные активные статусы — строго один агент.

Идентичность колонки — это значение поля **Status** на Project board. Отдельных меток для
стадии нет; смена стадии = передача задачи следующему агенту через `kanban_set`.

### Смена стадии (ОБЯЗАТЕЛЬНО)

Единственный источник правды о стадии задачи — поле **Status** на Project board. Смена стадии — одна операция:

```
kanban_set N "<Status>"   # выставляет Status на доске; сама close при Done / reopen иначе
```

**Порядок: СНАЧАЛА выставить Status на доске через `kanban_set` → ПОТОМ начинать работу.**

Детерминированный backstop — `.github/workflows/kanban-reconcile.yml` — приводит состояние open/closed ↔ Status в порядок. Он дополняет `kanban_set`, а не заменяет его.

Хелперы (`kanban_set`, `kanban_query`) и полный протокол: `.claude/agents/kanban-board-sync.md`.

### Feature-карточка (родительский issue)

По всем 9 колонкам едут **stories**. Feature-карточка (Type=feature) отражает агрегатное
состояние своих stories и проходит только 5 статусов. Кто и когда её двигает:

| Событие | Status фичи | Кто двигает |
|---------|-------------|-------------|
| Фича создана (`/feature`) | Backlog | analyst |
| `/analyze` стартовал (G1) | Analysis | analysis-lead |
| G2 пройден — все stories в Ready for Dev | Ready for Dev | analysis-lead |
| Первая story ушла в In Development (G3) | In Development | dev-lead |
| ВСЕ stories фичи Done (G8) | Done (issue закрывается) | ops-lead |

Между «первая story в работе» и «все stories Done» фича стоит **In Development** — сколько бы
её stories ни находились в Code Review/Testing/Deploy и сколько бы ни было уже Done. Частично
реализованная фича (часть stories Done, остальные в Backlog) — тоже In Development: это маркер
«фича в работе», а не стадия конкретной story. Фича НЕ может быть в Backlog, если хотя бы одна
её story уже прошла дальше.

---

## Quality Gates

Обязательная проверка при каждом переходе. Полный протокол: `.claude/agents/quality-gates.md` (единый источник в репозитории).

| Gate | Переход | Enforcer | Ключевые проверки |
|------|---------|----------|-------------------|
| **G1** | Backlog → Analysis | analysis-lead | Business value, AC, дубликаты, тип, приоритет |
| **G2** | Analysis → Ready for Dev | analysis-lead | Spec (FR+NFR+Given/When/Then), SD-1..SD-5, **SDC: 8 слотов заполнены/N/A**, arch doc, INVEST, budget-threshold→ADR |
| **G3** | Ready for Dev → In Development | dev-lead | **Тесты baseline OK** (`commands.backend.test` из профиля), AC testable (один G/W/T), deps resolved, WIP < quality.wip_limit, feature-ветка |
| **G4** | In Development → Code Review | dev-lead | **Тесты SUCCESS** (`commands.backend.test` / `commands.frontend[].test`), story-ветка смёрджена в feature, handoff+coverage, чистый `git status`. Гейт «код готов к ревью» |
| **G5** | Code Review → Testing | dev-lead | `Security=passed` + `JavaReview=passed/warning` (если backend-delta) + `FrontendReview=passed/warning` (если frontend-delta). Включает SDC Conformance. Все применимые reviewer'ы прошли |
| **G6** | Testing → Ready to Deploy | qa-lead | Coverage ≥ quality.unit_coverage_min (default 95%; hotfix: ≥ quality.hotfix_coverage_min, default 50%), AC верифицированы тестами, TC docs созданы, поле `Security=passed` ОБЯЗАТЕЛЬНО |
| **G7** | Ready to Deploy → Deploy | ops-lead | Pre-flight: `QA=passed` + `Security=passed` + build/tests green. Prod → человек постит `APPROVE PRODUCTION DEPLOY` |
| **G8** | Deploy → Done | ops-lead | Tests green, health OK (`topology.services[].health` + `kubectl rollout status` для k8s), smoke OK, logs clean, поле `Deploy` выставлено, **rollback rehearsal на staging (`commands.deploy.rollback`) + kill switch проверен** |
| **G9** | через 72ч после prod | `postdeploy.sh` (cron, без LLM) | Реальные метрики vs PROD AC из SDC #7. Расхождение → автоматический issue с полем `Type=tech-debt` |

### Verdicts

| Verdict | Значение | Действие |
|---------|----------|----------|
| **PASS** ✅ | Все проверки выполнены | Переход в следующую колонку |
| **NEEDS WORK** ⚠️ | Мелкие проблемы | Fix inline, повтори gate |
| **BLOCKED** 🚫 | Критическая проблема | СТОП, issue остаётся в текущей колонке |

Каждый gate оставляет **Quality Gate Report** comment в issue с реальным выводом команд (не утверждениями).

---

## System Design Discipline (ТРИЗ-слой)

Системные вопросы — ownership, идемпотентность, граница транзакции, миграция forward+backward, таймауты, blast radius, прод-AC, anti-scope — встроены не в новых агентов, а в **один артефакт-посредник** и точечные правки промптов существующих агентов. Никаких новых ролей и моделей.

### Принцип

Вместо «вертикального» pipeline с reviewer'ами уровня системы — **shared-чеклист**, который заполняется в spec, детализируется в arch doc, верифицируется java-reviewer'ом в коде и проверяется cron'ом в проде. Один источник правды, нулевое дублирование, ноль LLM-токенов на пост-фактум-проверку.

### Артефакты

```
.claude/system/
├── sdc.md            # System Design Checklist — 8 обязательных слотов в spec
├── budget.md         # Architectural Budget — cumulative complexity + threshold→ADR
├── ownership-map.md  # Карта владения: таблица/exchange/endpoint → owner module/service
└── postdeploy.sh     # G9 cron (bash + jq + curl + gh) — без LLM
```

### 8 слотов SDC

| # | Слот | Закрывает вопрос |
|---|------|------------------|
| 1 | OWNERSHIP | Кто владеет данными, кто consumers, tenant-scope |
| 2 | IDEMPOTENCY | Что при повторной доставке / повторном вызове |
| 3 | CONSISTENCY | Граница транзакции, паттерн (saga/outbox/eventual), инвариант |
| 4 | MIGRATION | Forward + backward (rollback или forward-only с обоснованием) |
| 5 | RESILIENCE | Таймауты, ретраи, circuit breaker для каждого external call |
| 6 | BLAST RADIUS | Затронутые DTO/Event + consumers с grep evidence + breaking/non-breaking |
| 7 | PROD AC | Latency p95/p99, error rate, throughput, idempotency assertion, kill switch |
| 8 | NOT-DOING | Что СОЗНАТЕЛЬНО не делаем и почему (anti-scope) |

Полное описание: `.claude/system/sdc.md`.

### Кто заполняет / проверяет (без новых ролей)

| Этап | Агент | Что делает |
|------|-------|------------|
| `/feature` + `/analyze` | **analyst** | Читает `sdc.md`, `budget.md`, `ownership-map.md`. Заполняет SDC-блок в spec. Обновляет `ownership-map.md` и `budget.md` при появлении нового ресурса. |
| `/analyze` | **architect** | Детализирует SDC слоты в arch doc (rollback SQL, timeouts table, sequence для error path, ADR при threshold). Запрет нового модуля/слоя/external без ADR. |
| `/develop` | **developer** | Реализует код согласно SDC. В handoff фиксирует факт реализации (Migration file, Idempotency key location, Circuit breaker name). |
| `/develop` (Code Review, G5) | **java-reviewer** | Чек-лист **SDC-01..SDC-07**: сверка кода со слотами spec. Расхождение HIGH → `kb_set N JavaReview failed`. |
| `/test` | **qa-lead** | TC docs покрывают слот #2 (idempotency tests), слот #5 (timeout/retry tests), слот #8 (NOT-doing не реализовано). |
| `/deploy production` (G8) | **ops-lead** | Rollback rehearsal на staging (слот #4), kill switch проверен (слот #7). |
| +72ч после prod (G9) | **`postdeploy.sh`** (cron, без LLM) | Реальные метрики Prometheus vs PROD AC (слот #7). Расхождение → авто-issue с полем `Type=tech-debt`. |

### Когда SDC обязателен (Local Quality — TRIZ принцип 3)

- `Type=feature` — всегда
- `Size=l`/`Size=xl` — всегда
- Изменения в shared-contracts модуле (DTO/Events; `topology.shared_contracts` из профиля) — всегда
- Новая миграция — всегда (слоты 4 + 7)
- Новый external call — всегда (слот 5)
- Новая queue/exchange/topic — всегда
- Новый микросервис / Deployment в k8s — всегда (все слоты)

**НЕ обязателен:** `Size=xs`/`Size=s` локально в одном модуле, без новых таблиц/очередей/external. В spec одна строка: `SDC: N/A — локальный рефакторинг`.

### Стоимость

- Токены: ~+800 на story (расширенный промпт analyst/architect, +1 чек-лист java-reviewer). Альтернатива «полноценный system-steward agent» = +40-60K токенов на story.
- Сложность: 4 файла в `.claude/system/`, +3 точечные правки промптов, +1 пункт в G2, +2 пункта в G6, +1 cron G9. Никаких новых агентов, моделей, MCP-инструментов.
- Maintenance: один `sdc.md` — единая точка правды.

---

## Детальные флоу агентов

### Analysis Flow (`/analyze #N`)

```
analysis-lead
  │
  ├── G1: Backlog → Analysis
  │     ✓ Business value, AC, дубликаты, тип, приоритет
  │
  ├── [ПАРАЛЛЕЛЬНО]
  │     ├── analyst
  │     │     ├── Декомпозиция фичи → User Stories
  │     │     ├── Каждая story: ровно ОДИН Given/When/Then (SD-1)
  │     │     ├── Запрет: Size=xl, " и ", " and ", "and also" (SD-3, SD-5)
  │     │     └── docs/specs/feature-{N}-{name}.md
  │     │
  │     └── architect
  │           ├── docs/arch/feature-{N}-{name}.md
  │           ├── ERD, API contracts, ADR
  │           └── Code stubs по модулям
  │
  ├── G2: analysis → ready-for-dev
  │     ✓ Spec полный, stories INVEST, arch doc создан, SD-1..SD-5
  │
  └── doc-sync: обновить traceability.md
```

### Development Flow (`/develop #N`)

```
dev-lead
  │
  ├── Dependency Check: blockers resolved?
  ├── WIP Check: < 5 in-development?
  ├── Conflict Detection: git diff origin/feature/{featureN}...story/{storyN}
  │
  ├── G3: Ready for Dev → In Development
  │     ✓ Build OK, AC testable, deps resolved, WIP OK
  │     ✓ feature-ветка `feature/{featureN}-{slug}` существует (создать если нет)
  │
  ├── developer (isolation: worktree)
  │     ├── GIT GITFLOW — ОБЯЗАТЕЛЬНО:
  │     │     1. Убедиться что ветка `feature/{featureN}-{slug}` существует
  │     │     2. Создать story-ветку от feature: `git checkout -b story/{storyN}-{slug} feature/{featureN}-{slug}`
  │     │     3. Вся работа ведётся в `story/{storyN}-{slug}`
  │     │     4. По завершению: `git checkout feature/{featureN}-{slug} && git merge --no-ff story/{storyN}-{slug}`
  │     │     5. **ЗАПРЕЩЕНО** пушить story-ветку в default branch напрямую
  │     ├── Context: project-profile + README/CLAUDE + story-{N}.md (📋+🏗️) при наличии
  │     ├── Implement: Data Layer → Service → API → Frontend (Angular/React из профиля)
  │     ├── Unit tests (coverage ≥ quality.unit_coverage_min новых файлов)
  │     ├── **Обязательно:** тесты успешны (commands.backend.test / commands.frontend[].test) + handoff с фрагментом вывода
  │     └── Commit + merge story→feature. НЕ меняет Status сам (остаётся In Development)
  │
  ├── G4: In Development → Code Review  (код готов к ревью)
  │     ✓ Тесты SUCCESS (команды из профиля), Build+lint OK, нет orphaned файлов, чистый git status
  │     ✓ story-ветка смёрджена в feature-ветку
  │     ✓ Handoff `.claude/handoffs/story-{N}-dev.md` создан с реальным coverage %
  │
  ├── kanban_set N "Code Review"
  │
  ├── [статус Code Review — reviewers ПАРАЛЛЕЛЬНО, состав по delta]
  │     ├── security-reviewer (всегда)
  │     │     ├── Scope: delta (изменённые файлы из developer comment + git diff)
  │     │     ├── OWASP Top 10, AI-specific, JWT/RBAC, k8s-секреты
  │     │     ├── PASS → kb_set N Security passed
  │     │     └── FAIL → kb_set N Security failed → developer исправляет (max quality.fix_loop_max циклов)
  │     │
  │     ├── java-reviewer (если backend-delta: *.java/*.kt)
  │     │     ├── Architecture, JPA, Modern Java, Scalability, микросервисы, high-load, System Design + SDC
  │     │     ├── PASS/WARNING → kb_set N JavaReview passed / warning
  │     │     └── FAIL (CRITICAL/HIGH) → kb_set N JavaReview failed → developer исправляет
  │     │     ☛ JavaReview=warning НЕ блокирует Testing (tech-debt)
  │     │
  │     └── frontend-reviewer (если frontend-delta: файлы приложений из stack.frontend)
  │           ├── Angular/React архитектура, типизация, state, perf, a11y, тесты
  │           ├── PASS/WARNING → kb_set N FrontendReview passed / warning
  │           └── FAIL (CRITICAL/HIGH) → kb_set N FrontendReview failed → developer исправляет
  │           ☛ FrontendReview=warning НЕ блокирует Testing (tech-debt)
  │
  ├── G5: Code Review → Testing
  │     ✓ Security=passed + JavaReview=passed/warning (если применим) + FrontendReview=passed/warning (если применим)
  │     └── kanban_set N "Testing"
  │
  └── doc-sync: обновить traceability matrix
```

### Testing Flow (`/test #N`)

```
qa-lead
  │
  ├── Pre-flight: build OK? developer handoff создан?
  ├── Dependency Check: blockers resolved?
  ├── Field CHECK (kb_get N …):
  │     └── Security ≠ passed → BLOCKED: запросить /develop
  │     └── JavaReview = failed → BLOCKED: запросить /develop
  │
  ├── test-case-writer (sonnet)
  │     ├── Читает spec + arch + issue AC + handoff
  │     ├── Верифицирует unit coverage % из handoff (≥ quality.unit_coverage_min)
  │     ├── docs/test-cases/feature-{N}-{name}.md
  │     ├── Для каждого AC: happy path + error case + RBAC test
  │     ├── Cross-reference sync: обновить Related TCs
  │     └── Обновить docs/test-cases/traceability-tc.md
  │
  ├── G6: Testing → Ready to Deploy
  │     ✓ Coverage ≥ quality.unit_coverage_min подтверждён из handoff (hotfix: ≥ quality.hotfix_coverage_min)
  │     ✓ TC docs созданы, AC верифицированы
  │     ✓ Security=passed + JavaReview/FrontendReview=passed/warning (по применимости) ОБЯЗАТЕЛЬНЫ (выставлены на G5)
  │     ✗ BLOCKED если применимое поле не выставлено или =failed
  │
  ├── PASS → kanban_set N "Ready to Deploy" + kb_set N QA passed
  └── FAIL → kanban_set N "In Development" + kb_set N QA failed
```

### Deploy Flow (`/deploy staging`)

```
ops-lead
  │
  ├── G7 Pre-flight: Ready to Deploy → Deploy
  │     ✓ Status=Ready to Deploy + QA=passed + Security=passed
  │     ✓ Build/tests проходят
  │     ✓ Production: человек постил `APPROVE PRODUCTION DEPLOY`
  │     ✗ СТОП если любой check fails / нет prod-approve
  │     └── kanban_set N "Deploy"
  │
  ├── devops (sonnet) — в статусе Deploy
  │     ├── Pre-deploy: тесты + build (команды из профиля)
  │     ├── Docker build / artifact
  │     ├── Deploy: commands.deploy.staging из профиля (helm/kustomize/kubectl или compose)
  │     ├── k8s: kubectl rollout status по каждому затронутому сервису
  │     ├── Health check (topology.services[].health)
  │     ├── Smoke test (commands.smoke.staging)
  │     └── Logs check (kubectl logs --since=60s / docker logs — нет ERROR/WARN)
  │
  ├── G8 Post-deploy: Deploy → Done
  │     ✓ Health OK, Smoke OK, Logs clean, rollback rehearsal (commands.deploy.rollback) + kill switch
  │     ✗ Health FAIL → НЕМЕДЛЕННЫЙ ROLLBACK (BLOCKED)
  │     └── kb_set N Deploy staging → kanban_set N "Done" (issue закрывается автоматически)
  │
  └── Все stories фичи done → закрыть parent feature issue

  Production (перед G7):
  ├── ops-lead готовит Production Checklist + rollback команду в comment
  ├── Пишет: "Awaiting approval. Post `APPROVE PRODUCTION DEPLOY` to proceed."
  ├── ЖДЁТ человека (не двигает в Deploy без комментария)
  └── После `APPROVE PRODUCTION DEPLOY` → G7 → Deploy → devops для prod
```

### Hotfix Flow

Hotfix пропускает G1 и G2 (analysis phase). Входит напрямую в G3.

```
Условия: Type=hotfix + Priority=critical + Status=Ready for Dev (MANAGER выставил вручную через kanban_set + kb_meta)

G3 (dev-lead) → developer реализует
  → G4 (In Development → Code Review)
  → G5 (Code Review → Testing): security-reviewer ОБЯЗАТЕЛЕН + java/frontend reviewers по delta
       (coverage threshold снижен, но security review — нет)
  → G6 (qa-lead, coverage ≥ quality.hotfix_coverage_min, default 50%)
  → G7 → G8 (ops-lead: Ready to Deploy → Deploy → Done)
```

### E2E Flow (`/e2e #N`)

```
Отдельный поток — не блокирует деплой stories.

qa-lead (или прямой вызов)
  → e2e-tester (opus)
        ├── Читает docs/test-cases/feature-{N}-{name}.md
        ├── Создаёт/обновляет Page Objects в e2e-tests/
        ├── Генерирует E2E Test-классы (Java, Playwright, JUnit 5)
        ├── Только [data-testid='*'] селекторы
        ├── Critical + High TCs автоматизируются обязательно
        └── Обновляет TC traceability (E2E Automated: Yes)
```

---

## Правила декомпозиции (SD-1..SD-5)

Каждая User Story обязана следовать этим правилам. Проверяются на G2.

| Правило | Суть |
|---------|------|
| **SD-1** | Ровно ОДИН Given/When/Then блок. Не больше одного сценария. |
| **SD-2** | INVEST: Independent, Negotiable, Valuable, Estimable, Small, Testable |
| **SD-3** | Максимум 3 рабочих дня. `Size=xl` ЗАПРЕЩЁН для stories. |
| **SD-4** | Обязательный шаблон: User Story + один G/W/T + Вне Scope + Technical Notes |
| **SD-5** | Запрещённые паттерны в title: ` и `, ` and `. В AC: "and also", два Given-блока. |

---

## DAG-зависимости

Синтаксис в body issue:

```
Blocked by: #10, #12
Depends on: #10
Requires: #10, #12, #15
```

| Состояние | Действие |
|-----------|----------|
| Blocker closed / Status=Done | Не блокирует — можно обрабатывать |
| Blocker open и не done | BLOCKED — skip, не запускай агента |
| Circular dependency | Manual intervention — нельзя авторазрешить |
| Depth > 10 уровней | BLOCKED — предупреди человека |

Интеграция:
- **analyst** добавляет `Blocked by: #N` при создании зависимых stories
- **dev-lead** и **qa-lead** — dependency check перед запуском агентов (Step 2.5)
- **`/board`** — визуализация заблокированных issues

---

## Board Field System

**Всё состояние задачи живёт в полях GitHub Project board (идентичность — `.claude/board.env`),
а не в лейблах.** Лейблы как механизм синхронизации **упразднены полностью** (все семейства
мигрированы в поля). Причина: дублирование состояния в трёх местах (issue open/closed + метка +
доска) давало хронический рассинхрон. Теперь единственный писатель состояния — хелперы
`kb_set` / `kanban_set` (ключ = board item node-id). Протокол и хелперы: `.claude/agents/kanban-board-sync.md`.

### Поля доски (заменяют лейблы)

| Поле | Тип | Значения | Заменяло лейбл | Пишет |
|------|-----|----------|----------------|-------|
| **Status** | single-select | 9 стадий (agent-per-status) | стадию | Team Lead (`kanban_set`) |
| **Type** | single-select | feature, epic, story, bug, tech-debt, hotfix, spike | `type:*` | analyst |
| **Priority** | single-select | critical, high, medium, low | `priority:*` | analyst |
| **Size** | single-select | xs, s, m, l, xl | `size:*` | analyst |
| **Component** | text (CSV) | backend,frontend,ai,infra,docs,qa | `component:*` | analyst |
| **Security** | single-select | pending, passed, failed | `security:*` | **security-reviewer** |
| **JavaReview** | single-select | pending, passed, warning, failed | `java-review:*` | **java-reviewer** |
| **FrontendReview** | single-select | pending, passed, warning, failed | — (новое) | **frontend-reviewer** |
| **QA** | single-select | pending, in-progress, passed, failed | `qa:*` | qa-lead |
| **Deploy** | single-select | none, staging, production | `deployed:*` | devops |
| **Coverage** | number | % покрытия | (текст в `qa:passed`) | qa-lead |

Установка: `kb_meta N type=story priority=high size=m component=backend,infra`,
`kb_set N Security passed`, `kb_num N Coverage 96`. Чтение: `kb_get N Security`.

> **Single-writer на поле-семейство:** `Security` пишет ТОЛЬКО security-reviewer, `JavaReview`
> — ТОЛЬКО java-reviewer, `FrontendReview` — ТОЛЬКО frontend-reviewer (все через dev-lead в
> статусе Code Review). qa-lead/ops-lead эти поля ТОЛЬКО читают (`kb_get`) — никогда не пишут.
> Это устраняет гонку на состоянии. Неприменимый reviewer (нет соответствующих файлов в delta)
> не запускается — его поле остаётся `pending`, dev-lead фиксирует «N/A» в Gate Report.

---

## WIP Limits

Лимит — `quality.wip_limit` из project-profile.md (default **5**).

| Колонка | Лимит | Кто проверяет |
|---------|-------|---------------|
| In Development | quality.wip_limit | dev-lead перед запуском developer(ов) |
| Code Review | quality.wip_limit | dev-lead (In Development + Code Review вместе ≤ лимита) |
| Testing | quality.wip_limit | qa-lead перед запуском tester(ов) |

При превышении — Team Lead предупреждает и НЕ берёт новые задачи.

---

## Команды (Skills)

### Kanban pipeline

| Команда | Агент | Что делает |
|---------|-------|------------|
| `/feature <описание>` | analyst | Создаёт GitHub Issue с AC, приоритетом, размером |
| `/analyze #N` | **analysis-lead** → analyst + architect | Декомпозиция → Stories + Spec + Architecture. Gates: G1, G2 |
| `/develop #N [#M ...]` | **dev-lead** → developer(s) + reviewers (security/java/frontend по delta) | Реализация + code review. Gates: G3, G4, G5 |
| `/test #N [all]` | **qa-lead** → test-case-writer | Верификация coverage + TC docs. Gate: G6 |
| `/deploy [staging\|production\|all]` | **ops-lead** → devops | Build → deploy (k8s/compose из профиля) → health check. Gates: G7, G8 |
| `/e2e #N [all]` | **e2e-tester** | E2E автотесты из TC docs в `e2e-tests/` |

### Автоматизация

| Команда | Что делает |
|---------|------------|
| `/kanban <описание>` | Полный pipeline: Feature → Analysis → Develop → Test → Deploy (гейты G1–G8) |
| `/swarm [develop\|test\|analyze\|dry-run]` | Все Team Leads ПАРАЛЛЕЛЬНО по всей доске |
| `/sweep [колонка\|dry-run]` | Автопилот right-to-left (deploy → test → dev → analysis) |
| `/board` | Kanban-доска: колонки, WIP, блокировки, зависимости, метрики |
| `/pick <колонка>` | Взять следующую задачу по приоритету (critical → high → medium → low) |

### Настройка

| Команда | Что делает |
|---------|------------|
| `/setup-board` | Создать поля Project board (включая FrontendReview) + 9 Status-опций (agent-per-status). Лейблы НЕ создаются. Один раз. |
| `/init` | Полная инициализация: авто-детект стека → project-profile.md + board.env + доска + system/memory. Один раз. |
| `/refresh-agents` | Синхронизировать агентов из другого проекта-источника (project-profile.md и board.env НЕ синхронизируются) |

### /sweep vs /swarm

| | `/sweep` | `/swarm` |
|---|----------|----------|
| Порядок | Right-to-left (сначала deploy, потом test, потом dev) | Все Team Leads одновременно |
| Безопасность | Порядок гарантирован, минимум гонок | Возможны гонки на полях доски (несколько Team Lead'ов пишут разные поля) |
| Когда | Обычная обработка всей доски | Нужна максимальная скорость |

---

## Agent Memory System

Shared persistent memory для мультиагентной системы. Экономит ~60-70% токенов на context loading.

### Структура

```
.claude/memory/
├── project-summary.md     # ~500 токенов сжатый ARCHITECTURE.md. Читают все агенты вместо полного файла.
├── active-sprint.md       # Текущий WIP (In Development / Testing). Обновляет dev-lead + qa-lead.
├── decisions.md           # Кросс-story архитектурные решения. Дописывает architect + developer.
└── stories/
    ├── _template.md       # Шаблон для новых stories
    └── story-{N}.md       # Аккумулируется по pipeline. Каждый агент дописывает свой раздел.
```

### Accumulating story-N.md

```
analyst          → создаёт story-N.md, раздел 📋 Задача (~200 токенов)
architect        → дописывает раздел 🏗️ Архитектура (~300 токенов)
developer        → дописывает раздел 💻 Реализация (~300 токенов)
security-reviewer→ дописывает раздел 🔒 Security Review (~100 токенов)
java-reviewer    → дописывает раздел ☕ Java Review (~150 токенов)
qa-lead          → дописывает раздел ✅ QA (~150 токенов)
```

Итог: ~1200 токенов вместо spec(3K)+arch(3K)+issue(2K)+ARCHITECTURE(8K) = **-15K токенов на story**.

### Obsidian Integration

Папка `.claude/memory/` открывается как Obsidian Vault (File → Open Folder as Vault). Плагины Dataview, Tasks, Graph View — для навигации между stories и decisions.

### Правила

- Агенты **дописывают** свой раздел — не перезаписывают чужие
- `decisions.md` — только решения, влияющие на **2+ stories**
- `active-sprint.md` — обновляют Team Leads, не рабочие агенты
- Память читается ПЕРВОЙ (до ARCHITECTURE.md и specs)

---

## Артефакты

| Этап | Агент | Артефакт |
|------|-------|----------|
| Analysis | analyst | `docs/specs/feature-{N}-{name}.md` |
| Analysis | architect | `docs/arch/feature-{N}-{name}.md` |
| Analysis | architect | Code stubs (по модулям проекта, стиль из CLAUDE.md) |
| Development | developer | Backend + Frontend (Angular/React) код |
| Development | developer | DB migrations (Flyway/Liquibase из профиля) |
| Development | developer | Unit tests (coverage ≥ quality.unit_coverage_min новых файлов) |
| Development | developer | `.claude/handoffs/story-{N}-dev.md` (для QA, с реальным coverage %) |
| Memory | analyst | `.claude/memory/stories/story-{N}.md` (раздел 📋) |
| Memory | architect | `.claude/memory/stories/story-{N}.md` (раздел 🏗️) |
| Memory | developer | `.claude/memory/stories/story-{N}.md` (раздел 💻) |
| Memory | security-reviewer | `.claude/memory/stories/story-{N}.md` (раздел 🔒) |
| Memory | java-reviewer + frontend-reviewer | `.claude/memory/stories/story-{N}.md` (раздел ☕) |
| Memory | qa-lead | `.claude/memory/stories/story-{N}.md` (раздел ✅) |
| Security | security-reviewer | Comment в issue: Security Review Report |
| Security | security-reviewer | Bug issues (Type=bug, Priority=critical) при FAIL |
| Java Review | java-reviewer | Comment в issue: Java + System Design Review Report |
| Java Review | java-reviewer | Bug issues (Type=tech-debt, Priority=high) при FAIL |
| Frontend Review | frontend-reviewer | Comment в issue: Frontend Review Report + bug issues при FAIL |
| Testing | test-case-writer | `docs/test-cases/feature-{N}-{name}.md` |
| Testing | test-case-writer | `docs/test-cases/traceability-tc.md` |
| E2E | e2e-tester | `e2e-tests/src/` (Page Objects + Scenarios) |
| Deploy | devops | Docker / CI configs |
| All gates | Team Leads | Quality Gate Report comments в issues |
| All stages | doc-sync | `docs/traceability.md` |

---

## Принципы системы

1. **Автономность** — каждый агент Senior-уровня, работает без подтверждений от человека
2. **Иерархия** — Team Leads координируют и enforc'ят gates; рабочие агенты исполняют
3. **Status-first** — СНАЧАЛА выставить Status на доске через `kanban_set`, ПОТОМ начинать работу
4. **Multi-review по delta** — security-reviewer (всегда) + java-reviewer (backend-delta) + frontend-reviewer (frontend-delta) запускаются dev-lead **параллельно** в статусе **Code Review** (после G4). Все применимые должны пройти (G5) перед переходом в Testing. `warning` не блокирует.
5. **GitFlow story branching** — ветка `feature/{N}-{name}` для фичи; каждая story отпочковывается в `story/{storyN}-{slug}` **от ветки фичи**, работа ведётся там, по завершению мёрж story → feature (не в default branch напрямую)
6. **Evidence-driven** — Quality Gate Reports содержат реальный вывод команд, не утверждения
7. **Параллелизм** — независимые stories всегда параллельно; developer в worktree; reviewer-агенты параллельно
8. **WIP-контроль** — строго ≤ quality.wip_limit (default 5) in-development, столько же in-testing
9. **Field ownership (single-writer)** — каждое поле-семейство пишет ровно один агент: `Security` → security-reviewer, `JavaReview` → java-reviewer, `FrontendReview` → frontend-reviewer, `QA`/`Coverage` → qa-lead, `Deploy` → devops, `Type/Priority/Size/Component` → analyst, `Status` → Team Lead через `kanban_set` (см. Board Field System). Всё состояние живёт в полях доски; лейблов состояния не существует.
10. **DAG-aware** — зависимые stories автоматически skip'ятся если blocker не resolved
11. **Circuit breaker** — max quality.fix_loop_max (default 3) попыток исправить (review fix loop, build fix) → эскалация человеку
12. **Build gate** — developer, devops проверяют build перед ключевыми действиями (команды из профиля)
13. **Developer owns tests** — developer пишет unit tests (coverage ≥ quality.unit_coverage_min). E2E → `/e2e` (ручной). Integration → в рамках разработки.
14. **Memory-first context loading** — агенты читают `.claude/memory/story-N.md` (~900 токенов) ВМЕСТО spec+arch+issue+ARCHITECTURE (~16K токенов). Экономия ~90K токенов на 3 stories × pipeline.
15. **Accumulating story files** — каждый агент дописывает свой раздел в `story-N.md` (📋🏗️💻🔒☕✅). Следующий агент читает весь файл — не перечитывает первоисточники.
16. **SDC как артефакт-посредник** — системные вопросы (ownership/идемпотентность/транзакции/откат миграции/таймауты/blast radius/прод-AC/anti-scope) живут в одном файле `.claude/system/sdc.md`. analyst заполняет 8 слотов в spec, architect детализирует, java-reviewer верифицирует код против spec, G6 проверяет rollback+kill switch, G7 cron'ом сверяет реальные метрики. Без новых агентов.
17. **Architectural Budget — ratchet** — `.claude/system/budget.md` отслеживает cumulative complexity. При threshold (новый модуль/external/exchange) — ADR обязателен. Это самозапрет через ресурс, не через надзирателя.
18. **Ownership-map — единый owner на ресурс** — каждая таблица/exchange/endpoint имеет ровно одного владельца-модуля. Cross-module запись только через owner API/event. analyst обновляет `.claude/system/ownership-map.md` при создании нового ресурса.
19. **Post-deploy без LLM** — G9 это `bash + jq + curl + gh`, не агент. Метрики — это цифры; сравнивать цифры с порогом моделей не нужно.
20. **Agent-per-status** — каждый Status доски = активный агент, который сейчас держит задачу. Доска синхронна и последовательна: следующий агент берёт задачу только после того, как предыдущий провёл её через Quality Gate. Два статуса держат группу агентов, работающих параллельно над одной задачей (Analysis: analyst+architect; Code Review: security + java + frontend reviewers по delta) — все применимые обязаны пройти гейт выхода. «Ожидающие» статусы (Ready for Dev, Ready to Deploy) — буферы между Team Lead'ами, активного агента нет.
21. **Profile-first** — всё проект-специфичное (стек, команды build/test/deploy, топология сервисов, пороги) живёт в `.claude/project-profile.md` + `.claude/board.env`, заполняется `/init` авто-детектом. Агенты не хардкодят команды и не угадывают стек — читают профиль; при незаполненном профиле выполняют Fallback Detect и предлагают запустить `/init`.
22. **Kubernetes-first deploy** — на k8s-проектах деплой идёт через helm/kustomize/kubectl из `commands.deploy.*`, здоровье проверяется `kubectl rollout status` + health endpoints сервисов, откат — `commands.deploy.rollback` (helm rollback / kubectl rollout undo). docker-compose — альтернатива для проектов без k8s. High-load проекты (quality.high_load) дополнительно проверяются на resources/HPA/replicas перед prod.

---

## Структура файлов

```
.claude/
├── AGENTS_FRAMEWORK.md          # ← этот файл
├── project-profile.md           # ★ Профиль проекта: стек, топология, команды, пороги. Заполняет /init.
├── board.env                    # ★ Идентичность доски (OWNER/REPO/PROJECT_NUMBER/PROJECT_ID). Создаёт /init.
├── board.env.example            # Шаблон board.env
├── settings.json                # Permissions (gh, git, build tools, docker, kubectl, ...) + hooks
├── agents/
│   │   — Team Leads —
│   ├── analysis-lead.md         # [sonnet] Координирует analyst + architect. G1, G2.
│   ├── dev-lead.md              # [sonnet] Координирует developer(s) + reviewers. G3, G4, G5.
│   ├── qa-lead.md               # [sonnet] Координирует test-case-writer. G6.
│   ├── ops-lead.md              # [sonnet] Координирует devops. G7, G8.
│   │   — Рабочие агенты —
│   ├── analyst.md               # [sonnet] Декомпозиция, спецификации, Status на доске
│   ├── architect.md             # [opus]   ADR, ERD, API contracts, code stubs, k8s/high-load дизайн
│   ├── developer.md             # [opus]   Backend + Frontend (Angular/React). Unit tests. Worktree isolation.
│   ├── security-reviewer.md     # [sonnet] OWASP, AI-specific, JWT/RBAC, k8s-секреты. Всегда в Code Review.
│   ├── java-reviewer.md         # [sonnet] Java Senior + System Design + микросервисы. Если backend-delta.
│   ├── frontend-reviewer.md     # [sonnet] Angular/React ревью. Если frontend-delta.
│   ├── test-case-writer.md      # [sonnet] TC-документация. Cross-reference sync.
│   ├── e2e-tester.md            # [opus]   Java Playwright E2E. Только /e2e.
│   ├── devops.md                # [sonnet] k8s/compose deploy, CI/CD, monitoring
│   ├── doc-sync.md              # [sonnet] Traceability matrix. Spec↔code consistency.
│   ├── integration-tester.md    # [opus]   НЕ АКТИВЕН. Резерв.
│   │   — Shared-протоколы (не агенты) —
│   ├── quality-gates.md         # G1–G8 чеклисты (+ G9 post-deploy), verdicts, report template
│   ├── dependency-resolver.md   # DAG-зависимости, circular detection, auto-dispatch
│   └── kanban-board-sync.md     # Хелперы kb_*/kanban_* (source board.env) + протокол доски
├── memory/                      # Shared persistent memory (Obsidian-compatible)
│   ├── project-summary.md       # Сжатый ARCHITECTURE.md (~500 токенов) — генерирует /init
│   ├── active-sprint.md         # Текущий WIP — обновляют Team Leads
│   ├── decisions.md             # Кросс-story архитектурные решения
│   └── stories/
│       ├── _template.md         # Шаблон
│       └── story-{N}.md         # Аккумулируется: 📋🏗️💻🔒☕✅
├── system/                      # System Design Discipline (TRIZ-слой)
│   ├── sdc.md                   # System Design Checklist — 8 обязательных слотов
│   ├── budget.md                # Architectural Budget — cumulative + threshold→ADR
│   ├── ownership-map.md         # Карта владения: ресурс → owner module/service
│   └── postdeploy.sh            # G9 cron (bash, без LLM): метрики vs PROD AC
└── commands/
    ├── feature.md               # /feature  — Feature Request
    ├── analyze.md               # /analyze  — Analysis (analysis-lead)
    ├── develop.md               # /develop  — Development (dev-lead)
    ├── test.md                  # /test     — Testing (qa-lead)
    ├── deploy.md                # /deploy   — CI/CD & Deploy (ops-lead)
    ├── e2e.md                   # /e2e      — E2E автотесты (e2e-tester)
    ├── allure-report.md         # /allure-report — E2E прогон + Allure HTML отчёт
    ├── java-review.md           # /java-review — ad-hoc запуск java-reviewer
    ├── doc-sync.md              # /doc-sync — Traceability + spec↔code валидация
    ├── kanban.md                # /kanban   — Full Pipeline (все 5 этапов)
    ├── swarm.md                 # /swarm    — Все Team Leads параллельно
    ├── sweep.md                 # /sweep    — Right-to-left автопилот
    ├── board.md                 # /board    — Kanban-доска + метрики
    ├── pick.md                  # /pick     — Взять задачу по приоритету
    ├── setup-board.md           # /setup-board — Поля доски (11) + 9 Status-опций
    ├── init.md                  # /init     — Полная инициализация системы (адаптер под проект)
    └── refresh-agents.md        # /refresh-agents — Синхронизация агентов (кроме profile/board.env)
```

---

## Настройка на новом проекте

**Один шаг: скопируй `.claude/` в корень проекта и запусти `/init`.** Он сделает всё сам:

```bash
# 0. Предусловия
gh auth login
gh auth refresh -s repo,project,read:org
gh auth status                    # проверить scopes

# 1. Скопировать систему в проект
cp -R <источник>/.claude <проект>/.claude    # или /refresh-agents --source <источник>

# 2. Инициализация (один раз)
/init
```

`/init` выполняет:
1. **Скан стека** — build tool (Gradle/Maven wrapper), Spring Boot, микросервисы (мульти-модуль /
   несколько Dockerfile / services/), frontend-приложения (Angular и/или React — может быть
   несколько), БД/кэш/брокер, Kubernetes (helm/kustomize/manifests), миграции (Flyway/Liquibase),
   CI, мониторинг.
2. **Заполняет `.claude/project-profile.md`** — канонические команды build/test/coverage/deploy,
   топология сервисов, пороги качества (coverage/WIP/fix-loop — дефолты 95/50/5/3).
3. **Создаёт `.claude/board.env`** — OWNER/REPO из `git remote`, Project берёт существующий или
   создаёт `gh project create`.
4. **Создаёт поля доски** (логика `/setup-board`): 9 Status-опций + Type, Priority, Size,
   Component, Security, JavaReview, FrontendReview, QA, Deploy, Coverage.
5. **Генерирует backstop** `.github/workflows/kanban-reconcile.yml` (нужен repo-secret
   `KANBAN_PROJECT_TOKEN` — classic PAT со scope `project`).
6. **Инициализирует** `.claude/system/` (budget учёт + ownership-map сканом) и
   `.claude/memory/project-summary.md` (~500 токенов выжимка архитектуры).
7. **Дополняет CLAUDE.md** ссылками на профиль (не дублируя значения).

Вручную (UI, один раз): Project Settings → Workflows — выключить `Auto-close issue` и
`Pull request merged`, `Item added` → Backlog, `Item closed` → Done. Детали — в `/setup-board`.

### Первая фича

```bash
/feature <описание новой фичи>
/analyze #1
/develop #2 #3 #4
/test all
/deploy staging
```

Или всё одной командой: `/kanban <описание>`

### Переезд системы между проектами

`/refresh-agents --source <другой-проект>` синхронизирует агентов и команды.
`.claude/project-profile.md` и `.claude/board.env` — проект-специфичны и НИКОГДА не копируются.

---

## Типичные сценарии

| Задача | Команды |
|--------|---------|
| Новая фича от идеи до staging | `/kanban <описание>` |
| Новая фича пошагово | `/feature` → `/analyze` → `/develop` → `/test` → `/deploy` |
| Обработать всю доску безопасно | `/board` → `/sweep dry-run` → `/sweep` |
| Максимальная параллельность | `/swarm` |
| Несколько stories параллельно | `/develop #3 #4 #5` → `/test all` → `/deploy staging` |
| Зависимые stories (Entity→Service→API) | `/develop #3 #4 #5 #6` (dev-lead сам определит порядок) |
| Срочный hotfix | `kb_meta N type=hotfix priority=critical` + `kanban_set N "Ready for Dev"` → `/develop #N` → `/test #N` → `/deploy staging` |
| E2E тесты после деплоя | `/e2e #N` или `/e2e all` |
| Утренний check-in | `/board` |
| Разблокировать доску | `/board` → найти blocked → `/develop #blocker` → `/sweep` |
