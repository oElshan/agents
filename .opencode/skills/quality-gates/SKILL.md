---
name: quality-gates
description: Гейты G1–G8 и гейт фичи. Проверки SHA, утверждённых документов, покрытия JaCoCo XML, миграций и артефактов. Подготовка веток и обработка ошибок.
---

# Гейты

Гейт проверяет оркестратор сам. Каждый пункт подтверждается выводом команды, который ты
получил в этой сессии, или строкой отчёта субагента с SHA. Итог гейта: `PASS`, `FAIL`
(вернуть на доработку) или `PARK` (нужен человек). Результат записывается в карточку
(skill `board`, раздел «Запись»).

Обозначения: `<F>` фича, `<S>` story или задача, `<base>` ветка, от которой создана ветка
story (feature-ветка или default branch), `<story>` ветка story, `<default>` =
`project.default_branch` из профиля.

## Общие проверки

Исполняемые проверки: `python3 .opencode/lib/gates.py <проверка>`. Запускай из корня
проекта. Нужен Python 3.9+. Результат — JSON. Код 0 = PASS, 1 = FAIL, 2 = ERROR.
Проверяй и код завершения, и поле `status`. ERROR блокирует переход: `PARK human`.
Пустой вывод, отсутствующая команда и ошибка Git не означают PASS.
Команды из профиля передавай одним аргументом. Сохраняй буквальные символы и кавычки.

**Чистое дерево** перед любым `git switch` и в G4:
```bash
git status --porcelain
```
Пусто: можно. Иначе остановись и перечисли файлы.

**Свежесть ревью, покрытия и QA**:
```bash
python3 .opencode/lib/gates.py freshness --verified <sha> --head <story> --qa-report <docs/qa/отчёт.md>
```
Исключение — только указанный обычный файл отчёта. Изменение тестов отменяет вердикты.
Неизвестный SHA даёт ERROR. Коммит вне истории ветки даёт FAIL.

**Утверждённые документы**:
```bash
python3 .opencode/lib/gates.py contract --ref <branch> --spec <spec> --arch <arch> --expected <approved_snapshot>
```
Снимок включает spec, arch, профиль, AGENTS.md, budget, ownership-map и все файлы `.opencode`.
Проверяй снимок feature-ветки и рабочей ветки перед G3, G4, G6, G7 и перед PR.
Нет снимка или он изменился: `PARK human`, причина «документы изменены; нужен /approve <F>».
Чистое дерево обязательно. Незакоммиченные документы нельзя утверждать.

**Миграции**: инструмент и пути бери из профиля. Для каждого пути передай `--path`.
```bash
python3 .opencode/lib/gates.py migrations --base <base> --head <story> --tool <flyway|liquibase> --path ':(glob)**/db/migration/**' --path ':(glob)**/db/changelog/**'
```
Flyway: существующие файлы неизменны. Liquibase: можно добавить в конец XML master
`include` нового файла. Существующие узлы и файлы неизменны. Подробности: `db-migration`.
`migration_tool: none` допустим только при отсутствии изменений в путях миграций.

**Покрытие изменённых исходных файлов**: JaCoCo XML, счётчик LINE.
```bash
python3 .opencode/lib/gates.py coverage --base <base> --head <story> --minimum <порог> --command '<commands.backend.coverage>' --source '<root>=<report>'
```
Повтори `--source` для каждой записи `commands.backend.coverage_sources`.
Проверка сама запускает команду. Команда должна заново создать отчёты и запускать тесты.
Ошибка команды, старый отчёт или отсутствующий файл блокируют G4.
Источник сопоставляется по пакету и имени файла. Модули используют отдельные отчёты.
Нет изменённых Java/Kotlin исходников: `applicable: false`, можно записать `n/a@<sha>`.
При изменении исходников пустая команда запрещена. Файл без данных LINE также блокирует G4.

**TODO без ссылки** в добавленных строках:
Сначала получи `git diff <base>...<story>` и проверь код завершения Git.
Затем проверь добавленные строки. Формат ссылки: `TODO(123)`, `TODO(#123)` или `TODO(PROJ-123)`.

## G1 · Sprint → Analysis (feature)

Проверки:
- в карточке есть бизнес-ценность и хотя бы высокоуровневые критерии, задан `priority`;
- нет дубля среди карточек и spec (`grep -il` по ключевым словам);
- дерево чистое.

