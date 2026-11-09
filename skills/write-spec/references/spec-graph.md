# Формат spec/v1 и жизненный цикл

## Хранение

```text
docs/specs/F12-export/
  master.md
  stories/S1-csv.md
  stories/S2-download.md
  corrections/S1-C1-format.md
  corrections/S1-C2-format.md
```

Логическое дерево: master → story → correction. Последующая correction остаётся ребёнком
исходной story, а `corrects` ссылается на предыдущую correction. Пути и ID стабильны и не
зависят от номеров карточек. ID: F12, F12-S1, F12-S1-C1. Новые номера не переиспользуются.

Каждый файл содержит YAML frontmatter `schema: spec/v1`. CLI поддерживает небольшой
поднабор YAML: одно поле на строку, строки без кавычек или в двойных JSON-кавычках, массивы
только JSON flow (`[]`, `["value"]`). Не используй YAML anchors, вложенные блоки и комментарии
в конце строки. Это обычный YAML, читаемый Obsidian, без зависимости от Python-пакетов.

Связи — полные wikilinks от корня vault, без `.md`, alias и anchor во frontmatter:
`"[[docs/specs/F12-export/stories/S1-csv]]"`. В теле для навигации допустимы anchors и aliases.
Обычные Markdown-ссылки можно добавить для GitHub. Не полагайся на basename: master.md
встречается у разных фич. Обратные ссылки Obsidian выводит из новых файлов; старые не дописывай.

| Поле | Смысл |
|---|---|
| schema, id, kind, title | spec/v1; стабильный ID; master/story/correction; название |
| parent | null у master; wikilink на master у story, на исходную story у correction |
| stories | Только master: непустой список исходных story-спек |
| depends_on | Story/correction, список wikilinks на обязательные результаты; master: [] |
| blockers | Внешние условия, например `decision:csv-encoding`; закрытие хранится на доске с evidence |
| writes, reads | Буквальные пути от корня repo; каталог заканчивается `/`; glob запрещён |
| resources | Исключительные общие ресурсы, например `api:orders-export`, `db:orders`, `stand:shared` |
| corrects | Только correction: исходная story и/или предыдущая correction, чьё поведение меняется |
| supersedes | Только correction: ID старых AC из corrects, которые заменены её новыми AC |

`parent` — иерархия, `depends_on` — порядок, `resources` и пересечение writes/reads —
запрет одновременной работы, `blockers` — внешняя готовность. Ссылка сама по себе не
делает задачу зависимой. Независимые stories не должны редактировать общий master/arch/QA.
Общие тестовые fixtures, сборочные файлы и каталоги миграций тоже учитывай в writes/resources.

## Неизменяемость и утверждение

До первого утверждения analyst и architect могут дорабатывать черновики. G2 проверяет
master и все исходные stories; `/approve <F>` утверждает этот набор. Каждая карточка story
получает свой `approved_snapshot` и `approved_ref` (Git SHA), `spec`, `spec_id`, `master_spec`.
Master-контракт включает исходные stories; контракт story включает её саму, master и
транзитивные prerequisites. Соседние stories в него не входят. Все контракты также включают
arch, профиль и правила. Новая correction не меняет утверждение старых файлов.

Замораживание — с первого approve, не только после Done. Нельзя менять, переименовывать,
удалять или «актуализировать» старую spec даже новым approve. Реестр утверждений на доске
хранит исходный `frozen_ref`; переутверждение профиля/архитектуры не двигает этот SHA.
Проверяй `spec-graph --baseline <frozen_ref>` для каждого уже утверждённого узла.
Даты, статусы, SHA реализации, блокировки и результаты прогонов живут в карточках/QA,
а не во frontmatter specs. Не ставь задним числом status: done в spec.

## Correction

`/correction <story-card-id> <изменение>` создаёт новую карточку type: story, work_kind: correction,
с тем же parent feature и `origin_story` исходной карточки. Интейк в Backlog; пользователь
берёт её в Sprint как обычную story. Analyst создаёт отдельный correction-файл, architect —
дополнение `docs/arch/F12-S1-C1.md`, не переписывая прежний arch. G2 и `/approve <correction-card-id>`
проверяют только новый контракт и неизменность его оснований. Реализация всё ещё идёт через story.

