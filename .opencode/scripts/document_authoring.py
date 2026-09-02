#!/usr/bin/env python3
"""Validate and atomically create/update approved AA/TC Markdown documents.

The script owns deterministic document-authoring checks. The OpenCode commands
remain responsible for the interactive dialogue and explicit user approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

AA_DIR = Path("docs/atomic-actions")
TC_DIR = Path("docs/test-cases")

CODE_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$")
AA_ID_RE = re.compile(r"^AA-([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)$")
TC_ID_RE = re.compile(r"^TC-([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)-(\d{3})$")
H1_RE = re.compile(r"^#\s+([^\n]+?)\s*$", re.MULTILINE)
H2_RE = re.compile(r"^##\s+([^\n]+?)\s*$", re.MULTILINE)
PLACEHOLDER_RE = re.compile(r"<[^>\n]+>")
DEPENDENCY_LINE_RE = re.compile(
    r"^-\s+`(?P<id>AA-[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)`\s+—\s+.+\S\.?$"
)
ORDERED_STEP_RE = re.compile(r"^(?P<number>\d+)\.\s+\S.*$")
NESTED_STEP_ITEM_RE = re.compile(r"^(?: {2,}|\t+)-\s+\S.*$")

AA_SECTIONS = [
    "Код",
    "Назначение",
    "Входные параметры",
    "Описание сценария",
    "Варианты успешного результата",
    "Выходные данные",
]
TC_SECTIONS = [
    "Код",
    "Описание",
    "Роль",
    "Тестовые данные",
    "Зависимости",
    "Описание сценария",
    "Условие проверки",
]

# Разделы, участвующие в расчёте хэша источника (см. playwright-implementation.md).
# "Назначение" у AA и "Описание" у TC — чисто описательные, не хэшируются.
AA_HASH_SECTIONS = {
    "signature": ["Входные параметры", "Выходные данные"],
    "logic": ["Описание сценария", "Варианты успешного результата"],
}
TC_HASH_SECTIONS = ["Роль", "Тестовые данные", "Зависимости", "Описание сценария", "Условие проверки"]

SELECTOR_STRATEGIES = {"role", "label", "text", "testid", "css"}

ROLE_LINE_RE = re.compile(r"^`(?P<code>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)`\s+—\s+.+\S\.?$")
ROLE_NONE_TEXT = "Роль не используется."

ROLES_PATH = Path("docs/roles.md")
ROLE_HEADER_RE = re.compile(r"^##\s+(?P<name>[^(\n]+?)\s*\(`(?P<code>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)`\)\s*$", re.MULTILINE)
AA_MENTION_RE = re.compile(r"`(AA-[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)`")


@dataclass(frozen=True)
class Issue:
    code: str
    message: str


@dataclass
class ValidationResult:
    kind: str
    document_id: str
    project_root: Path
    target_path: Path
    issues: list[Issue] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


class ScriptExecutionError(RuntimeError):
    pass


def resolve_project_root(value: str | None) -> Path:
    return Path(value).resolve() if value else Path.cwd().resolve()


def target_path_for(project_root: Path, kind: str, document_id: str) -> Path:
    directory = AA_DIR if kind == "aa" else TC_DIR
    return project_root / directory / f"{document_id}.md"


def selectors_path_for(project_root: Path, kind: str, document_id: str) -> Path:
    return target_path_for(project_root, kind, document_id).with_suffix(".selectors.json")


def validate_identifier(kind: str, document_id: str) -> list[Issue]:
    pattern = AA_ID_RE if kind == "aa" else TC_ID_RE
    if pattern.fullmatch(document_id):
        return []
    expected = "AA-<CODE>" if kind == "aa" else "TC-<CODE>-<NNN>"
    return [Issue("INVALID_IDENTIFIER", f"Идентификатор `{document_id}` не соответствует формату `{expected}`.")]


def split_sections(content: str) -> tuple[str | None, list[str], dict[str, str], list[Issue]]:
    issues: list[Issue] = []
    h1_matches = list(H1_RE.finditer(content))
    if not h1_matches:
        issues.append(Issue("TITLE_MISSING", "Отсутствует заголовок первого уровня."))
        title = None
    elif len(h1_matches) > 1:
        issues.append(Issue("MULTIPLE_TITLES", "Документ содержит несколько заголовков первого уровня."))
        title = h1_matches[0].group(1).strip()
    else:
        title = h1_matches[0].group(1).strip()

    matches = list(H2_RE.finditer(content))
    section_names: list[str] = []
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        if name in sections:
            issues.append(Issue("DUPLICATE_SECTION", f"Раздел `## {name}` указан несколько раз."))
            continue
        section_names.append(name)
        sections[name] = content[start:end].strip()
    return title, section_names, sections, issues


def validate_section_order(actual: Sequence[str], expected: Sequence[str]) -> list[Issue]:
    issues: list[Issue] = []
    missing = [name for name in expected if name not in actual]
    unknown = [name for name in actual if name not in expected]
    for name in missing:
        issues.append(Issue("SECTION_MISSING", f"Отсутствует обязательный раздел `## {name}`."))
    for name in unknown:
        issues.append(Issue("UNKNOWN_SECTION", f"Раздел `## {name}` не предусмотрен шаблоном."))
    if not missing and not unknown and list(actual) != list(expected):
        issues.append(Issue("INVALID_SECTION_ORDER", "Разделы документа расположены не в порядке шаблона."))
    return issues


def validate_nonempty_sections(sections: dict[str, str], expected: Iterable[str]) -> list[Issue]:
    return [
        Issue("EMPTY_SECTION", f"Раздел `## {name}` не должен быть пустым.")
        for name in expected
        if name in sections and not sections[name].strip()
    ]


def validate_steps(value: str) -> list[Issue]:
    lines = [line.rstrip() for line in value.splitlines() if line.strip()]
    if not lines:
        return [Issue("SCENARIO_STEPS_MISSING", "Описание сценария должно содержать хотя бы один шаг.")]

    numbers: list[int] = []
    has_current_step = False
    for line in lines:
        match = ORDERED_STEP_RE.fullmatch(line)
        if match:
            numbers.append(int(match.group("number")))
            has_current_step = True
            continue

        if NESTED_STEP_ITEM_RE.fullmatch(line):
            if not has_current_step:
                return [
                    Issue(
                        "INVALID_SCENARIO_NESTED_ITEM",
                        "Вложенный пункт должен находиться после нумерованного шага.",
                    )
                ]
            continue

        return [Issue("INVALID_SCENARIO_STEP", f"Некорректная строка шага: `{line.strip()}`.")]

    if numbers != list(range(1, len(numbers) + 1)):
        return [Issue("INVALID_SCENARIO_NUMBERING", "Шаги должны быть последовательно пронумерованы с 1.")]
    return []


def validate_success_results(value: str) -> list[Issue]:
    if any(line.strip().startswith("- ") for line in value.splitlines()):
        return []
    return [Issue("SUCCESS_RESULTS_MISSING", "Раздел `Варианты успешного результата` должен содержать хотя бы один положительный результат в виде элемента списка.")]


def parse_dependencies(value: str) -> tuple[list[str], list[Issue]]:
    stripped = value.strip()
    if stripped == "Зависимости отсутствуют.":
        return [], []

    dependencies: list[str] = []
    issues: list[Issue] = []
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        return [], [Issue("DEPENDENCIES_EMPTY", "Раздел `Зависимости` не должен быть пустым.")]

    for line in lines:
        match = DEPENDENCY_LINE_RE.fullmatch(line)
        if not match:
            issues.append(
                Issue(
                    "INVALID_DEPENDENCY_LINE",
                    "Зависимость должна иметь формат `- `AA-ID` — Мнемоническое название.`: " + line,
                )
            )
            continue
        dependency_id = match.group("id")
        if dependency_id in dependencies:
            issues.append(Issue("DUPLICATE_DEPENDENCY", f"Зависимость `{dependency_id}` указана несколько раз."))
        else:
            dependencies.append(dependency_id)
    return dependencies, issues


def known_role_codes(project_root: Path) -> set[str]:
    roles_path = project_root / ROLES_PATH
    if not roles_path.is_file():
        return set()
    content = roles_path.read_text(encoding="utf-8")
    return {code for code, _, _ in iter_role_blocks(content)}


def parse_role_reference(value: str) -> tuple[str | None, list[Issue]]:
    stripped = value.strip()
    if stripped == ROLE_NONE_TEXT:
        return None, []
    match = ROLE_LINE_RE.fullmatch(stripped)
    if not match:
        return None, [
            Issue(
                "INVALID_ROLE_LINE",
                f"Раздел `Роль` должен содержать либо `` `<ROLE-CODE>` — <Название роли>. `` либо строго «{ROLE_NONE_TEXT}».",
            )
        ]
    return match.group("code"), []


def validate_document(
    *,
    project_root: Path,
    kind: str,
    document_id: str,
    content: str,
    require_target_absent: bool = True,
    require_target_exists: bool = False,
) -> ValidationResult:
    target_path = target_path_for(project_root, kind, document_id)
    result = ValidationResult(
        kind=kind,
        document_id=document_id,
        project_root=project_root,
        target_path=target_path,
    )
    result.issues.extend(validate_identifier(kind, document_id))

    title, section_names, sections, split_issues = split_sections(content)
    result.issues.extend(split_issues)
    expected_sections = AA_SECTIONS if kind == "aa" else TC_SECTIONS
    result.issues.extend(validate_section_order(section_names, expected_sections))
    result.issues.extend(validate_nonempty_sections(sections, expected_sections))

    expected_title_prefix = f"{document_id} — "
    if title is not None:
        if not title.startswith(expected_title_prefix) or not title.removeprefix(expected_title_prefix).strip():
            result.issues.append(
                Issue("INVALID_TITLE", f"Заголовок должен иметь формат `# {document_id} — <Название>`.")
            )

    code_value = sections.get("Код", "").strip()
    if code_value and code_value != f"`{document_id}`":
        result.issues.append(Issue("CODE_MISMATCH", f"Раздел `Код` должен содержать только `{document_id}` в обратных кавычках."))

    scenario = sections.get("Описание сценария")
    if scenario:
        result.issues.extend(validate_steps(scenario))

    if kind == "aa":
        success_results = sections.get("Варианты успешного результата")
        if success_results:
            result.issues.extend(validate_success_results(success_results))
    else:
        dependencies_value = sections.get("Зависимости")
        if dependencies_value:
            dependencies, dependency_issues = parse_dependencies(dependencies_value)
            result.dependencies = dependencies
            result.issues.extend(dependency_issues)
            for dependency_id in dependencies:
                dependency_path = project_root / AA_DIR / f"{dependency_id}.md"
                if not dependency_path.is_file():
                    result.issues.append(
                        Issue("UNKNOWN_ATOMIC_ACTION", f"Action `{dependency_id}` не найден: `{dependency_path.relative_to(project_root)}`.")
                    )

        role_value = sections.get("Роль")
        if role_value:
            role_code, role_issues = parse_role_reference(role_value)
            result.issues.extend(role_issues)
            if role_code is not None:
                known_roles = known_role_codes(project_root)
                if role_code not in known_roles:
                    result.issues.append(
                        Issue(
                            "UNKNOWN_ROLE",
                            f"Роль `{role_code}` не найдена в `docs/roles.md`. Настройте её через `/configure-roles` перед использованием.",
                        )
                    )

    placeholders = sorted(set(PLACEHOLDER_RE.findall(content)))
    for placeholder in placeholders:
        result.issues.append(Issue("UNRESOLVED_PLACEHOLDER", f"В документе остался незаполненный шаблон `{placeholder}`."))

    expected_name = f"{document_id}.md"
    if target_path.name != expected_name:
        result.issues.append(Issue("TARGET_NAME_MISMATCH", f"Имя файла должно быть `{expected_name}`."))

    if require_target_absent and target_path.exists():
        result.issues.append(Issue("TARGET_EXISTS", f"Файл `{target_path.relative_to(project_root)}` уже существует."))

    if require_target_exists and not target_path.exists():
        result.issues.append(Issue("TARGET_MISSING", f"Файл `{target_path.relative_to(project_root)}` не найден — нечего редактировать."))

    return result


def extract_summary(path: Path, kind: str) -> dict[str, str]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScriptExecutionError(f"Не удалось прочитать `{path}`: {exc}") from exc
    title, _, sections, _ = split_sections(content)
    summary_section = "Назначение" if kind == "aa" else "Описание"
    summary = sections.get(summary_section, "").strip().split("\n\n", 1)[0].replace("\n", " ").strip()
    return {
        "id": path.stem,
        "title": title or "",
        "summary": summary,
        "path": path.as_posix(),
    }


def inventory(project_root: Path, kind: str) -> list[dict[str, str]]:
    directory = project_root / (AA_DIR if kind == "aa" else TC_DIR)
    if not directory.is_dir():
        raise ScriptExecutionError(f"Каталог `{directory}` не существует.")
    prefix = "AA-" if kind == "aa" else "TC-"
    documents: list[dict[str, str]] = []
    for path in sorted(directory.glob(f"{prefix}*.md")):
        if path.name.endswith(".selectors.md"):
            continue
        item = extract_summary(path, kind)
        item["path"] = path.relative_to(project_root).as_posix()
        documents.append(item)
    return documents


def next_tc_id(project_root: Path, code: str) -> str:
    if not CODE_RE.fullmatch(code):
        raise ValueError("Семантический код должен содержать только заглавные латинские буквы, цифры и дефисы.")
    directory = project_root / TC_DIR
    if not directory.is_dir():
        raise ScriptExecutionError(f"Каталог `{directory}` не существует.")
    pattern = re.compile(rf"^TC-{re.escape(code)}-(\d{{3}})\.md$")
    numbers = [int(match.group(1)) for path in directory.iterdir() if (match := pattern.fullmatch(path.name))]
    next_number = max(numbers, default=0) + 1
    if next_number > 999:
        raise ValueError(f"Для кода `{code}` закончились трёхзначные номера TC.")
    return f"TC-{code}-{next_number:03d}"


def compute_document_hash(project_root: Path, kind: str, document_id: str, part: str | None) -> str:
    path = target_path_for(project_root, kind, document_id)
    if not path.is_file():
        raise ScriptExecutionError(f"Документ `{path.relative_to(project_root)}` не найден.")
    content = path.read_text(encoding="utf-8")
    _, _, sections, _ = split_sections(content)
    if kind == "aa":
        if part not in AA_HASH_SECTIONS:
            raise ValueError("Для `--kind aa` обязателен `--part signature|logic`.")
        section_names = AA_HASH_SECTIONS[part]
    else:
        section_names = TC_HASH_SECTIONS
    parts_text = [sections.get(name, "").strip() for name in section_names]
    digest_input = "\n\n".join(parts_text).encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()[:12]


def find_role_usage(project_root: Path, role_code: str) -> list[str]:
    """TC-документы, ссылающиеся на указанную роль (для предупреждения при удалении роли)."""
    directory = project_root / TC_DIR
    if not directory.is_dir():
        return []
    pattern = re.compile(rf"Роль:\s*`{re.escape(role_code)}`")
    result: list[str] = []
    for path in sorted(directory.glob("TC-*.md")):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if pattern.search(content):
            result.append(path.stem)
    return result


def find_dependents(project_root: Path, aa_id: str) -> list[str]:
    directory = project_root / TC_DIR
    if not directory.is_dir():
        raise ScriptExecutionError(f"Каталог `{directory}` не существует.")
    dependents: list[str] = []
    for path in sorted(directory.glob("TC-*.md")):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        _, _, sections, _ = split_sections(content)
        dependency_value = sections.get("Зависимости", "")
        dependencies, _ = parse_dependencies(dependency_value)
        if aa_id in dependencies:
            dependents.append(path.stem)
    return dependents


def iter_role_blocks(content: str) -> list[tuple[str, str, str]]:
    """Return (role_code, role_name, block_text) for each role in docs/roles.md."""
    headers = list(ROLE_HEADER_RE.finditer(content))
    blocks: list[tuple[str, str, str]] = []
    for index, match in enumerate(headers):
        start = match.end()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(content)
        blocks.append((match.group("code"), match.group("name").strip(), content[start:end]))
    return blocks


def find_role_dependents(project_root: Path, aa_id: str) -> list[str]:
    """Roles whose preparation chain mentions the given AA-ID. Empty if docs/roles.md is absent."""
    roles_path = project_root / ROLES_PATH
    if not roles_path.is_file():
        return []
    content = roles_path.read_text(encoding="utf-8")
    result = []
    for code, name, block in iter_role_blocks(content):
        if aa_id in set(AA_MENTION_RE.findall(block)):
            result.append(f"{code} — {name}")
    return result


def check_roles(project_root: Path) -> list[Issue]:
    """Verify every AA mentioned in docs/roles.md actually exists."""
    roles_path = project_root / ROLES_PATH
    if not roles_path.is_file():
        return [Issue("ROLES_FILE_MISSING", f"Файл `{ROLES_PATH}` не найден.")]
    content = roles_path.read_text(encoding="utf-8")
    issues: list[Issue] = []
    for code, name, block in iter_role_blocks(content):
        for aa_id in sorted(set(AA_MENTION_RE.findall(block))):
            if not (project_root / AA_DIR / f"{aa_id}.md").is_file():
                issues.append(
                    Issue(
                        "ROLE_UNKNOWN_ATOMIC_ACTION",
                        f"Роль `{code}` ({name}) ссылается на несуществующий `{aa_id}`.",
                    )
                )
    return issues


def read_content(path_value: str) -> str:
    if path_value == "-":
        return sys.stdin.read()
    path = Path(path_value)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScriptExecutionError(f"Не удалось прочитать `{path}`: {exc}") from exc


def render_validation(result: ValidationResult, operation: str) -> str:
    if result.ok:
        status = {"create": "CREATED", "update": "UPDATED"}.get(operation, "OK")
        try:
            display_path = result.target_path.relative_to(result.project_root).as_posix()
        except ValueError:
            display_path = result.target_path.as_posix()
        lines = [
            f"**Статус:** `{status}`",
            "",
            f"**Документ:** `{result.document_id}`",
            f"**Путь:** `{display_path}`",
        ]
        if result.dependencies:
            lines.extend(["", "**Зависимости:** " + ", ".join(f"`{item}`" for item in result.dependencies)])
        return "\n".join(lines) + "\n"

    lines = ["**Статус:** `VALIDATION_ERROR`", "", "**Ошибки:**"]
    lines.extend(f"- `{issue.code}` — {issue.message}" for issue in result.issues)
    return "\n".join(lines) + "\n"


def create_document(result: ValidationResult, content: str) -> None:
    if not result.ok:
        return
    parent = result.target_path.parent
    if not parent.is_dir():
        raise ScriptExecutionError(f"Каталог `{parent}` не существует.")
    try:
        fd = os.open(result.target_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content.rstrip() + "\n")
    except FileExistsError:
        result.issues.append(Issue("TARGET_EXISTS", f"Файл `{result.target_path}` уже существует."))
    except OSError as exc:
        raise ScriptExecutionError(f"Не удалось создать `{result.target_path}`: {exc}") from exc


def update_document(result: ValidationResult, content: str) -> None:
    """Atomically overwrite an existing, already-approved document (used by /edit-aa, /edit-tc)."""
    if not result.ok:
        return
    parent = result.target_path.parent
    if not parent.is_dir():
        raise ScriptExecutionError(f"Каталог `{parent}` не существует.")
    tmp_path = result.target_path.with_suffix(result.target_path.suffix + ".tmp")
    try:
        tmp_path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")
        os.replace(tmp_path, result.target_path)
    except OSError as exc:
        raise ScriptExecutionError(f"Не удалось обновить `{result.target_path}`: {exc}") from exc
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def validate_selector_locator(value: object, path_label: str) -> list[Issue]:
    issues: list[Issue] = []
    if not isinstance(value, dict):
        issues.append(Issue("INVALID_SELECTOR_LOCATOR", f"`{path_label}` должен быть объектом."))
        return issues
    strategy = value.get("strategy")
    if strategy not in SELECTOR_STRATEGIES:
        issues.append(
            Issue(
                "INVALID_SELECTOR_STRATEGY",
                f"`{path_label}.strategy` должна быть одной из: {', '.join(sorted(SELECTOR_STRATEGIES))}.",
            )
        )
    return issues


def validate_selector_document_data(document_id: str, data: object) -> list[Issue]:
    issues: list[Issue] = []
    if not isinstance(data, dict):
        return [Issue("INVALID_SELECTOR_ROOT", "Документ селекторов должен быть JSON-объектом.")]

    if data.get("document") != document_id:
        issues.append(Issue("SELECTOR_DOCUMENT_MISMATCH", f"Поле `document` должно быть `{document_id}`."))

    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        issues.append(Issue("SELECTOR_PAGES_MISSING", "Раздел `pages` должен быть непустым списком."))
        return issues

    for page_index, page in enumerate(pages):
        page_label = f"pages[{page_index}]"
        if not isinstance(page, dict):
            issues.append(Issue("INVALID_SELECTOR_PAGE", f"`{page_label}` должен быть объектом."))
            continue
        if not page.get("name"):
            issues.append(Issue("SELECTOR_PAGE_NAME_MISSING", f"`{page_label}.name` не должно быть пустым."))
        if not page.get("route"):
            issues.append(Issue("SELECTOR_PAGE_ROUTE_MISSING", f"`{page_label}.route` не должно быть пустым."))

        elements = page.get("elements")
        if not isinstance(elements, dict) or not elements:
            issues.append(Issue("SELECTOR_ELEMENTS_MISSING", f"`{page_label}.elements` должен быть непустым объектом."))
            continue

        for key, element in elements.items():
            element_label = f"{page_label}.elements.{key}"
            if not isinstance(element, dict):
                issues.append(Issue("INVALID_SELECTOR_ELEMENT", f"`{element_label}` должен быть объектом."))
                continue
            if not element.get("description"):
                issues.append(Issue("SELECTOR_DESCRIPTION_MISSING", f"`{element_label}.description` не должно быть пустым."))

            locator = element.get("locator")
            if not isinstance(locator, dict) or "primary" not in locator:
                issues.append(Issue("SELECTOR_LOCATOR_MISSING", f"`{element_label}.locator.primary` обязателен."))
            else:
                issues.extend(validate_selector_locator(locator.get("primary"), f"{element_label}.locator.primary"))
                fallback = locator.get("fallback")
                if fallback is not None:
                    issues.extend(validate_selector_locator(fallback, f"{element_label}.locator.fallback"))

            within = element.get("within")
            if within is not None and within not in elements:
                issues.append(
                    Issue(
                        "SELECTOR_WITHIN_UNKNOWN",
                        f"`{element_label}.within` ссылается на несуществующий ключ `{within}` на этой же странице.",
                    )
                )
    return issues


def write_selectors(project_root: Path, kind: str, document_id: str, raw_content: str) -> tuple[bool, list[Issue], Path]:
    target = selectors_path_for(project_root, kind, document_id)
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        return False, [Issue("INVALID_JSON", str(exc))], target

    issues = validate_selector_document_data(document_id, data)
    if issues:
        return False, issues, target

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix(target.suffix + ".tmp")
    try:
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        os.replace(tmp_path, target)
    except OSError as exc:
        raise ScriptExecutionError(f"Не удалось записать `{target}`: {exc}") from exc
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
    return True, [], target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Проверка, создание, редактирование и агрегация документов AA/TC")
    parser.add_argument("--project-root", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory_parser = subparsers.add_parser("inventory", help="Показать существующие документы")
    inventory_parser.add_argument("--kind", choices=("aa", "tc"), required=True)
    inventory_parser.add_argument("--format", choices=("markdown", "json"), default="markdown")

    next_parser = subparsers.add_parser("next-tc-id", help="Предложить следующий свободный TC-ID")
    next_parser.add_argument("--code", required=True)

    for command in ("validate", "create", "update"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--kind", choices=("aa", "tc"), required=True)
        command_parser.add_argument("--id", required=True, dest="document_id")
        command_parser.add_argument("--content-file", default="-")
        if command == "validate":
            command_parser.add_argument(
                "--mode",
                choices=("create", "update"),
                default="create",
                help="create: целевой файл должен отсутствовать. update: целевой файл должен существовать (используется /edit-aa, /edit-tc).",
            )

    hash_parser = subparsers.add_parser("hash", help="Вычислить хэш источника документа")
    hash_parser.add_argument("--kind", choices=("aa", "tc"), required=True)
    hash_parser.add_argument("--id", required=True, dest="document_id")
    hash_parser.add_argument("--part", choices=("signature", "logic"), default=None)

    dependents_parser = subparsers.add_parser("dependents", help="Найти TC, зависящие от указанного AA")
    dependents_parser.add_argument("--kind", choices=("aa",), required=True)
    dependents_parser.add_argument("--id", required=True, dest="document_id")

    role_dependents_parser = subparsers.add_parser(
        "role-dependents", help="Найти роли (docs/roles.md), зависящие от указанного AA"
    )
    role_dependents_parser.add_argument("--id", required=True, dest="document_id")

    role_usage_parser = subparsers.add_parser(
        "role-usage", help="Найти TC, ссылающиеся на указанную роль"
    )
    role_usage_parser.add_argument("--id", required=True, dest="document_id")

    check_roles_parser = subparsers.add_parser(
        "check-roles", help="Проверить, что все AA, упомянутые в docs/roles.md, существуют"
    )

    write_selectors_parser = subparsers.add_parser(
        "write-selectors", help="Проверить и записать JSON-спецификацию селекторов"
    )
    write_selectors_parser.add_argument("--kind", choices=("aa", "tc"), required=True)
    write_selectors_parser.add_argument("--id", required=True, dest="document_id")
    write_selectors_parser.add_argument("--content-file", default="-")

    return parser


def render_inventory(documents: Sequence[dict[str, str]], kind: str) -> str:
    label = "Actions" if kind == "aa" else "Test Cases"
    lines = [f"## {label}", ""]
    if not documents:
        return "\n".join(lines + ["Документы отсутствуют.", ""])
    for item in documents:
        detail = item["summary"] or item["title"] or "Описание не найдено"
        lines.append(f"- `{item['id']}` — {detail} (`{item['path']}`)")
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = resolve_project_root(args.project_root)
    try:
        if args.command == "inventory":
            documents = inventory(project_root, args.kind)
            if args.format == "json":
                print(json.dumps(documents, ensure_ascii=False, indent=2))
            else:
                print(render_inventory(documents, args.kind), end="")
            return 0

        if args.command == "next-tc-id":
            print(next_tc_id(project_root, args.code))
            return 0

        if args.command == "hash":
            print(compute_document_hash(project_root, args.kind, args.document_id, args.part))
            return 0

        if args.command == "dependents":
            for tc_id in find_dependents(project_root, args.document_id):
                print(tc_id)
            return 0

        if args.command == "role-dependents":
            for entry in find_role_dependents(project_root, args.document_id):
                print(entry)
            return 0

        if args.command == "role-usage":
            for tc_id in find_role_usage(project_root, args.document_id):
                print(tc_id)
            return 0

        if args.command == "check-roles":
            issues = check_roles(project_root)
            if not issues:
                print("**Статус:** `OK`\n\nВсе AA, упомянутые в `docs/roles.md`, существуют.")
                return 0
            lines = ["**Статус:** `VALIDATION_ERROR`", "", "**Ошибки:**"]
            lines.extend(f"- `{issue.code}` — {issue.message}" for issue in issues)
            print("\n".join(lines))
            return 1

        if args.command == "write-selectors":
            raw_content = read_content(args.content_file)
            ok, issues, target = write_selectors(project_root, args.kind, args.document_id, raw_content)
            if ok:
                print(f"**Статус:** `WRITTEN`\n\n**Путь:** `{target.relative_to(project_root)}`\n", end="")
                return 0
            lines = ["**Статус:** `VALIDATION_ERROR`", "", "**Ошибки:**"]
            lines.extend(f"- `{issue.code}` — {issue.message}" for issue in issues)
            print("\n".join(lines))
            return 1

        content = read_content(args.content_file)
        if args.command == "validate":
            mode = args.mode
        else:
            mode = args.command  # "create" or "update"
        require_target_absent = mode == "create"
        require_target_exists = mode == "update"

        result = validate_document(
            project_root=project_root,
            kind=args.kind,
            document_id=args.document_id,
            content=content,
            require_target_absent=require_target_absent,
            require_target_exists=require_target_exists,
        )
        if args.command == "create" and result.ok:
            create_document(result, content)
        elif args.command == "update" and result.ok:
            update_document(result, content)
        print(render_validation(result, args.command), end="")
        return 0 if result.ok else 1
    except ValueError as exc:
        print(f"**Статус:** `VALIDATION_ERROR`\n\n- `INVALID_ARGUMENT` — {exc}")
        return 1
    except ScriptExecutionError as exc:
        print(f"**Статус:** `SCRIPT_ERROR`\n\n- `SCRIPT_EXECUTION` — {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # defensive CLI boundary
        print(f"**Статус:** `SCRIPT_ERROR`\n\n- `UNEXPECTED_ERROR` — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
