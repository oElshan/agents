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

**Утверждённые документы и граф**:
```bash
python3 .opencode/lib/gates.py spec-graph --ref <branch> --spec <unit-spec> --baseline <frozen_ref>
python3 .opencode/lib/gates.py contract --ref <branch> --spec <unit-spec> --arch <unit-arch> --expected <approved_snapshot>
```
Первый вызов сохраняет неизменность ранее утверждённых spec. `frozen_ref` никогда не
перезаписывается при переутверждении профиля/архитектуры. Для нового узла G2 вызывает
spec-graph без baseline и отдельно проверяет замороженные основания по их frozen_ref.
Снимок story/correction включает её файл, предков, зависимости, arch, профиль и правила;
снимок master — master и исходные stories. Соседние stories не входят в контракт story.
Проверяй контракт конкретной карточки на integration base и в её worktree перед G3/G4/G6/G7/PR.
Нет снимка или изменились профиль/архитектура: PARK human, нужен G2 и `/approve <id>`.
Изменение frozen spec нельзя легализовать повторным approve: требуется correction.
Незакоммиченные документы нельзя утверждать; дерево соответствующего worktree чистое.
Самостоятельные bug/tech-debt без spec используют AC карточки и существующие проверки;
это исключение не распространяется на новый функционал.


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
есть: `git switch feature/<F>-<slug>`). В карточку: `branch`, `spec: docs/specs/F<F>-<slug>/master.md`,
`arch: docs/arch/<F>-<slug>.md`, `qa_doc: docs/qa/F<F>/regression.md`, статус Analysis.
Нет бизнес-ценности: FAIL, карточка остаётся в Sprint, спроси человека.

## Analysis

Фича: analyst создаёт master + отдельные story-файлы, architect проверяет контракты и DAG.
Correction из Sprint: выбери её integration branch. Если feature не завершена — feature-ветка;
если feature Done — новая `change/<spec-id>-<slug>` от default, историческую feature не меняй.
Done означает draft PR, а не релиз: сначала проверь, что исходная реализация и specs
попали в default. Если PR ещё не смёржен — PARK deps. При squash используй подтверждённый
merge SHA исходного PR и сопоставление spec-файлов/реализации, сохрани released_commit
и evidence в журнале. При проверке deps допускается этот SHA вместо integrated_commit.
Карточку correction переведи в Analysis; analyst пишет новый файл по correction-template,
architect — `docs/arch/<spec-id>.md`. Старые spec и arch остаются неизменными.
Анализ общих документов выполняй последовательно, без конкурирующего писателя в этом checkout.
BLOCKED → уточнение черновиков; затем G2. Standalone функционал сначала получает feature.

## G2 · Analysis → Ready for Dev

На чистой ветке вызови `spec-graph --spec <master-or-correction>`, затем `contract` без expected.
Для каждого ранее утверждённого основания выполни spec-graph с его frozen_ref. После ручной
проверки повтори contract: снимок должен совпасть с первым вызовом.

Проверь:
- master имеет цель, общие ограничения, FR и минимум одну story; каждый FR покрыт ссылкой;
- каждая story/correction — отдельный файл по шаблону, свои AC/SDC/QA/откат;
- у каждого AC Given/When/Then и проверка stand/integration/unit; ID уникален и принадлежит узлу;
- DAG без циклов/битых ссылок; parent корректен; correction явно задаёт corrects/supersedes;
- writes/reads/resources полны (код, тесты, DTO, сборка, миграции, стенд), blockers объяснены;
- arch готов, ADR и карты ресурсов соответствуют требованиям; открытые вопросы, меняющие
  контракт, закрыты; числовые NFR и SDC проверены по write-spec/sdc/design-change;
- изменения закоммичены, старые specs не изменены.

FAIL → analyst/architect с замечаниями; после fix_loop_max — PARK attempts. ERROR → PARK human.
PASS → `g2_snapshot`, `g2_ref`. При human покажи дерево/AC/зависимости/возможные параллельные
группы и жди `/approve <id>`. При auto выполни те же проверки утверждения без ожидания.

## Утверждение (`/approve <id>` или auto)

1. Чистое дерево, G2 PASS и `contract --expected <g2_snapshot>` на том же наборе документов.
   Снимок сдвинулся — новый G2. Замороженные specs сверяются с прежним frozen_ref.
