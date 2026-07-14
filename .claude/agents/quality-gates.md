# Quality Gates Protocol

Shared-протокол для Team Leads. При каждом переходе kanban-колонки — выполни соответствующий Quality Gate.
Команды build/test/deploy и пороги бери из `.claude/project-profile.md` (`commands.*`, `quality.*`); если `initialized: false` — выполни Fallback Detect из этого же файла.

**Модель доски — agent-per-status:** каждый Status соответствует активному агенту (или паре).
Гейт срабатывает на границе между статусами. Полная карта — в `AGENTS_FRAMEWORK.md` → «Kanban Flow».

```
Backlog ─(человек)→ Sprint → Analysis → Ready for Dev → In Development → Code Review → Testing → Ready to Deploy → Deploy → Done
                         G1        G2               G3               G4           G5        G6                G7       G8
```

> `Backlog` = сырой интейк (агенты не берут). `Sprint` = взято в работу (человек кладёт рукой или
> `/sprint add`). Переход `Backlog → Sprint` — это **действие человека**, не gate. Оркестратор
> берёт новую работу ТОЛЬКО из `Sprint`; для `feature`/`epic` первый gate — G1 (`Sprint → Analysis`),
> для dev-ready (`story`/`bug`/…) вход в пайплайн — G3 (`Sprint → In Development`).

| Gate | Переход | Enforcer | Активный агент справа |
|------|---------|----------|-----------------------|
| G1 | Sprint → Analysis | analysis-lead | analyst + architect |
| G2 | Analysis → Ready for Dev | analysis-lead | — (ожидание) |
| G3 | Ready for Dev → In Development | dev-lead | developer |
| G4 | In Development → Code Review | dev-lead | security-reviewer + java-reviewer + frontend-reviewer (по delta) |
| G5 | Code Review → Testing | dev-lead | test-case-writer |
| G6 | Testing → Ready to Deploy | qa-lead | — (ожидание / prod approve) |
| G7 | Ready to Deploy → Deploy | ops-lead | devops |
| G8 | Deploy → Done | ops-lead | — (терминал) |
| G9 | +72ч после prod | postdeploy.sh (cron, без LLM) | — |

---

## Gate Definitions

### G1 — Sprint → Analysis

**Enforcer:** analysis-lead
**Transition:** Status: `Sprint` → `Analysis` (`kanban_set {N} "Analysis"`)
**Источник:** только `feature`/`epic` из колонки `Sprint` (взято в работу человеком). `Backlog` не трогаем — это интейк.
**Активный агент справа:** analyst + architect (работают в статусе Analysis).

Checklist:
- [ ] Business value описана (WHY, не только WHAT)
- [ ] Acceptance Criteria присутствуют (хотя бы верхнеуровневые)
- [ ] Нет дубликатов в Issues (поиск по title + keywords)
- [ ] Приоритет назначен (поле `Priority`: critical/high/medium/low — `kb_get {N} Priority`)
- [ ] Тип назначен (поле `Type`: feature/story/tech-debt/… — `kb_get {N} Type`)

Verdict: **PASS** (все ✅) | **NEEDS WORK** (AC отсутствуют — добавь) | **BLOCKED** (дубликат найден)

---

### G2 — Analysis → Ready for Dev

**Enforcer:** analysis-lead
**Transition:** Status: `Analysis` → `Ready for Dev` (`kanban_set {N} "Ready for Dev"`)