Correction может быть подготовлена заранее, но запускается после интеграции исходной story
и всех `corrects`/`depends_on`. Для выпущенной фичи создаётся отдельная ветка изменения от
default branch с master как контекстом; завершённую feature/старые карточки не переоткрывай.
Draft PR этой correction идёт в default branch, с регрессией затронутой фичи. Для незавершённой
фичи correction входит в её feature-ветку и в гейт фичи.

Опиши старое → новое поведение, причину, заменяемые AC, новые AC, совместимость, проверку и
откат. Если C2 меняет результат C1, укажи `corrects: ["[[.../C1]]"]` и AC из C1 в `supersedes`.
Две несвязанные corrections одного AC запрещены: нужна явная последовательная цепочка.
Одновременные изменения разных AC допустимы при отсутствии конфликтов ресурсов.
Для удаления поведения новый AC проверяет отсутствие/отказ операции; старый AC не удаляется.

Действующие требования на SHA: исходные AC + AC только интегрированных corrections;
убери из активного набора `supersedes` этих corrections. Применяй их в топологическом порядке.
Утверждение correction само по себе не меняет поведение уже реализованной системы.
Неинтегрированные corrections не попадают в текущую регрессию. При QA самой correction
проверяется будущий набор: интегрированные предки + текущая correction.

## Исполняемые проверки

Из корня проекта, после коммита документов:

```bash
python3 .opencode/lib/gates.py spec-graph --spec docs/specs/F12-export/master.md
python3 .opencode/lib/gates.py spec-graph --spec docs/specs/F12-export/master.md --baseline <frozen_ref>
python3 .opencode/lib/gates.py contract --spec docs/specs/F12-export/stories/S1-csv.md --arch docs/arch/12-export.md
python3 .opencode/lib/gates.py spec-plan --spec docs/specs/F12-export/master.md --limit 2
python3 .opencode/lib/gates.py spec-plan --spec docs/specs/F12-export/master.md --completed F12-S1 --active F12-S2 --resolved-blocker decision:csv-encoding --limit 2
python3 .opencode/lib/gates.py spec-effective --spec docs/specs/F12-export/master.md --integrated F12-S1 --include F12-S1-C1
python3 .opencode/lib/gates.py spec-scope --spec docs/specs/F12-export/stories/S1-csv.md --base <integration-base> --head <story> --qa-report docs/qa/F12/S1.md
```

`spec-plan` возвращает ready и причины blocked. completed передаётся только после G6 и
проверки `integrated_commit` в базе конкретного запуска; Done в другой ветке недостаточно.
Если человек сделал squash исходного PR, сохрани released_commit подтверждённого merge
и evidence соответствия specs/реализации; проверяй его вхождение в default вместо старого
SHA story. frozen_ref продолжает указывать исходное утверждение: сравниваются blob, не история веток.
В рабочем запуске передавай только допущенные карточки через повторяемый `--candidate`.
Если кандидатов нет, не запускай волну. Без этого параметра CLI показывает весь граф.
План — рекомендация, не разрешение обойти Sprint, approve, stage pause или capacity. Перед
запуском сверяй карточки, снимки и занятые worktrees. Внешние blockers закрываются на доске
по evidence и передаются как resolved-blocker. Непустые blockers не редактируют старую spec.

CLI не создаёт worktrees и не владеет блокировками доски. Это делает один orchestrator
по [parallel-stories](../../parallel-stories/SKILL.md). Проверка scope обнаруживает выход
за заявленные файлы, но семантические конфликты API/данных требуют архитектурного ревью.

## Переход со старой монолитной спеки

Не дели и не перезаписывай исторический файл на месте. Сохрани его как legacy-источник.
На отдельном анализе создай новый master и story-файлы с `legacy_source` (путь старого файла)
и таблицей old AC → new AC, без изменения смысла. Иерархию проверь G2 и утверди. В карточках
сохрани прежние verdict/SHA в журнале; новые контрактные поля заполни явно. Не переносись на
новые ID «по совпадению названия», не объявляй новый QA PASS без проверки. Завершённым задачам
достаточно исторических ссылок; незавершённым нужны новые снимки и проверки.
Если нужно именно изменить уже реализованное поведение, после такой привязки создай correction.
Старый режим `contract` остаётся читаемым для legacy, но новые фичи требуют spec/v1.