2. Первое approve feature: создай по карточке на каждый файл из master.stories (даже одну),
   `type: story`, Ready for Dev. Свяжи spec IDs с числовыми card IDs; не редактируй specs.
   Сохрани feature snapshot и отдельный contract snapshot для каждой story, а также
   собственные `g2_snapshot`/`g2_ref`, `approved_ref`, `frozen_ref`, `approved`, `spec_sha`, `spec`, `master_spec`, `spec_id`, `arch`,
   `qa_doc`, `deps`, `blockers`, `writes`, `reads`, `resources`. Feature → Ready for Dev.
3. Первое approve correction: обнови только её карточку, вычисли собственный contract,
   привяжи origin_story, prerequisites (parent + corrects + depends_on), новый arch и QA path.
   Correction → Ready for Dev. Исторические карточки и snapshots остаются прежними.
4. Повторное approve разрешено для профиля/архитектуры/правил, если все frozen specs неизменны.
   Сначала повтори G2 для затронутых узлов; обнови их approved_snapshot/approved_ref, сохраняя
   frozen_ref. Очисти review/coverage/QA/deploy незавершённых затронутых карточек; начатые
   верни в In Development. Done автоматически не переоткрывай, историю вердиктов сохрани.
   Feature approve не утверждает добавленные corrections: каждой нужен отдельный approve.
5. Сними только парковку по утверждению/дрейфу этого контракта. Запиши журнал и снимки.
   Удалять строки декомпозиции, менять AC или исключать утверждённую story повторным approve
   запрещено. Изменение scope — correction/новая feature; старые карточки сохраняются.


## G3 · Ready for Dev или Sprint → In Development

Проверки:
- есть свободный слот и нет конфликтов по `parallel-stories`; ресурс/checkout не занят;
- prerequisites интегрированы и их integrated_commit входит в выбранную базу;
- внешние blockers закрыты с evidence; spec-plan допускает задачу;
- story/correction утверждена, собственный снимок совпадает, frozen specs сохранены;
- `excluded: false`; AC взяты из своей spec; standalone bug/tech-debt имеют AC в карточке;
- дерево целевого worktree чистое.

Standalone bug/tech-debt без spec/v1 выполняй эксклюзивно, не параллельно другим писателям.

Действия: orchestrator резервирует ресурсы и создаёт выделенный worktree от `<base>` по
parallel-stories. Сохрани `base_commit`, проверь сборку базы в worktree; сломана — PARK human.
Передай developer абсолютный cwd, spec/master/arch, AC и области записи. Статус In Development.
Незавершённая родительская feature переходит в In Development при первой story. Для correction
выпущенной feature её исторический Done остаётся без изменений.


## Возобновление story

Story после парковки или после ожидания, пока шла другая story, могла отстать от базы.

1. В назначенном worktree проверь ветку `<story>` и чистоту; затем:
   ```bash
   git merge-base --is-ancestor <base> <story> && echo up-to-date
   ```
2. Отстала: orchestrator выполняет `git merge --no-ff <base> -m "merge(<S>): update from <base>"`.
   - Конфликт: merge не прерывай, статус In Development, запусти developer с задачей
     «разреши конфликты» (шаблон developer, последняя строка).
   - Без конфликта: вердикты ревью и QA устарели. Статус In Development и сразу G4 без
     developer: если G4 PASS, story идёт в Code Review заново.
3. Не отстала: продолжай с текущего статуса. После обновления базы запиши base_commit.
   Ресурсы повторно резервируются перед возобновлением; парковка не даёт обхода spec-plan.

## G4 · In Development → Code Review

Developer вернул WAIT_RESOURCE: оставь In Development/execution: waiting, выдай ресурс
после освобождения и возобнови task; attempts не меняй. G4 начинается после DONE.
Developer вернул `BLOCKED`: `PARK human` с его причиной.

Проверки в назначенном worktree story:
- `spec-scope --spec <unit-spec> --base <base_commit> --head <story> --qa-report <qa_doc>` PASS
  для story/correction с отдельной spec; выход за область — PARK human до согласования нового контракта;
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

Интегратор берёт единственную очередь merge. Если HEAD базы отличается от base_commit,
обнови story по «Возобновление story», сбрось старые вердикты и повтори G4 → ревью → QA.
Даже чистое слияние новой базы не сохраняет старый PASS. Повторно проверь базу сразу перед merge.

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
- story незавершённой фичи: в интеграционном checkout влей `<story>` в feature-ветку;
- correction выпущенной фичи: влей `<story>` в её `change/<spec-id>-<slug>`;
- merge только orchestrator: `git merge --no-ff <story> -m "merge(<S>): <title>"`.
  Конфликт: `git merge --abort`, PARK conflict; дальнейшее обновление делается в worktree story;
