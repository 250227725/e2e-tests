# Состав комплекта

## Команды

- `/create-aa` — создание нового AA.
- `/create-tc` — создание нового TC.
- `/research-tc` — исследование TC без реализации.
- `/implement-tc` — полный цикл реализации TC.
- `/run-tc` — изолированный запуск TC.

## Владельцы правил

- `AGENTS.md` — постоянные ограничения и маршрутизация.
- `documentation-authoring.md` — интерактивное создание документации.
- `test-development.md` — процесс исследования и реализации одного TC.
- `test-data-and-environment.md` — данные, окружение и контекст теста.
- `playwright-implementation.md` — архитектура Playwright-кода и проверки.
- `selector-research.md` — исследование интерфейса и локаторы.
- `diagnostics.md` — категории ошибок, статусы и отчётность.
- `.opencode/scripts/document_authoring.py` — проверка и атомарное создание новых AA/TC.
- `.opencode/templates/` — только формы документов и отчётов.

## Исполняемые команды

- `/create-aa` и `/create-tc` используют `.opencode/scripts/document_authoring.py` для инвентаризации, валидации и атомарной записи.

## Технические требования

- Opencode
- Python 3.10 или новее.
- Python-скрипты используют только стандартную библиотеку.
- Playwright Test установлен в целевом проекте.
- Playwright MCP сервис доступен
