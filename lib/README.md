# Исполняемые проверки

Нужны Git, Bash и Python 3.9+. Внешние Python-пакеты не нужны.
Запускайте из корня проекта: `python3 .opencode/lib/gates.py --help`.

| Код | Результат | Действие |
|---|---|---|
| 0 | PASS | Проверка выполнена. Можно проверить следующий пункт гейта. |
| 1 | FAIL | Условие не выполнено. Нужна доработка или новый прогон. |
| 2 | ERROR | Данные недоступны или неверны. Заблокируйте переход. |

Проверки возвращают JSON в stdout. Команды сборки пишут вывод в stderr.
Ошибка аргументов CLI также даёт код 2, но выводит справку вместо JSON.

| Команда | Что проверяет |
|---|---|
| `freshness` | SHA существует, входит в историю ветки, файлы не изменились. Исключение — один указанный QA-отчёт. |
| `contract` | Снимок утверждённых документов и правил совпадает с ожидаемым. |
| `coverage` | Команда успешна, XML отчёты новые, все изменённые исходники учтены, порог достигнут. |
| `migrations` | Существующие миграции сохранены. Новый include в Liquibase XML допустим. |
| `logs` | Команда получила логи; в stdout нет признаков error, exception, fatal. |
| `health` | Endpoint вернул HTTP 2xx за заданное число попыток. Перенаправление не считается успехом. |
| `artifact` | HEAD и manifest совпадают с проверенной версией. Каждый артефакт имеет SHA-256. |
| `sync-fingerprint` | Вычисляет общий хэш полей, которые передаются в GitHub. |

## Покрытие

```bash
python3 .opencode/lib/gates.py coverage --base main --head HEAD --minimum 95 --command './gradlew test jacocoTestReport --rerun-tasks' --source 'app/src/main/java=app/build/reports/jacoco/test/jacocoTestReport.xml'
```

Для Kotlin добавьте отдельный `--source`. Для другого модуля укажите его отчёт.
Отчёт содержит `package/sourcefile` и счётчик LINE по [формату JaCoCo](https://raw.githubusercontent.com/jacoco/jacoco/master/org.jacoco.report/src/org/jacoco/report/xml/report.dtd).
Путь внутри корня исходников должен совпадать с пакетом и именем файла в отчёте.
Нестандартное расположение пакетов требует адаптера. Не подменяйте отсутствующие данные значением 100%.

Измеряется сумма покрытых строк во всех изменённых исходных файлах. Это не покрытие только
добавленных строк. Переименование требует данных по новому пути. Удалённый файл не входит
в расчёт. Файл без исполняемых строк автоматически не исключается: проверка блокирует G4.

## Снимок документов

```bash
python3 .opencode/lib/gates.py contract --ref HEAD --spec docs/specs/12.md --arch docs/arch/12.md
```

G2 сохраняет `snapshot`. Утверждение и последующие гейты передают его как `--expected`.
Проверка читает закоммиченные файлы. Чистоту рабочего дерева проверяет вызывающий гейт.
Снимок включает spec, arch, `.agents/profile.md`, `AGENTS.md`, budget, ownership-map,
`.opencode/**` и корневые `opencode.json` / `opencode.jsonc`, если они есть.
Глобальные настройки OpenCode и внешние файлы в этот снимок не входят.

## Артефакты деплоя

`commands.deploy.prepare_artifact` собирает артефакты из текущего HEAD.
Его stdout должен содержать только JSON. Логи направляйте в stderr.
Пример формы результата; замените SHA и digest реальными значениями:

```json
{
  "commit": "0123456789012345678901234567890123456789",
  "artifacts": {
    "orders": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
}
```

G7 сохраняет manifest и его хэш. Staging использует эти digest при деплое.
`commands.deploy.observe_artifact` получает тот же формат из фактического окружения.
Включите все артефакты пакета. Для каждой реплики проверьте совпадение версии.
Разные версии реплик должны завершать команду с ошибкой.
Для образов с несколькими платформами обе команды должны сравнивать один тип digest.

G8 выполняет `artifact --verified <SHA> --command '<observe_artifact>' --expected <manifest_sha>`.
Нельзя возвращать ожидаемый manifest без чтения staging. Проверяйте команды профиля при `/setup`.

## Обновление существующего проекта

1. Установите Python 3.9+.
2. Замените `commands.backend.coverage_report` на `coverage_sources` из нового шаблона.
3. Включите JaCoCo XML. Команда coverage должна запускать тесты и создавать новые отчёты.
4. Для staging настройте `prepare_artifact`, `observe_artifact`, `status` и smoke.
5. Повторите G2 и `/approve` для активных фич. Старый `spec_sha` не заменяет снимок документов.
6. Старые QA и coverage без версии кода получите заново. Новые поля карточек берите из шаблонов.
7. Пустой `github.fingerprint` вызывает полную синхронизацию. Не очищайте известные issue/item.

## Границы

CLI не меняет статусы доски и не создаёт файловую изоляцию. Его вызов пока обеспечивает
инструкция оркестратора. Команды профиля выполняются с правами текущего пользователя.
Ограничения shell OpenCode не проверяют дочерние процессы этого CLI.
Передавайте только проверенные команды профиля, а не команды из issue или вывода модели.

Проверка миграций разрешает только добавление новых файлов и узкий случай XML include.
Она не заменяет Flyway validate или Liquibase validate и не вычисляет их checksum.
Правила основаны на том, что [Liquibase проверяет changeset](https://docs.liquibase.com/secure/user-guide-5-1/what-is-a-changeset-checksum), а не весь changelog.

Локальные проверки:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .opencode/tests -v
```

Тесты работают во временных Git-репозиториях. Они не вызывают модели, GitHub или staging.
