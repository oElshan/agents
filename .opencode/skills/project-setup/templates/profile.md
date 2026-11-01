# Профиль проекта

Единственный источник команд и порогов для агентов. Заполняет `/setup` (детект и
подтверждение человеком). Агенты подставляют команды дословно и своих не придумывают.
Пустая строка означает «не настроено». Если проверка требует такую команду, она блокирует работу.

```yaml
profile:
  initialized: false        # /setup ставит true
  updated: ""               # YYYY-MM-DD

project:
  default_branch: main

tracker:
  mode: local               # local | github
  # параметры GitHub Project хранятся в .agents/cache/github.json (создаёт /sync setup, вне git)

gates:
  spec_approval: human      # human: после G2 фича ждёт /approve | auto: stories создаются сразу

stack:
  backend:
    language: java          # java | kotlin
    framework: ""           # spring-boot-3 | quarkus | micronaut
    build_tool: ""          # gradle | gradle-kts | maven
    java_version: ""
  frontend:                 # несколько приложений допустимо
    - name: ""
      framework: ""         # angular | react
      path: ""
      package_manager: ""   # npm | yarn | pnpm
  data:
    databases: []           # postgresql, mysql, mongodb
    caches: []              # redis, caffeine
    brokers: []             # kafka, rabbitmq
    migration_tool: ""      # flyway | liquibase | none
  infra:
    containerization: ""    # docker | none
    orchestration: ""       # kubernetes | docker-compose | none
    k8s_tooling: ""         # helm | kustomize | raw-manifests | none
    k8s_manifests_path: ""
    ci: ""                  # github-actions | gitlab-ci | jenkins | none
    monitoring: ""          # prometheus | none

topology:
  type: ""                  # monolith | modular-monolith | microservices
  shared_contracts: ""      # модуль общих DTO/Events или ""
  services:
    - name: ""
      path: ""
      kind: backend         # backend | frontend | gateway | worker
      port: 0
      health: ""            # /actuator/health

paths:
  migrations:               # pathspec-глобы файлов миграций
    - "**/db/migration/**"
    - "**/db/changelog/**"

commands:
  backend:
    build: ""               # ./gradlew build -x test | ./mvnw -q package -DskipTests
    test: ""                # ./gradlew test | ./mvnw test
    test_one_service: ""    # ./gradlew :{service}:test | ./mvnw -pl {service} test
    coverage: ""            # ./gradlew test jacocoTestReport | ./mvnw verify
    coverage_sources:      # каждому корню исходников — XML отчёт своего модуля; без glob
      - root: src/main/java
        report: ""          # build/reports/jacoco/test/jacocoTestReport.xml | target/site/jacoco/jacoco.xml
    lint: ""                # ./gradlew spotlessCheck | ./mvnw checkstyle:check
    integration_test: ""    # ./gradlew integrationTest (Testcontainers)
  frontend:
    - name: ""
      install: ""           # npm ci
      build: ""             # npm run build | ng build
      test: ""              # npm test -- --watch=false | ng test --watch=false
      lint: ""              # npm run lint
  e2e:
    runner: ""              # java-playwright | none
    path: ""                # e2e-tests/
    run: ""                 # cd e2e-tests && ./gradlew test
  local_env:
    up: ""                  # docker compose up -d
    down: ""                # docker compose down
  deploy:
    prepare_artifact: ""    # собрать из HEAD; stdout = JSON {commit, artifacts}; логи в stderr
    staging: ""             # helm upgrade --install … | kubectl apply -k … | пусто = стадии деплоя нет
                            # команда читает .agents/cache/deploy-manifest.json и использует digest
    observe_artifact: ""    # прочитать фактический {commit, artifacts} из staging
    rollback: ""            # helm rollback {release} | kubectl rollout undo deployment/{service}
    status: ""              # kubectl rollout status deployment/{service} -n {ns} --timeout=180s
    namespace_staging: ""
    context_staging: ""     # явный контекст Kubernetes
  smoke:
    staging: ""             # curl -sf https://staging…/api/health

quality:
  unit_coverage_min: 95     # % строк изменённых исходных файлов (G4)
  hotfix_coverage_min: 50
  fix_loop_max: 3           # возвратов в In Development до парковки
  high_load: false          # включает high-load чек-листы

orchestrator:
  max_agent_runs: 40        # запусков субагентов за один /orchestrate
  stall_rounds: 3           # шагов без движения подряд → STALL
  # паузы стадий не здесь: их ставит /stage в .agents/board/stages.json (вне git)
```