Checklist:
- [ ] Spec файл создан: `docs/specs/feature-{N}-{name}.md`
- [ ] Spec содержит: FR, NFR, AC в Given/When/Then
- [ ] Stories созданы и соответствуют INVEST принципам (SD-2)
- [ ] **SD-1: Каждая story содержит РОВНО ОДИН Given/When/Then блок** — не больше одного сценария
- [ ] **SD-3: Ни одна story не имеет `Size=xl`** — максимум 3 рабочих дня
- [ ] **SD-5: Нет запрещённых паттернов** — title не содержит ` и `/` and `, AC не содержит "and also" / два Given-блока
- [ ] Каждая story имеет заполненные поля доски (Type, Component, Size, Priority) + AC — `kb_meta {N} type=… priority=… size=… component=…`
- [ ] Arch doc создан: `docs/arch/feature-{N}-{name}.md` (если применимо)
- [ ] Arch doc покрывает: data model, API contract, security considerations, RBAC matrix
- [ ] **SDC заполнен**: spec содержит блок `## System Design Answers (SDC)` — все 8 слотов имеют конкретный ответ ИЛИ явный `N/A: <причина>`. Пустых слотов нет. Применимость SDC см. `.claude/system/sdc.md`. Если фича попадает под threshold из `.claude/system/budget.md` — в слоте OWNERSHIP есть ADR-обоснование «почему новый компонент, а не расширение»
- [ ] **Ownership-map обновлён** (если введены новые таблицы/exchange/endpoints): запись добавлена в `.claude/system/ownership-map.md`
- [ ] **Budget обновлён** (если +1 модуль/таблица/external): счётчик и changelog в `.claude/system/budget.md`
- [ ] Parent issue обновлён со ссылками на stories и артефакты
- [ ] Зависимости объявлены через `Blocked by:` синтаксис (если есть)

Verdict: **PASS** | **NEEDS WORK** (spec неполный / stories нарушают SD-1..SD-5 / SDC слоты пустые — исправь) | **BLOCKED** (arch вопрос не решён / threshold budget без ADR)

---

### G3 — Ready for Dev → In Development

**Enforcer:** dev-lead
**Transition:** Status: `Ready for Dev` → `In Development` (`kanban_set {N} "In Development"`)
**Источник:** `Ready for Dev` (дочерние stories после анализа) ИЛИ dev-ready задачи (`story`/`bug`/`tech-debt`/`hotfix`/`spike`), взятые человеком прямо в `Sprint` (тогда переход `Sprint → In Development`).
**Активный агент справа:** developer (реализует в статусе In Development).

Checklist:
- [ ] Build проходит СЕЙЧАС (`commands.backend.build` из профиля, например `./gradlew build -x test` или `mvn -q package -DskipTests`)
- [ ] AC в формате Given/When/Then (testable)
- [ ] Зависимости resolved (см. Dependency Resolver protocol)
- [ ] WIP limit не превышен (< quality.wip_limit, default 5, in-development)
- [ ] Spec и/или arch doc доступны для developer
- [ ] Feature-ветка `feature/{featureN}-{slug}` существует (создать если нет)

Verdict: **PASS** | **NEEDS WORK** (AC не testable — уточни) | **BLOCKED** (build сломан / dependency не resolved / WIP full)

---

### G4 — In Development → Code Review

**Enforcer:** dev-lead
**Transition:** Status: `In Development` → `Code Review` (`kanban_set {N} "Code Review"`)
**Активный агент справа:** security-reviewer + java-reviewer + frontend-reviewer (по delta; все применимые запускаются dev-lead параллельно в статусе Code Review).

> Это гейт «код готов к ревью». Проверки самого ревью (Security/JavaReview) — на **G5**.
> developer НЕ переводит статус сам — он коммитит и остаётся в In Development; переход делает dev-lead.

Checklist:
- [ ] Build + lint проходят без ошибок (реальный вывод команды)
- [ ] **`commands.backend.test` из профиля SUCCESS** (например `./gradlew test` или `mvn test`; для microservices — `commands.backend.test_one_service` по каждому затронутому сервису; реальный фрагмент вывода)
- [ ] **`git status --short` возвращает пустой вывод** (нет untracked/modified файлов). Обязательная проверка ПЕРЕД сменой Status. Если есть файлы → NEEDS WORK, добавь в коммит.
- [ ] **story-ветка смёрджена в feature-ветку** (`git checkout feature/{featureN}-{slug} && git merge --no-ff story/{storyN}-{slug}`)
- [ ] **Unit тесты написаны developer**: coverage ≥ quality.unit_coverage_min (default 95%) для новых/изменённых файлов (реальный отчёт `commands.backend.coverage` из профиля, путь — `commands.backend.coverage_report`; конкретные цифры, не "около"). Unit тесты — ответственность developer, не QA.
- [ ] **Handoff создан**: `.claude/handoffs/story-{N}-dev.md` существует и содержит реальный coverage %
- [ ] Нет TODO/FIXME в новом коде (кроме намеренных с issue ссылкой)
- [ ] Commit сообщение в формате `feat(#N): description` с трейлерами (Confidence, Scope-risk, Not-tested)
- [ ] Comment в issue с: изменённые файлы, build status, unit coverage % (реальная цифра), AC checklist для reviewers/QA
- [ ] **doc-sync**: invoke doc-sync agent to update traceability matrix

