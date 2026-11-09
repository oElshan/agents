---
name: project-setup
description: Подключение проекта к агентной команде (/setup) - детект стека по файлам сборки, заполнение .agents/profile.md, создание AGENTS.md, docs/arch/budget.md и ownership-map.md, .gitignore, выбор режима доски local или github. Раздел «Детект» нужен любому агенту, если профиль не заполнен.
---

# Подключение проекта

Шаблоны лежат рядом: `templates/profile.md`, `templates/AGENTS.md`, `templates/budget.md`,
`templates/ownership-map.md`.

## Шаги `/setup`

1. **Проверки.** Доступен Python 3.9+. Это git-репозиторий (`git rev-parse --show-toplevel`), дерево чистое.
   Определи default branch: `git symbolic-ref --short refs/remotes/origin/HEAD` (без
   `origin/`), иначе текущая ветка; подтверди у человека и переключись на неё
   (`git switch <default>`). Если `.agents/profile.md` уже есть и `initialized: true`,
   покажи текущие значения и обновляй только то, что человек попросил.
2. **Детект** по таблице ниже. Команды бери из реальных файлов: wrapper (`./gradlew`,
   `./mvnw`) раньше глобальных, npm-скрипты из `package.json`, а не угаданные.
3. **Покрытие.** G4 читает JaCoCo XML. В Gradle нужен `xml.required = true`.
   В Maven нужен goal `jacoco:report`. Проверь фактический путь отчёта.
   Заполни `coverage_sources`: корень Java/Kotlin и отчёт каждого модуля.
   Команда coverage должна заново запускать тесты и создавать XML. Для Gradle проверь
   необходимость `--rerun-tasks`; для Maven — `clean verify`. Не используй старый отчёт.
   Если отчёт отключён, предложи правку build-файла. До настройки G4 для backend заблокирован.
4. **Профиль.** Скопируй `templates/profile.md` в `.agents/profile.md` и заполни. Покажи
   человеку итог одной таблицей (стек, команды, стенд, деплой, пороги) и спроси:
   - режим доски: `local` или `github`;
   - утверждение spec человеком (`gates.spec_approval`): `human` (по умолчанию) или `auto`;
   - параллельность stories (по умолчанию 2 worktrees), доступность изоляции cwd;
   - пороги покрытия, если 95/50 не подходят.
   Для isolated_test_env: true проверь уникальность портов, БД и compose names. Без этого
   разработка может идти параллельно, команды общего стенда — последовательно.
   После подтверждения поставь `initialized: true`, `updated`.
   Если staging включён, настрой `prepare_artifact`, `observe_artifact`, `status` и smoke.
   Команды артефактов возвращают формат из `.opencode/lib/README.md`.
   Staging должен использовать digest. Для Kubernetes нужен явный context и namespace.
5. **AGENTS.md.** Если файла нет, создай по `templates/AGENTS.md`: модули из структуры
   каталогов, домен из сущностей и README, роли из security-конфига. Есть `CLAUDE.md`:
   возьми знание оттуда. Есть `AGENTS.md`: допиши только раздел «Агентная команда».
6. **Карты.** `docs/arch/budget.md` и `docs/arch/ownership-map.md` из шаблонов, стартовое
   состояние сканом:
   - таблицы: имена из миграций (`CREATE TABLE`) или `@Table`/`@Entity`;
   - очереди и topics: `@KafkaListener`, `@RabbitListener`, конфиги брокера;
   - endpoints: `@RequestMapping`/`@GetMapping`… по контроллерам (префиксы);
   - внешние вызовы: `RestClient`, `WebClient`, `FeignClient`, `RestTemplate`.
7. **.gitignore.** Добавь строки, если их нет:
   ```
   .agents/board/
   .agents/cache/
   .agents/worktrees/
   ```
8. **Доска.** `mkdir -p .agents/board`. Режим `github`: выполни настройку из skill
   `github-sync`.
9. **Коммит** на default branch: `.agents/profile.md`, `AGENTS.md`, `docs/arch/*`,
   `.gitignore`: `chore: подключение агентной команды`.
10. **Итог** человеку: что найдено, что не удалось определить, следующий шаг
    (`/feature <описание>`).

## Детект

| Признак | Вывод |
|---|---|
| `gradlew`, `build.gradle(.kts)` | gradle: `./gradlew build -x test`, `./gradlew test`, покрытие `./gradlew test jacocoTestReport` |
| `mvnw`, `pom.xml` | maven: `./mvnw -q package -DskipTests`, `./mvnw test`, покрытие `./mvnw verify` |
| `settings.gradle` с несколькими `include`, несколько `pom.xml` | многомодульный: тесты модуля `./gradlew :{service}:test` или `./mvnw -pl {service} test` |
| `spring-boot` в build-файле | framework spring-boot, health `/actuator/health` |
| `sourceCompatibility`, `java.version`, `<java.version>` | версия Java |
| `angular.json` | frontend angular: `ng build`, `ng test --watch=false` |
| `package.json` с `react` | frontend react: скрипты из `package.json` |
| `pnpm-lock.yaml` / `yarn.lock` / `package-lock.json` | pnpm / yarn / npm |
| `src/main/resources/db/migration` | flyway |
| `liquibase` в build-файле, `db/changelog` | liquibase |
| `docker-compose*.yml`, `compose*.yml` | local_env: `docker compose up -d` / `docker compose down` |
| `Chart.yaml`, `helm/` | k8s helm |
| `kustomization.yaml` | k8s kustomize |
| манифесты с `kind: Deployment` | kubernetes |
| `.github/workflows/` | ci github-actions |
| `Testcontainers` в зависимостях, задача `integrationTest` | `integration_test` |

Агент, который нашёл незаполненный профиль во время работы, определяет команды по этой
таблице, работает по ним и пишет в отчёте: «профиль не заполнен, запустите /setup».
