---
description: Провести анализ фичи сейчас - G1, analyst, architect, G2 (без петли оркестратора)
agent: orchestrator
---
Проведи анализ фичи или correction-карточки $ARGUMENTS.

Загрузи skills `board` и `quality-gates`. Карточка должна быть в Sprint или Analysis. Если она в
Backlog, скажи, что сначала нужен `/sprint add`.

Выполни G1 для фичи в Sprint либо подготовку correction из раздела Analysis, затем Analysis и G2. Итог: вердикт G2, путь к spec
и arch doc, число AC и stories, ADR. Если нужна `/approve`, скажи это.
