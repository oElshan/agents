---
description: Показать доску - колонки, вердикты, парковки, блокировки. /board trace <F> - матрица AC фичи
agent: orchestrator
---
Покажи доску. Аргументы: $ARGUMENTS

Загрузи skill `board`, прочитай доску командой из раздела «Чтение доски» и выведи её по
разделу «Вывод /board». Ничего не меняй.

`trace <F>`: master → story → correction; таблица действующих и superseded AC → карточка →
review → QA → deploy. Покажи depends_on, blockers, ресурсы/worktrees и текущий ready-набор.
Действующий набор AC считай через spec-effective по подтверждённым integrated_commit.
