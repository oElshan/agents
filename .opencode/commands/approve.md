---
description: Утвердить master со story-контрактами либо отдельную correction; старые specs неизменны.
agent: orchestrator
---
Человек утверждает контракт карточки $ARGUMENTS.

Загрузи board и quality-gates, выполни раздел «Утверждение». Нужен G2 PASS текущего снимка
на чистой ветке. Первое approve feature создаёт story-карточки со своими spec/snapshot;
approve correction утверждает только её. Повторный approve профиля/архитектуры не разрешает
менять frozen specs. Проверяй прежний frozen_ref и не перезаписывай его.

В ответе: дерево и пути, approved_snapshot, созданные карточки, зависимости и blockers,
какие задачи готовы параллельно. В режиме github синхронизируй изменённые карточки.
