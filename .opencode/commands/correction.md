---
description: Создать correction к реализованной/утверждённой story без изменения старых specs.
agent: orchestrator
---
Аргументы: $ARGUMENTS — <id исходной story-карточки> <требуемое изменение поведения>.

Загрузи board и write-spec. Прочитай исходную story, master и интегрированные corrections.
Определи действующие AC и проверь дубли correction. Если код нарушает действующие AC,
создай bug с repro/expected/actual; если ожидаемое поведение изменяется — новую карточку
story, work_kind correction, origin_story, parent feature, Backlog. Сформулируй старое → новое,
причину, затронутые AC и вопросы. Старые файлы и Done-карточки не меняй.

Spec ID C<N> зарезервируй без повторного использования. Файл correction создаст analyst
после /sprint add; Analysis → G2 → /approve <correction-id> обязательны. Для завершённой
feature используй отдельную ветку изменения и PR; для текущей — её integration branch.
Ответ: card ID, spec ID, исходная story, следующий шаг /sprint add <id>. Режим github: sync карточки.
