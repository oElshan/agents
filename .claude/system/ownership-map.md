# Ownership Map — единый владелец на ресурс

Каждая таблица / очередь / endpoint / topic имеет ровно ОДНОГО владельца (модуль или
микросервис). Cross-module запись — только через API/event владельца. Прямой доступ к
чужой таблице запрещён (проверяет code-reviewer, SDC-01).

Обновляет **analyst** при создании нового ресурса в spec. `/init` заполняет стартовое
состояние сканом миграций/контроллеров/listeners.

## Таблицы БД

| Таблица | Owner (модуль/сервис) | Пишут | Читают |
|---|---|---|---|

## Очереди / Topics / Exchanges

| Ресурс | Producer (owner) | Consumers |
|---|---|---|

## API Endpoints (внешние контракты)

| Endpoint | Owner | Consumers |
|---|---|---|

## Shared contracts (DTO / Events)

| Контракт | Owner | Consumers (grep evidence при изменении) |
|---|---|---|