Действия: `git switch <default>`, затем `git switch -c feature/<F>-<slug>` (если ветка уже
есть: `git switch feature/<F>-<slug>`). В карточку: `branch`, `spec: docs/specs/<F>-<slug>.md`,
`arch: docs/arch/<F>-<slug>.md`, `qa_doc: docs/qa/<F>-<slug>.md`, статус Analysis.
Нет бизнес-ценности: FAIL, карточка остаётся в Sprint, спроси человека.

## Analysis

1. analyst (шаблон ниже) → отчёт `ANALYST DONE`.
2. architect → отчёт `ARCHITECT DONE`. `BLOCKED: spec неполная` → снова analyst с этим списком.
3. G2.

## G2 · Analysis → Ready for Dev (feature)

На чистой feature-ветке сначала вызови `contract` без `--expected`. Сохрани начальный
`snapshot`. После чек-листа повтори вызов. Снимки должны совпасть.

Проверки на feature-ветке:
- spec содержит обязательные разделы шаблона (skill `write-spec`);
- AC: заголовки `### AC-<F>-NN`, ID уникальны, у каждого Given/When/Then и строка
  `Проверка: stand | integration | unit`:
  ```bash
  grep -oE '^### AC-<F>-[0-9]+' <spec> | sort | uniq -d          # дубли: должно быть пусто
  grep -cE '^### AC-<F>-[0-9]+' <spec>; grep -c '^Проверка:' <spec> # числа равны
  ```
- SDC: восемь слотов, в каждом решение или `N/A: <причина>`; либо весь блок
  `SDC: N/A — <причина>`, если фича под это подпадает (skill `sdc`);
- «Декомпозиция»: каждый AC фичи покрыт хотя бы одной story, у каждой story есть AC,
  размер xs, s или m, зависимости ссылаются на существующие ключи и не образуют цикл;
- arch doc есть и содержит разделы шаблона (skill `design-change`);
- новый модуль, сервис, очередь или внешняя интеграция при пороге из `budget.md`: в arch doc
  есть ADR; новые таблицы, очереди, endpoints внесены в `ownership-map.md`;
- изменения закоммичены, дерево чистое.

FAIL: снова analyst или architect с перечнем замечаний. После `quality.fix_loop_max` неудачных
G2 подряд: `PARK attempts`.

PASS:
- запиши `g2_snapshot` из результата `contract` вместе с G2 PASS;
- `gates.spec_approval: human` (по умолчанию): `parked: human`, причина «ждёт /approve <F>».
  Человеку выведи: путь к spec, число AC и stories, ADR, открытые вопросы analyst.
- `gates.spec_approval: auto`: сразу выполни шаги утверждения ниже.

## Утверждение (`/approve <F>` или auto)

**Первое утверждение**, фича в Analysis:

1. Проверь последний G2 PASS и чистое дерево. Вызови `contract --expected <g2_snapshot>`
   на feature-ветке. Несовпадение: повтори G2 и запроси новое утверждение.
2. Запиши `approved_snapshot = g2_snapshot`, `spec_sha` из результата проверки и дату `approved`.
   Сними парковку.
3. Создай карточки stories по таблице «Декомпозиция» (skill `board`).
4. Фича → Ready for Dev.

**Повторное утверждение**, фича в Ready for Dev или In Development, а снимок документов
не совпадает с `approved_snapshot`:

1. Проверь изменённую spec по чек-листу G2, без analyst и architect. FAIL: откажи и перечисли
   замечания, spec правит человек.
2. Обнови `g2_snapshot`, `approved_snapshot`, `spec_sha` и `approved`.
3. Сверь таблицу «Декомпозиция» с карточками фичи по `spec_key`:
   - строка без карточки: создай story в Ready for Dev;
   - у незавершённых stories обнови `ac`, `deps`, `priority`, `size`. Очисти `review`,
     `coverage`, `qa`, `qa_report_commit`, `deploy_commit`, `artifact_manifest_sha` и `deploy`.
     Начатые stories верни в In Development. Это нужно и при изменении текста AC без смены ID;
   - строка удалена: поставь `excluded: true`, `parked: human`, причина «story исключена из spec».
     Не запускай её. Сохрани карточку и историю. Возврат строки снимает `excluded`;
   - Done не переоткрывай автоматически. Перечисли такие stories человеку. Регрессия
     проверит новые AC. Если изменённый код нужно удалить, создай отдельную задачу.
4. Сними только парковки по дрейфу документов у stories с `excluded: false`.
   Запрети утверждение, если зависимость активной story указывает на исключённую story.
