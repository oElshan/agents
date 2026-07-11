# Project Profile

> **Единственный источник правды о стеке и командах проекта.**
> Заполняется командой `/init` (авто-детект + подтверждение человеком). Все агенты читают
> этот файл ПЕРВЫМ — до CLAUDE.md, ARCHITECTURE.md и spec'ов — и берут команды ТОЛЬКО отсюда.
> Ни один агент не хардкодит `./gradlew`, `npm`, `kubectl` — только ссылки на ключи профиля.

```yaml
profile:
  initialized: false        # /init выставляет true. Если false — агент обязан запустить Fallback Detect (ниже)
  updated: ""               # YYYY-MM-DD последней синхронизации с реальностью проекта
```

---

## 1. Идентификация

```yaml
github:
  owner: ""                 # org или user
  repo: ""
  project_number: 0         # номер GitHub Project (доски)
  project_id: ""            # node-id доски (PVT_...)
  default_branch: main      # main | develop | master
```

## 2. Стек

```yaml
stack:
  backend:
    language: java          # java | kotlin | ...
    framework: ""           # spring-boot-3 | quarkus | micronaut | ...
    build_tool: ""          # gradle | gradle-kts | maven
    java_version: ""
  frontend:                 # НЕСКОЛЬКО приложений допустимо (Angular + React в одном репо)
    - name: ""              # например admin-ui
      framework: ""         # angular | react | ...
      path: ""              # относительный путь
      package_manager: ""   # npm | yarn | pnpm
  data:
    databases: []           # [postgresql, mysql, mongodb, ...]
    caches: []              # [redis, hazelcast, caffeine, ...]
    brokers: []             # [kafka, rabbitmq, ...]
    migration_tool: ""      # flyway | liquibase | none
  infra:
    containerization: ""    # docker | none
    orchestration: ""       # kubernetes | docker-compose | none
    k8s_tooling: ""         # helm | kustomize | raw-manifests | none
    k8s_manifests_path: ""  # например deploy/helm или k8s/
    ci: ""                  # github-actions | gitlab-ci | jenkins | none
    monitoring: ""          # prometheus | none
    metrics_url: ""         # base URL Prometheus/Grafana API (для postdeploy.sh)
```

## 3. Топология (микросервисы)

```yaml
topology:
  type: ""                  # monolith | modular-monolith | microservices
  shared_contracts: ""      # модуль общих DTO/Events (например `common` / `shared-contracts`); "" если нет
  services:                 # для microservices/multi-module — по строке на сервис
    - name: ""              # например order-service
      path: ""              # относительный путь
      kind: backend         # backend | frontend | gateway | worker
      port: 0
      health: ""            # health endpoint, например /actuator/health
```

## 4. Канонические команды

Агенты подставляют эти команды дословно. `{service}` — плейсхолдер имени/пути сервиса;
для монолита команды без плейсхолдера.

```yaml
commands:
  backend:
    build: ""               # напр. ./gradlew build -x test | mvn -q package -DskipTests
    test: ""                # напр. ./gradlew test | mvn test
    test_one_service: ""    # напр. ./gradlew :{service}:test | mvn -pl {service} test
    coverage: ""            # команда с отчётом покрытия + путь к отчёту
    coverage_report: ""     # напр. build/reports/jacoco/test/html/index.html
    lint: ""                # напр. ./gradlew spotlessCheck | mvn checkstyle:check; "" если нет
    integration_test: ""    # напр. ./gradlew integrationTest (Testcontainers); "" если нет
  frontend:                 # по записи на каждое frontend-приложение из stack.frontend
    - name: ""
      install: ""           # npm ci | yarn install --frozen-lockfile | pnpm i --frozen-lockfile
      build: ""             # npm run build | ng build
      test: ""              # npm test -- --watch=false | ng test --watch=false
      lint: ""              # npm run lint; "" если нет
  e2e:
    runner: ""              # java-playwright | playwright-ts | cypress | none
    path: ""                # e2e-tests/ или аналог
    run: ""                 # команда запуска E2E
  local_env:
    up: ""                  # docker compose up -d | make dev | ""
    down: ""
  deploy:
    staging: ""             # helm upgrade --install ... | kubectl apply -k ... | скрипт
    production: ""
    rollback: ""            # helm rollback {release} | kubectl rollout undo deployment/{service}
    status: ""              # kubectl rollout status deployment/{service} -n {ns} --timeout=180s
    namespaces:
      staging: ""
      production: ""
  smoke:
    staging: ""             # curl основного API на staging
    production: ""
```

