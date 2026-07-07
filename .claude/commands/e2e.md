---
description: "E2E: Генерация E2E автотестов на Java (Playwright + JUnit 5 + Page Object) из TC документации. Отдельный проект e2e-tests/. Примеры: /e2e #42 | /e2e #42 #45 | /e2e all"
argument-hint: "<#N feature | несколько через пробел | all>"
---

# E2E Test Generation: $ARGUMENTS

Генерирует E2E автотесты из `docs/test-cases/` в отдельный Java проект `e2e-tests/`.

> Запускается ОТДЕЛЬНО от `/test`. Не блокирует деплой на staging.
> Обычно запускают после первого деплоя feature на staging.

## Алгоритм

Сначала прочитай `.claude/project-profile.md`: build tool backend'а (`stack.backend.build_tool`),
пути и фреймворки frontend-приложений (`stack.frontend[]`), порты (`topology.services[].port`)
бери оттуда; если `initialized: false` — выполни Fallback Detect из этого же файла.

### ШАГ 1 — Определи scope

- Если номер(а) → читай `docs/test-cases/feature-{N}-{name}.md`
- Если `all` → читай все файлы в `docs/test-cases/`

```
Glob("docs/test-cases/feature-{N}-*.md")
```

Проверь что TC файлы существуют. Если нет → сначала запусти `/test #{N}` (test-case-writer создаст их).

### ШАГ 2 — Инициализация e2e-tests/ проекта (если не существует)

```bash
ls e2e-tests/ 2>/dev/null || echo "NOT_EXISTS"
```

Если проект не существует:
```
Agent(subagent_type="e2e-tester", prompt="Initialize e2e-tests/ project structure.
Build tool: тот же, что у backend из .claude/project-profile.md (stack.backend.build_tool):
Gradle → build.gradle, Maven → pom.xml.
Create: build-файл, BasePage.java, BaseE2ETest.java, E2EConfig.java, TestUsers.java, LoginPage.java.
See e2e-tester agent instructions for exact structure and code.")
```

### ШАГ 3 — Запуск e2e-tester

```
Agent(subagent_type="e2e-tester", prompt="Generate E2E tests for: $ARGUMENTS.

CONTEXT LOADING:
1. Read TC files: docs/test-cases/feature-{N}-{name}.md (for each requested feature)
2. Read traceability: docs/test-cases/traceability-tc.md
3. Glob existing E2E: e2e-tests/src/test/java/**/*.java
4. Glob frontend components по путям из stack.frontend[] профиля:
   Angular → {path}/src/app/**/*.{ts,html}; React → {path}/src/**/*.{tsx,ts}

ЗАДАЧА:
1. For each TC with Priority=Critical or Priority=High:
   - Create/update Page Object for the tested page
   - Create E2E test method mapping TC steps to Playwright actions
   - Use data-testid selectors ONLY
2. Compile: cd e2e-tests && команда по build tool проекта e2e-tests — определи по существующему
   build-файлу в e2e-tests/ (build.gradle → ./gradlew compileTestJava; pom.xml → mvn test-compile)
3. If environment available: запусти тесты тем же build tool (./gradlew test | mvn test)
4. Update TC docs: mark E2E Automated=Yes, add E2E Test IDs
5. Update docs/test-cases/traceability-tc.md

Report: test count, compile status, runtime status.")
```

### ШАГ 4 — Финальный отчёт

```
E2E GENERATION COMPLETE
Features: $ARGUMENTS

E2E Tests:
  ✅ Critical: {N} automated
  ✅ High: {N} automated
  ⏸ Medium: {N} skipped (not required)

Project: e2e-tests/
  Compile: {OK | FAIL}
  Runtime: {N passed | skipped (no env) | N failed}

data-testid gaps:
  {list of missing attributes if any — developer must add}

TC Docs Updated:
  {list of updated TC files}

Run locally:
  cd e2e-tests && E2E_BASE_URL={URL frontend-приложения из профиля (topology.services[].port),
  например http://localhost:4200 для Angular dev-server} {команда тестов по build tool:
  ./gradlew test | mvn test}

Run in CI:
  Add to CI pipeline: cd e2e-tests && {./gradlew test | mvn test — по build tool проекта e2e-tests}
  Requires: E2E_BASE_URL and E2E_API_URL env vars
```
