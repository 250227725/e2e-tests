---
description: Интерактивно изменить существующую спецификацию Atomic Action
---

Используй правила из @AGENTS.md, @.opencode/instructions/documentation-authoring.md и @.opencode/instructions/playwright-implementation.md.
Используй структуру @.opencode/templates/atomic-action.md.

Целевой Atomic Action: `$1`.

1. Загрузи текущую утверждённую редакцию `docs/atomic-actions/AA-<CODE>.md`, покажи пользователю.
2. До начала диалога правки покажи блок-радиус изменения: выполни `document_authoring.py dependents --kind aa --id AA-<CODE>` (зависимые TC) и `document_authoring.py role-dependents --id AA-<CODE>` (роли, использующие эту AA — см. `role-configuration.md`). Покажи оба списка пользователю как контекст перед началом правки, даже если они пустые.
3. Веди диалог изменений по правилам «Интерактивного режима» из `documentation-authoring.md` (батчинг вопросов 3–5).
4. После согласования новой редакции подготовь полный текст и передай его через stdin в `python3 .opencode/scripts/document_authoring.py validate --kind aa --id AA-<CODE> --content-file - --mode update`.
5. Покажи полный прошедший проверку текст, запроси явное подтверждение именно этой редакции.
6. После подтверждения, но до записи: вычисли новые хэши (`document_authoring.py hash --kind aa --id AA-<CODE> --part signature` и `--part logic`), сравни с хэшами в существующем `actions/AA-<CODE>.ts` (если файла нет — пропусти этот шаг). Определи тип изменения и последствия по `playwright-implementation.md`, раздел «Редактирование AA и TC» → «`/edit-aa`»: удаление реализации самой AA и, при смене сигнатуры, реализаций зависимых TC (список уже получен на шаге 2). Роли (`docs/roles.md`) **не пересоздаются автоматически** — только фиксируются в отчёте на шаге 9.
7. Выполни удаления, определённые на шаге 6, **до** записи новой редакции документа.
8. Передай тот же текст в `python3 .opencode/scripts/document_authoring.py update --kind aa --id AA-<CODE> --content-file -`.
9. Сообщи: что изменено, какой тип изменения (сигнатура/логика/назначение), какие файлы удалены, какие TC потребуют повторного `/implement-tc`. Если менялась сигнатура — отдельно повтори список ролей из шага 2 как требующих ручной проверки разработчиком (`/configure-roles` при необходимости).

Не создавай новые TC/AA. Не изменяй документы, не являющиеся целью редактирования.