## 5. Политики качества (пороги гейтов)

```yaml
quality:
  unit_coverage_min: 95     # % для новых файлов (G6); hotfix — hotfix_coverage_min
  hotfix_coverage_min: 50
  wip_limit: 5
  review:
    backend: true           # запускать code-reviewer (Java) на backend-delta
    frontend: true          # запускать frontend-reviewer на frontend-delta
    security: true          # security-reviewer — всегда
  high_load: true           # включает high-load чек-листы (пулы, кэши, backpressure, нагрузочные NFR)
  fix_loop_max: 3           # circuit breaker: попыток исправления до эскалации человеку
```

## 6. Оркестрация (петля `/orchestrate`)

Политика единого оркестратора. Задаёт дефолты замкнутой петли; аргументы команды и пресеты
(`/sweep`/`/swarm`/`/pick`) переопределяют. Термины — в `.claude/ORCHESTRATOR_DESIGN.md`.

> ⚠️ Это **runtime-бюджет петли** (тики/токены/время). Не путать с
> `.claude/system/budget.md` — там бюджет **архитектурной сложности** (ratchet → ADR).

```yaml
orchestrator:
  mode: continuous          # single-tick (один проход, как старый /sweep) | continuous (петля до остановки)
  concurrency: auto         # seq (по очереди, минимум гонок) | parallel (все Team Leads разом) | auto
  max_ticks: 20             # жёсткий потолок числа тиков петли
  stall_rounds: 2           # тиков без прогресса подряд → STALL (нет prog. + нет in-flight → стоп)
  budget_tokens: null       # опциональный потолок токенов на прогон; null = без лимита
  pace_seconds: 1200        # сон при ожидании внешнего (человеческий APPROVE / общий idle); активный деплой опрашивается ~270с
  stop_on_human_gate: true  # prod-approve issue паркуются (Parked=human) и петля останавливается на них
  disabled_stages: []       # постоянно отключённые стадии (ставит /stage): analysis|develop|testing|deploy. Их агенты не запускаются, задачи ждут в буфере
  # --- Спринтовая модель: оркестратор работает ТОЛЬКО по текущему спринту, бэклог не трогает ---
  current_sprint: ""        # активный спринт (значение поля Sprint). Ставит /sprint activate. Пусто = спринт не выбран → оркестратор ничего не делает
  sprint_model: stories     # stories (в спринт кладём готовые к разработке stories; анализ фич — вручную в бэклоге) | features (фичи целиком, анализ внутри спринта)
  sprint_carryover: next    # при /sprint close недоделанное → next (следующий спринт) | backlog (назад в интейк)
```

---

## Fallback Detect (когда `initialized: false`)

Агент, обнаруживший незаполненный профиль, НЕ падает, а выполняет минимальный детект
и работает по нему (сообщив человеку, что стоит запустить `/init`):

| Признак в репо | Вывод |
|---|---|
| `gradlew` / `build.gradle(.kts)` | build_tool=gradle → `./gradlew build`, `./gradlew test` |
| `mvnw` / `pom.xml` | build_tool=maven → `./mvnw verify` (или `mvn`) |
| `settings.gradle` с N include / несколько `pom.xml` | modular/multi-service — тесты по модулю `:{service}:test` |
| `angular.json` | frontend=angular → `ng build`, `ng test --watch=false` |
| `package.json` с `react` в dependencies | frontend=react → `npm run build`, `npm test` |
| `Chart.yaml` / `helm/` | k8s_tooling=helm |
| `kustomization.yaml` | k8s_tooling=kustomize |
| каталог `k8s/`, `deploy/`, `*.yaml` c `kind: Deployment` | orchestration=kubernetes |
| `docker-compose*.yml` | local_env=docker compose |
| `src/main/resources/db/migration` | migration_tool=flyway |
| `liquibase` в build-файле | migration_tool=liquibase |
| `pnpm-lock.yaml` / `yarn.lock` / `package-lock.json` | package_manager=pnpm / yarn / npm |

Правило детекта команд: **сначала wrapper** (`./gradlew`, `./mvnw`), только потом глобальные
`gradle`/`mvn`. Для npm-скриптов — читать реальные `scripts` из `package.json`, не угадывать.