5. В журнал: `повторно утверждена · approved_snapshot <старый> → <новый>`.

## G3 · Ready for Dev или Sprint → In Development

Проверки:
- нет другой активной story (In Development, Code Review или Testing без парковки);
- все `deps` в Done;
- у story фичи: фича утверждена, снимок документов совпадает, `excluded: false`, каждый AC есть в spec;
- у самостоятельной задачи: в теле карточки есть AC с ID и строкой «Проверка»;
- дерево чистое.

Действия:
- `git switch <base>` и сборка базы `commands.backend.build` (и frontend build затронутых
  приложений). Сломана: `PARK human`, причина «база не собирается», вывод в журнал.
- `git switch -c story/<S>-<slug>`. Если ветка уже есть, это возобновление (раздел ниже).
- В карточку `branch`, статус In Development. Если родительская фича в Ready for Dev, переведи
  её в In Development.
- Запусти developer.

## Возобновление story

Story после парковки или после ожидания, пока шла другая story, могла отстать от базы.

1. `git switch <story>`, затем:
   ```bash
   git merge-base --is-ancestor <base> <story> && echo up-to-date
   ```
2. Отстала: `git merge --no-ff <base> -m "merge(<S>): update from <base>"`.
   - Конфликт: merge не прерывай, статус In Development, запусти developer с задачей
     «разреши конфликты» (шаблон developer, последняя строка).
   - Без конфликта: вердикты ревью и QA устарели. Статус In Development и сразу G4 без
     developer: если G4 PASS, story идёт в Code Review заново.
3. Не отстала: продолжай с текущего статуса.

## G4 · In Development → Code Review

Developer вернул `BLOCKED`: `PARK human` с его причиной.

Проверки на ветке story:
- дерево чистое, есть коммиты `git log --oneline <base>..<story>`;
- применённые миграции не тронуты;
- сборка и lint: `commands.backend.build`, `commands.backend.lint` (если задан), для
  затронутых frontend-приложений `build` и `lint`;
- тесты: `commands.backend.test` (или `test_one_service` по каждому затронутому сервису),
  frontend `test` затронутых приложений; все SUCCESS;
- покрытие изменённых исходных файлов ≥ `quality.unit_coverage_min` (hotfix:
  `quality.hotfix_coverage_min`);
- нет TODO/FIXME без ссылки.

PASS: `coverage: <pct>@<sha>`, статус Code Review, сброс `review` в пустые значения.
FAIL: In Development, `attempts + 1`, замечания с выводом команд.

## Code Review (ревьюеры)

Delta: `git diff --name-only <base>...<story>`.
- security-reviewer: всегда;
- java-reviewer: есть файлы `*.java *.kt *.sql *.gradle *.kts pom.xml` или `src/main/resources/**`;
- frontend-reviewer: есть `*.ts *.tsx *.js *.jsx *.mjs *.cjs *.html *.scss *.css *.json`
  или файлы сборки в путях `stack.frontend[].path`.

Неприменимому ревьюеру сразу пиши `n/a`. Применимых запускай параллельно, несколькими
вызовами task в одном сообщении. `BLOCKED: SHA изменился` → запусти этого ревьюера заново.

## G5 · Code Review → Testing

Проверки:
- `review.security` = `PASS@<sha>`;
- `review.java` и `review.frontend` = `PASS@<sha>`, `WARNING@<sha>` или `n/a`;
- все SHA свежие;
- `git status --porcelain` пуст и `git rev-parse HEAD` равен `<sha>` ревью.

PASS: статус Testing. MEDIUM/LOW находки запиши в журнал как tech-debt: они попадут в PR.
FAIL: In Development, `attempts + 1`, каждая CRITICAL/HIGH находка в замечания.
Дерево грязное или HEAD сдвинулся после ревью: `PARK human`, в причину вывод
`git status --porcelain`. Ревьюерам запрещён `edit`, но перенаправление `>` в shell OpenCode
не блокирует. Эта проверка обнаруживает изменения отслеживаемых файлов, но не защищает
игнорируемое состояние `.agents/board`. Изоляция файлов требует отдельного механизма.
Откат решает человек.

## G6 · Testing → merge → Ready to Deploy или Done

Проверки:
- tester вернул `VERDICT: PASS`; `Tested commit` — версия кода до записи QA-отчёта;
- `Report commit` равен HEAD. Проверка `freshness` от `Tested commit` до HEAD даёт PASS
  с исключением только точного пути отчёта;
