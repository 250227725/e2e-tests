---
description: Интерактивно настроить роли и подготовленные сессии
---

Используй @.opencode/instructions/role-configuration.md и @.opencode/instructions/documentation-authoring.md (раздел «Интерактивный режим»).
Используй @.opencode/scripts/document_authoring.py.

Настрой добавление, изменение или удаление роли в `docs/roles.md`, строго по правилам `role-configuration.md`: формат реестра, независимая подготовка каждой роли, обновление setup-файла и `playwright.config.ts`, проверка существования Action через `document_authoring.py check-roles`.

Не изменяй TC или Action документы. Не выполняй эту команду как часть `/edit-aa` или `/edit-tc` — только по прямому запросу.