Verdict: **PASS** (→ `kanban_set {N} "Code Review"`, запусти всех применимых reviewer'ов по delta) | **NEEDS WORK** (orphaned файлы / coverage ниже quality.unit_coverage_min — исправь) | **BLOCKED** (build/тесты сломаны)

---

### G5 — Code Review → Testing

**Enforcer:** dev-lead
**Transition:** Status: `Code Review` → `Testing` (`kanban_set {N} "Testing"`)
**Активный агент справа:** test-case-writer (в статусе Testing).

dev-lead определяет delta story (`git diff --name-only {feature-branch}...{story-branch}` или файлы
из handoff `.claude/handoffs/story-{N}-dev.md`), дожидается ВСЕХ применимых reviewer'ов и читает
вердикты с доски. Применимость: **security-reviewer — ВСЕГДА**; **java-reviewer — только при
backend-delta** (`*.java`/`*.kt`); **frontend-reviewer — только при frontend-delta**
(`*.ts`/`*.tsx`/`*.jsx`/`*.html`/`*.scss` в путях frontend-приложений из профиля).
Неприменимый reviewer не запускается — его поле остаётся `pending`, dev-lead пишет
«N/A — нет соответствующих файлов в delta» в Gate Report.

Checklist:
- [ ] **Поле `Security` = `passed`** (`kb_get {N} Security`; выставляет security-reviewer). Если `failed` → верни developer (max quality.fix_loop_max, default 3, циклов), повтори review.
- [ ] **Поле `JavaReview` ∈ {`passed`, `warning`}** — ЕСЛИ backend-delta (`kb_get {N} JavaReview`; выставляет java-reviewer). Включает **SDC Conformance** (SDC-01..SDC-07). Если `failed` (CRITICAL/HIGH) → верни developer (max quality.fix_loop_max циклов).
- [ ] **Поле `FrontendReview` ∈ {`passed`, `warning`}** — ЕСЛИ frontend-delta (`kb_get {N} FrontendReview`; выставляет frontend-reviewer). Если `failed` (CRITICAL/HIGH) → верни developer (max quality.fix_loop_max циклов).
- [ ] Все применимые reviewer'ы оставили Report comment в issue; для неприменимых в Gate Report зафиксировано «N/A».

> `JavaReview=warning` / `FrontendReview=warning` (только MEDIUM/LOW) **НЕ блокирует** переход в Testing — findings документируются как tech-debt.

Verdict: **PASS** (Security=passed И все применимые Review ∈ {passed, warning}) | **BLOCKED** (Security=failed / JavaReview=failed / FrontendReview=failed — вернуть в In Development на fix)

---

### G6 — Testing → Ready to Deploy

**Enforcer:** qa-lead
**Transition:** Status: `Testing` → `Ready to Deploy` (`kanban_set {N} "Ready to Deploy"`)
**Активный агент справа:** test-case-writer (QA-инженер) — **прогоняет AC по реальному стенду**, не только пишет TC.

Checklist:
- [ ] **ВСЕ AC верифицированы на реальном стенде** — тестировщик поднял стенд (local_env.up / Testcontainers / degraded) и вернул вердикт по каждому AC с **evidence** (реальный HTTP-ответ, код статуса, состояние БД через GET, фрагмент лога). Итог = PASS только если все AC = PASS.
- [ ] **Автотесты перепрогнаны зелёными по факту**: реальный вывод `commands.backend.test` (microservices → `test_one_service`) = SUCCESS. Не «число из handoff», а перепрогон.
- [ ] **Уровень стенда зафиксирован** (A live / B testcontainers / C degraded). C — не блокер, но фиксируется как пониженный confidence.
- [ ] **TC документация создана и обновлена фактом прогона**: `docs/test-cases/feature-{N}-{name}.md` exists, committed, содержит Actual+Verdict (living QA report). Каждый Given/When/Then → минимум 1 TC.
- [ ] **Unit coverage ≥ quality.unit_coverage_min (default 95%)** подтверждена из developer handoff `.claude/handoffs/story-{N}-dev.md`. Для `Type=hotfix` — порог quality.hotfix_coverage_min (default 50%).
- [ ] **Поле `Security` = `passed`** (выставлено security-reviewer на G5; `kb_get {N} Security`). Если не `passed` → **BLOCKED**. **НИКОГДА не выставлять Security самостоятельно — это поле security-reviewer/dev-lead.**
- [ ] **Поля `JavaReview`/`FrontendReview` ∈ {`passed`, `warning`} по применимости delta** (см. G5); неприменимые остаются `pending` — «N/A», не блокер. `failed` → **BLOCKED**.
- [ ] На **каждый провалившийся AC заведён Bug issue** (если были провалы): repro + Expected + Actual(evidence) + `Blocks: #{N}`, спринт унаследован. Поле `QA` ≠ `failed` для PASS.

**G6 НЕ требует (сделано в других этапах или отдельных процессах):**
- Написания unit tests → developer написал (G4); QA только перепрогоняет
- Security / Java review → выполнены на G5 (Code Review); QA только читает поля
- Load tests → отдельный performance cycle
- **UI E2E тесты → отдельный ручной процесс через `/e2e`. НЕ блокируют G6.**

Verdict: **PASS** (все AC верифицированы + автотесты SUCCESS + build зелёный → `kb_set {N} QA passed` + `kb_num {N} Coverage <pct>` → `Ready to Deploy`) | **FAIL** (провал AC / build/тесты сломаны → баги заведены тестировщиком → `kb_set {N} QA failed` → `In Development`, **петля замыкается**) | **BLOCKED** (Security≠passed / применимый Review=failed → остаётся Testing)

---

### G7 — Ready to Deploy → Deploy

**Enforcer:** ops-lead
**Transition:** Status: `Ready to Deploy` → `Deploy` (`kanban_set {N} "Deploy"`)
**Активный агент справа:** devops (деплоит в статусе Deploy).

Pre-flight (перед запуском devops):
- [ ] Issue в колонке `Ready to Deploy` (Status) И поле `QA` == `passed` (`kb_get {N} QA`)
- [ ] Поле `Security` == `passed` (`kb_get {N} Security`)
- [ ] Тесты зелёные (re-run `commands.backend.test` из профиля)
- [ ] Build проходит (`commands.backend.build` из профиля)
- [ ] **High-load** (если `quality.high_load: true`): для production — resources requests/limits, HPA, replicas > 1 заданы в k8s-манифестах
- [ ] **Production**: человек постил `APPROVE PRODUCTION DEPLOY` в комментарий issue. Без approve — ops-lead ждёт, НЕ двигает в Deploy. Staging — автономно.

Verdict: **PASS** (→ `kanban_set {N} "Deploy"`, запусти devops) | **BLOCKED** (любой check fail / для prod нет approve — предложи `/test`)

---

### G8 — Deploy → Done

**Enforcer:** ops-lead (проверяет результат работы devops)
**Transition:** Status: `Deploy` → `Done` (`kanban_set {N} "Done"` — auto-close issue) + `kb_set {N} Deploy staging|production`

Checklist:
- [ ] Все тесты зелёные перед деплоем (re-run: unit + integration)
- [ ] **Все stories коммиты на branch** — verify `git log origin/{BASE}..HEAD` contains all expected stories ({BASE} — `github.default_branch` из профиля)
- [ ] Build артефакт / Docker image собран успешно
- [ ] Деплой раскатан: `commands.deploy.status` OK (например `kubectl rollout status deployment/{service}`); readiness/liveness probes зелёные (k8s-первично; для docker-compose — контейнеры healthy)
- [ ] Health check endpoint отвечает OK после деплоя (приложи snippet ответа health endpoint из `topology.services[].health`; для Spring Boot обычно `/actuator/health`)
- [ ] Smoke test основного API endpoint пройден (`commands.smoke.*` из профиля; приложи запрос + ответ)
- [ ] Логи чистые (нет ERROR/WARN в первые 60 секунд, приложи `kubectl logs --tail 50`; для compose — `docker logs --tail 50`)
- [ ] **Поле `Deploy` выставлено** (`kb_set {N} Deploy staging|production`)
- [ ] Parent feature закрыт (если все stories done)
- [ ] **Rollback rehearsal на staging выполнен**: реально выполни `commands.deploy.rollback` из профиля (helm rollback {release} / kubectl rollout undo deployment/{service}), проверь health и вернись на новую версию; приложи snippet команды + результат (health / DB state до/после). Если SDC #4 = `forward-only` — приложи цитату обоснования. Команда отката должна быть в comment issue.
- [ ] **Kill switch проверен** (если SDC слот #7 декларирует): приложи snippet тоггла kill switch из SDC #7 (feature flag / env / ConfigMap) + observable эффект (логи / metric drop).
- [ ] **doc-sync**: final traceability matrix committed to branch

**Evidence requirement (обязательно):** G8 Report ДОЛЖЕН содержать реальный вывод команд, а не утверждения.

Verdict: **PASS** | **NEEDS WORK** (smoke test failed — investigate) | **BLOCKED** (health check failed — выполни rollback, не продолжай)

---

### G9 — Post-Deploy Verification (через 72ч после production)

**Enforcer:** cron / ручной `bash .claude/system/postdeploy.sh {N}` — **без LLM**, чистый bash (jq + curl + gh). Требует `.claude/board.env` и метрики (`infra.metrics_url` из профиля или env `METRICS_URL`).

Не блокирует pipeline — это feedback loop из прода в дизайн.

Что делает:
1. Извлекает целевые метрики из строки `PROD-AC:` в `docs/specs/feature-{N}-*.md` (формат: `PROD-AC: p95_ms=200 err_rate=0.001 rps=300 metric_prefix=http_server_requests`)
2. Запрашивает реальные значения из Prometheus (`infra.metrics_url`) — окно `[1h]` на момент запуска (запуск через 72ч после деплоя). Если metrics_url / spec / строка PROD-AC не найдены → SKIP
3. Сравнивает факт с целью

Verdict:
- **MATCH** → comment в issue: "✅ G9 post-deploy (+72h): PASS — p95={x}ms (target {y}ms), err={...}" + закрытие feedback loop
- **DEVIATION** → автоматически открывается issue `[G9] Post-deploy metrics mismatch for #{N}` с фактическими цифрами + comment в исходный issue; поля доски (`kb_meta {BUG} type=tech-debt priority=high`) выставляются следом через хелперы (скрипт печатает подсказку). Дальше — обычный pipeline (analyst разбирает).

Это не gate в смысле «блокирует переход» — это контракт о том, что **обещания из SDC слота #7 верифицируются**, и команда узнаёт, когда реальность расходится с дизайном.

---

## Quality Gate Report Template

При прохождении gate — добавь comment в issue:

```
### Quality Gate Report: G{N} — {Gate Name}

| Check | Status |
|-------|--------|
| {check 1} | ✅ / ❌ / ⚠️ |
| {check 2} | ✅ / ❌ / ⚠️ |
| ... | ... |

**Verdict:** {PASS ✅ / NEEDS WORK ⚠️ / BLOCKED 🚫}
{if NEEDS WORK/BLOCKED: описание что нужно исправить}

**Transition:** Status: `{from}` → `{to}`
```

---

## Правила

1. **Gate = обязательный** — НЕЛЬЗЯ пропустить gate при переходе
2. **BLOCKED = СТОП** — не переводи issue дальше, оставь в текущей колонке
3. **NEEDS WORK = fix inline** — исправь проблему и повтори gate
4. **Report = всегда** — каждый gate оставляет comment в issue
5. **Один статус = один активный агент** — переводя задачу в статус, ты передаёшь её конкретному агенту (или группе: Analysis, Code Review [2..3 по delta]). Статус на доске = кто сейчас владеет задачей.
6. **Минимум overhead** — gate это чеклист, не полный аудит. Держи быстрым.