- в отчёте `AUTOTESTS ... SUCCESS` и `BUILD ... SUCCESS`;
- ревью и покрытие свежие по проверке `freshness`; утверждённый снимок совпадает;
- QA-документ закоммичен.

`FAIL`: In Development, `attempts + 1`, в замечания каждый проваленный AC с repro, expected,
actual.
`NOT_VERIFIED`: `PARK human`, причина из отчёта (что нужно для стенда). После `/unpark`
story снова идёт в Testing.
`ERROR`: `PARK human`, причина — ошибка инструмента. Без исправления проверки merge запрещён.
`REVIEW_REQUIRED`: tester добавил тесты. Верни story в In Development, очисти старые
вердикты и выполни G4 → ревью → QA. Developer нужен только при провале G4.
Этот возврат сам по себе не увеличивает `attempts`.

PASS:
- story фичи: `git switch <feature-branch>`, `git merge --no-ff <story> -m "merge(<S>): <title>"`.
  Конфликт: `git merge --abort`, `PARK conflict`. После мёржа `git branch -d <story>`.
- самостоятельная задача: не мёржится, PR откроется после Done.
- запиши `qa: PASS@<tested_commit>` и `qa_report_commit: <report_commit>`;
- если задан `commands.deploy.staging`: Ready to Deploy. Пауза сохраняет этот статус;
- если staging не настроен: Done.

## G7 · Ready to Deploy → Deploy

Пакет: все карточки в Ready to Deploy одной ветки (feature-ветка или ветка задачи).

Проверки:
- стадия deploy включена. На паузе пакет остаётся в Ready to Deploy;
- снимок документов совпадает с утверждённым;
- у каждой карточки пакета `qa: PASS@<sha>`, и этот коммит входит в ветку деплоя:
  `git merge-base --is-ancestor <sha> <branch>` (ветка story после мёржа уже удалена,
  поэтому проверяется вхождение, а не свежесть);
- на HEAD ветки зелёные `commands.backend.build` и `commands.backend.test` (один прогон на пакет);
- дерево чистое.

Подготовь артефакты из этого HEAD:
```bash
python3 .opencode/lib/gates.py artifact --verified <sha> --command '<commands.deploy.prepare_artifact>'
```
Команда возвращает JSON: `commit` и `artifacts` (имя сервиса → `sha256:<64 hex>`).
Пустая команда блокирует деплой. Сохрани `manifest` в `.agents/cache/deploy-manifest.json`,
а `manifest_sha` и SHA кода — в полях `artifact_manifest_sha` и `deploy_commit` карточек.
`commands.deploy.staging` должен читать этот manifest и использовать точные digest.
PASS: карточки пакета → Deploy. Передай devops SHA, manifest и его хэш.

## G8 · Deploy → Done

Проверки по отчёту devops:
- `VERDICT: PASS`, деплой и раскатка OK, health каждого сервиса OK, smoke OK, логи чистые;
- HEAD равен `deploy_commit`, дерево чистое. Код и конфигурация после G7 не менялись;
- `artifact` с `commands.deploy.observe_artifact` и `--expected <artifact_manifest_sha>`
  дал PASS. Проверка получила digest из staging после всех откатов и повторного деплоя;
- репетиция отката выполнена, либо `skipped` с причиной: нет `commands.deploy.rollback` или
  SDC #4 = forward-only;
- kill switch проверен, если заявлен в SDC #7.

PASS: каждой карточке пакета `deploy: staging@<sha>`, статус Done.
FAIL или BLOCKED: карточки остаются в Deploy, `PARK human`, причина и вывод devops в журнал.
Нужна правка проекта: отдельная story с G4, ревью и QA. Затем повтори G7 для нового SHA.

## Гейт фичи · все stories в Done

Проверки:
- все карточки с `parent: <F>` и `excluded: false` в Done;
- утверждённый снимок совпадает с документами на feature-ветке;
- на HEAD feature-ветки `commands.backend.build` и `commands.backend.test` зелёные;
- tester в режиме `regression`: все AC фичи на HEAD feature-ветки.

