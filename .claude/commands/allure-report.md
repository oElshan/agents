---
description: "Allure: Запускает E2E тесты и генерирует Allure HTML отчёт. Примеры: /allure-report | /allure-report --groups=<tag> | /allure-report --skip-tests"
argument-hint: "[--groups=<tag>] [--skip-tests] [--long]"
---

# Allure E2E Report: $ARGUMENTS

Запускает E2E тесты в `e2e-tests/` и генерирует Allure HTML отчёт.

> **ОБЯЗАТЕЛЬНОЕ правило**: После каждого прогона E2E тестов ВСЕГДА генерируй Allure отчёт.
> Все тестовые классы в `e2e-tests/` ОБЯЗАНЫ иметь `@Epic`, `@Feature`, `@Story`, `@Severity`, `@Description` аннотации.

## Параметры

- `--groups=<tag>` — JUnit-тег группы тестов; без аргумента фильтр групп не применяется (запускаются все тесты)
- `--long` — включить долгосрочные тесты (pipeline tests)
- `--skip-tests` — только сгенерировать отчёт из существующих results (без запуска тестов)

## Алгоритм

### ШАГ 1 — Проверка зависимостей

```bash
which allure && allure --version || echo "allure not installed"
# Build tool e2e-проекта — по существующему build-файлу: pom.xml → mvn, build.gradle(.kts) → ./gradlew
ls e2e-tests/pom.xml e2e-tests/build.gradle e2e-tests/build.gradle.kts 2>/dev/null | head -1 || echo "e2e-tests/ not found"
```

Если `allure` не установлен — по платформе:
```bash
brew install allure              # macOS
scoop install allure             # Windows
npx allure-commandline --version # fallback без пакетного менеджера (далее вместо `allure` — `npx allure-commandline`)
```

### ШАГ 2 — Запуск тестов (если не `--skip-tests`)

```bash
cd e2e-tests

# Группа — ТОЛЬКО из аргумента --groups=<tag>; без аргумента фильтр групп не применяется
GROUPS=""            # значение из --groups=<tag>, если передан
EXCLUDED=""
if [[ "$ARGUMENTS" != *"--long"* ]]; then
  EXCLUDED="long"
fi

# Maven (pom.xml):
mvn test ${GROUPS:+-Dgroups="$GROUPS"} ${EXCLUDED:+-DexcludedGroups="$EXCLUDED"} \
  -DE2E_API_URL="${E2E_API_URL:-<URL backend API из .claude/project-profile.md (topology.services[].port), например http://localhost:8080>}"

# Gradle (build.gradle): те же -D свойства через ./gradlew test
# (build-файл должен пробрасывать groups/excludedGroups в useJUnitPlatform includeTags/excludeTags)
```

Опциональные фичефлаги E2E-окружения проекта (если определены в конфигурации `e2e-tests/`)
передаются так же через `-D<FLAG>=<value>` — их список смотри в README/конфиге e2e-проекта.

При ошибках — покажи summary, продолжай к генерации отчёта.

### ШАГ 3 — Генерация Allure отчёта

```bash
cd e2e-tests
# results-каталог зависит от build tool: target/allure-results (Maven) | build/allure-results (Gradle)
RESULTS_DIR=$( [ -d target/allure-results ] && echo target/allure-results || echo build/allure-results )
REPORT_DIR="$(dirname "$RESULTS_DIR")/allure-report"
allure generate "$RESULTS_DIR" --clean -o "$REPORT_DIR"
allure open "$REPORT_DIR"
```

### ШАГ 4 — Финальный отчёт

```
ALLURE REPORT GENERATED
========================

Tests run: {N}
  Passed:  {N}
  Failed:  {N}
  Skipped: {N}

Allure results: e2e-tests/{target|build}/allure-results/ ({N} files)
Allure report:  e2e-tests/{target|build}/allure-report/index.html

Report opened in browser via: allure open {REPORT_DIR}

Epics covered (из @Epic-аннотаций прогона; примеры):
  - {например «Orders API»}
  - {например «Notifications»}
  ...
```

## Требования к аннотациям

Каждый тестовый класс ОБЯЗАН иметь на уровне класса или метода:
```java
@Epic("...")
@Feature("...")
```

Каждый тестовый метод ОБЯЗАН иметь:
```java
@Story("...")
@Severity(SeverityLevel.CRITICAL | HIGH | NORMAL | MINOR)
@Description("...")
```

`ApiBaseTest.execute()` автоматически аттачит request URL, response status и body к каждому тесту.

## Зависимости (пример для Maven `pom.xml`; для Gradle — те же координаты в `build.gradle`)

Версии — актуальные стабильные (проверь Maven Central перед генерацией build-файла);
задай их свойствами `allure.version` / `aspectj.version` / `allure.plugin.version`.

```xml
<!-- Allure -->
<dependency>
  <groupId>io.qameta.allure</groupId>
  <artifactId>allure-junit5</artifactId>
  <version>${allure.version}</version>
  <scope>test</scope>
</dependency>
<dependency>
  <groupId>org.aspectj</groupId>
  <artifactId>aspectjweaver</artifactId>
  <version>${aspectj.version}</version>
  <scope>test</scope>
</dependency>

<!-- Maven plugin -->
<plugin>
  <groupId>io.qameta.allure</groupId>
  <artifactId>allure-maven</artifactId>
  <version>${allure.plugin.version}</version>
</plugin>
```

Maven Surefire ОБЯЗАН иметь AspectJ agent в `argLine`:
```xml
<argLine>-javaagent:${settings.localRepository}/org/aspectj/aspectjweaver/${aspectj.version}/aspectjweaver-${aspectj.version}.jar</argLine>
```

Для Gradle тот же AspectJ agent подключается в `test { jvmArgs "-javaagent:<путь к aspectjweaver jar>" }`.