- запиши `integrated_commit`, проверь вхождение проверенного SHA в integration branch;
  сохрани `qa: PASS@<tested_commit>` и `qa_report_commit: <report_commit>`;
- освободи ресурсы/удали чистый worktree после завершения task, затем можно удалить story-ветку;
- standalone bug/tech-debt остаётся в своей ветке до PR;
- staging настроен → Ready to Deploy (пауза сохраняет статус); иначе → Done.

Для correction с завершённой feature после стадий выполни regression затронутой фичи на
change-ветке (effective AC с этой correction), затем отдельный draft PR в default. Done
без pr остаётся незавершённой финализацией для петли, даже если G6/G8 уже пройдены. Если PR
не создан — PARK human с причиной. Регрессия выявила дефект текущей correction — верни
её в In Development в восстановленном worktree с новой базой, очисти verdict и повтори
G4–G6; старую feature не открывай. Дефект прежнего поведения — отдельный bug с действующим AC.
NOT_VERIFIED/ERROR/REVIEW_REQUIRED обрабатывай как в гейте фичи. Только PASS и созданный PR
завершают цикл; исторические docs и карточки сохраняются.


## G7 · Ready to Deploy → Deploy

Пакет: все карточки в Ready to Deploy одной integration_branch (feature, change или задача).
На всё время G7/G8 зарезервируй deploy:staging и checkout этой ветки. Merge/анализ в него
запрещены до отчёта devops; другие story-worktrees могут продолжать независимую работу.

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
- все исходные stories master и все принятые в Sprint corrections/bugs этой integration_branch
  с `parent: <F>` и `excluded: false` в Done; новый Backlog-intake не расширяет scope текущего PR;
- все утверждённые контракты master/stories/включённых corrections совпадают; frozen specs неизменны;
- на HEAD feature-ветки `commands.backend.build` и `commands.backend.test` зелёные;
- tester в режиме `regression`: действующие AC интегрированных stories/corrections на HEAD.
  Собери их через `spec-effective --spec <master> --integrated <spec-id> ...`; передавай только
  spec ID с подтверждённым integrated_commit в этой ветке. superseded AC остаются историей.

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

Тело PR собери в `.agents/cache/pr-<id>.md`: дерево master → stories → corrections, ссылки на arch, stories с вердиктами
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

Подставь значения. Каждому task обязательно передай абсолютный cwd, ожидаемые branch/HEAD,
абсолютный путь центральной карточки, spec/master/arch, AC и writes/reads/resources. Агент
подтверждает корень/ветку/HEAD и адресует все инструменты этому cwd. Карточку передавай файлом.
Для tester/review correction передавай effective AC, для regression — подтверждённые integrated IDs.

**analyst**
```
Spec для фичи <F> «<title>».
Карточка: .agents/board/<F>.md
Ветка: feature/<F>-<slug> (активна). Master: docs/specs/F<F>-<slug>/master.md; story specs: <пути>
Замечания G2: <список или «нет»>
Верни отчёт ANALYST.
```

**analyst / architect для correction**
```
Correction <spec-id> к story <origin-story-id>. Карточка: <абсолютный путь>.
Cwd: <абсолютный checkout>; branch/HEAD: <ожидаемые значения>.
Master: <путь>. Исходная story: <путь>. Corrects: <пути>; supersedes: <AC IDs>.
Новый файл: <correction path>. Новый arch: docs/arch/<spec-id>.md.
Старые specs/arch не редактировать. Верни ANALYST / ARCHITECT с графом и границами записи.
```

**architect**
```
Arch doc для фичи <F> «<title>».
Master: docs/specs/F<F>-<slug>/master.md; story specs: <пути>. Arch doc: docs/arch/<F>-<slug>.md
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
Master / Story / Correction (для SDC): <пути или «нет»>. AC story: <AC-…>
Верни отчёт <SECURITY|JAVA|FRONTEND> REVIEW.
```

**tester**
```
QA story <S> «<title>».
Ветка: <story> (активна), SHA: <sha>. AC: <AC-…>
Где AC: <story/correction spec или карточка>; effective AC: <список>. QA-документ: <docs/qa/…>
Режим: story | regression (действующие AC фичи на переданном integration HEAD)
Верни отчёт QA REPORT.
```

**devops**
```
Деплой на staging. Ветка: <branch> (активна), SHA: <sha>.
Карточки в пакете: <id, …>. SDC #4/#7: <master + story/correction specs пакета>.
Manifest: .agents/cache/deploy-manifest.json. Manifest SHA: <artifact_manifest_sha>.
Верни отчёт DEPLOY REPORT.
```