Регрессия упала: на каждый сломанный AC создай баг в Sprint (skill `board`), фича остаётся
In Development. Tester вернул FAIL, потому что не поднялся стенд: баги не создавай, `PARK
human` с выдержкой логов из отчёта. Отдельной story, которую можно вернуть на доработку, у
фичи здесь нет.
`REVIEW_REQUIRED` при регрессии: запаркуй фичу. Добавленные тесты должны пройти G4,
применимые ревью и повторную регрессию на feature-ветке. До этого PR запрещён.
`ERROR` или `NOT_VERIFIED` при регрессии: `PARK human`. PR запрещён.

PASS: draft PR (ниже). PR создан: фича → Done, поле `pr`. PR не создан (нет `gh` или remote,
человек отклонил push): фича остаётся In Development, `PARK human`, причина «PR не создан:
<почему>», в журнал `гейт фичи PASS@<sha>`. После `/unpark`, если HEAD feature-ветки всё ещё
`<sha>`, повтори только раздел «Draft PR», без регрессии.

## Spike

Исследование без продуктового кода. Из Sprint: ветка `story/<id>-<slug>` от `<default>`,
статус In Development, developer с задачей «исследование по карточке, результат в
`docs/spikes/<id>-<slug>.md`: вопрос, варианты, вывод, рекомендация; продуктовый код не
менять». Проверка: документ закоммичен, `git diff --name-only <default>...<story>` содержит
только `docs/spikes/`. PASS: Done и draft PR. Иначе FAIL с замечаниями.

## Draft PR

Повтори проверку снимка документов. Проверь свежесть последнего QA от `Tested commit`
до HEAD с исключением только его файла отчёта. Изменение тестов или кода требует нового QA.

Тело PR собери в `.agents/cache/pr-<id>.md`: ссылка на spec и arch doc, stories с вердиктами
ревью и QA, таблица AC → story → QA, tech-debt (MEDIUM/LOW находки), покрытие, статус staging,
план отката из spec, что не проверено.

```bash
gh auth status && git remote get-url origin
git push -u origin <branch>                      # подтверждает человек
gh pr create --draft --base <default> --head <branch> --title "<id>: <title>" --body-file .agents/cache/pr-<id>.md
```
Нет `gh` или remote: PR не создавай, выведи человеку путь к файлу с описанием и команды выше,
фичу запаркуй по разделу «Гейт фичи».
Самостоятельная задача после Done получает PR так же, из своей ветки в `<default>`.

## Шаблоны задач для субагентов

Подставь значения. Тексты карточек передавай путём к файлу, не пересказом.

**analyst**
```
Spec для фичи <F> «<title>».
Карточка: .agents/board/<F>.md
Ветка: feature/<F>-<slug> (активна). Spec: docs/specs/<F>-<slug>.md
Замечания G2: <список или «нет»>
Верни отчёт ANALYST.
```

**architect**
```
Arch doc для фичи <F> «<title>».
Spec: docs/specs/<F>-<slug>.md. Arch doc: docs/arch/<F>-<slug>.md
Ветка: feature/<F>-<slug> (активна). Замечания G2: <список или «нет»>
Верни отчёт ARCHITECT.
```

**developer**
```
Story <S> «<title>». Карточка: .agents/board/<S>.md
Ветка: <story> (активна), база: <base>. AC: <AC-…>
Spec: <путь или «AC в карточке»>. Arch doc: <путь или «нет»>
Попытка: <attempts + 1>. Замечания к исправлению: <раздел карточки или «нет»>
<если идёт merge с конфликтами: «Идёт merge <base> в <story>, конфликты: <файлы>. Разреши и закоммить.»>
Верни отчёт DEVELOPER.
```

**security-reviewer / java-reviewer / frontend-reviewer**
```
Ревью story <S> «<title>».
Ветка: <story>, база: <base>, SHA: <sha>
Diff: git diff <base>...<story>
Spec (для SDC): <путь или «нет»>. AC story: <AC-…>
Верни отчёт <SECURITY|JAVA|FRONTEND> REVIEW.
```

**tester**
```
QA story <S> «<title>».
Ветка: <story> (активна), SHA: <sha>. AC: <AC-…>
Где AC: <spec или карточка>. QA-документ: <docs/qa/…>
Режим: story | regression (все AC фичи на HEAD <feature-branch>)
Верни отчёт QA REPORT.
```

**devops**
```
Деплой на staging. Ветка: <branch> (активна), SHA: <sha>.
Карточки в пакете: <id, …>. SDC #4/#7 фичи: <spec или «нет»>.
Manifest: .agents/cache/deploy-manifest.json. Manifest SHA: <artifact_manifest_sha>.
Верни отчёт DEPLOY REPORT.
```
