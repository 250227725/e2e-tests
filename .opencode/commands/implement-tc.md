---
description: Реализовать один утверждённый Test Case
---

Используй:

- @.opencode/instructions/test-development.md
- @.opencode/instructions/test-data-and-environment.md
- @.opencode/instructions/playwright-implementation.md
- @.opencode/instructions/selector-research.md
- @.opencode/instructions/diagnostics.md
- @.opencode/templates/blocked-report.md
- @.opencode/templates/completion-report.md
- @.opencode/templates/selector-specification.schema.json
- @.opencode/templates/selector-specification.example.json

Целевой Test Case: `$1`.

Выполни полный цикл исследования, реализации и проверки только указанного TC. Утверждённую документацию не изменяй (кроме как через `/edit-aa`/`/edit-tc`, вызываемые отдельно). Не запускай проверочные TC автоматически.

Цикл реализации включает: реализацию отсутствующих AA-зависимостей (`actions/AA-<CODE>.ts`), создание или обновление JSON-спецификации селекторов для TC и его AA (`document_authoring.py write-selectors`), затем реализацию самого TC — подробно в `test-development.md`, раздел «5. Реализация».
