---
description: Утвердить spec фичи после G2 - записать хэш spec, создать карточки stories, фича в Ready for Dev
agent: orchestrator
---
Человек утверждает spec фичи $ARGUMENTS.

Загрузи skills `board` и `quality-gates`. Выполни раздел «Утверждение». Откажи с причиной,
если фича не в Analysis, последний G2 не PASS или spec не закоммичена на feature-ветке.

В ответе: `spec_sha`, список созданных stories (id, название, AC, зависимости).
Режим `github`: push фичи и новых карточек.
