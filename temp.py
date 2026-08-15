### CODECHECK.py - a coder's best friend for checking code quality and style.
### Circa 2026-August.

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from html.parser import HTMLParser

CODECHECK_VERSION = "v1.5.1"
CODECHECK_HI = "Hi!"

SCRIPT_NAME = Path(__file__).name

EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "botvenv",
    "venv312",
    "dump",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    "coverage",
    "htmlcov",
}

BACKUP_MARKERS = (
    "backup",
    "_v",
    ".zip",
)

EXCLUDED_METADATA_FILES = {
    ".gitignore",
    ".gitattributes",
    ".dockerignore",
    ".env",
}

DEVELOPMENT_MARKERS = (
    "TODO",
    "FIXME",
    "HACK",
    "NB:",
    "NOTE",
    "DEPRECATED",
)

NUMBERED_COPY_PATTERN = re.compile(r"\(\d+\)")

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
    ".tif", ".tiff", ".svg", ".ico",
}

OUTPUT_WIDTH = 80

LARGE_PROJECT_WARNING_THRESHOLD = 100
VERY_LARGE_PROJECT_WARNING_THRESHOLD = 500

# =============================================================================
# Global State
# =============================================================================
project_root: Path | None = None
directory_size_cache: dict[Path, int] = {}

# =============================================================================
# Utility Functions
# =============================================================================
def path_component_is_excluded(name: str) -> bool:
    """Return True when a file or directory name matches an exclusion rule."""
    lowered = name.lower()

    if lowered in EXCLUDED_DIRECTORY_NAMES:
        return True

    if any(marker in lowered for marker in BACKUP_MARKERS):
        return True

    if lowered in EXCLUDED_METADATA_FILES:
        return True

    if NUMBERED_COPY_PATTERN.search(lowered):
        return True

    # File is go
    return False


def should_exclude_path(path: Path, root: Path) -> bool:
    """Check every project-relative path component against exclusion rules."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path

    return any(path_component_is_excluded(part) for part in relative.parts)


def count_included_files(root: Path) -> int:
    """Count all included project files without following directory symlinks."""
    file_count = 0
    script_path = Path(__file__).resolve()

    for current_root, directory_names, file_names in os.walk(root):
        current_path = Path(current_root)

        directory_names[:] = sorted(
            directory_name
            for directory_name in directory_names
            if not path_component_is_excluded(directory_name)
            and not should_exclude_path(current_path / directory_name, root)
            and not (current_path / directory_name).is_symlink()
        )

        for file_name in file_names:
            path = current_path / file_name

            if path_component_is_excluded(file_name):
                continue

            if should_exclude_path(path, root):
                continue

            try:
                if path.resolve() == script_path:
                    continue
            except OSError:
                pass

            file_count += 1

    return file_count


def confirm_large_project(root: Path) -> bool:
    """Warn before running any insight against a project with many files."""
    file_count = count_included_files(root)

    if file_count >= VERY_LARGE_PROJECT_WARNING_THRESHOLD:
        print()
        print(
            f"Warning: this project contains {file_count:,} included files. "
            "Scanning it may produce substantial output and filesystem work."
        )
    elif file_count >= LARGE_PROJECT_WARNING_THRESHOLD:
        print()
        print(
            f"This project contains {file_count:,} included files. "
            "The selected report may produce a long output."
        )
    else:
        return True

    response = input("Continue? [y/n]: ").strip().lower()
    return response in {"y", "yes"}

# =============================================================================
# HTML Assessment Functions
# =============================================================================
# =============================================================================
# HTML Assessment Functions
# =============================================================================

HTML_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

HTML_OPTIONAL_END_TAGS = {
    "colgroup", "dd", "dt", "li", "optgroup", "option", "p",
    "tbody", "td", "tfoot", "th", "thead", "tr",
}

HTML_AUTO_CLOSE_RULES = {
    "li": {"li"},
    "dt": {"dt", "dd"},
    "dd": {"dt", "dd"},
    "p": {
        "address", "article", "aside", "blockquote", "div", "dl",
        "fieldset", "footer", "form", "h1", "h2", "h3", "h4",
        "h5", "h6", "header", "hr", "menu", "nav", "ol", "p",
        "pre", "section", "table", "ul",
    },
    "option": {"option", "optgroup"},
    "optgroup": {"optgroup"},
    "thead": {"tbody", "tfoot"},
    "tbody": {"tbody", "tfoot"},
    "tfoot": {"tbody"},
    "tr": {"tr"},
    "td": {"td", "th"},
    "th": {"td", "th"},
}


class HTMLCompletenessParser(HTMLParser):
    """Collect practical completeness and tag-balance information."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)

        self.has_doctype = False
        self.has_html = False
        self.has_html_lang = False
        self.has_charset = False
        self.has_body = False
        self.has_viewport = False
        self.has_embedded_style = False
        self.has_linked_stylesheet = False
        self.has_favicon = False

        self.in_title = False
        self.title_parts: list[str] = []

        self.meta_description = ""
        self.og_title = ""
        self.og_description = ""
        self.og_image = ""
        self.og_url = ""
        self.og_type = ""

        self.open_tags: list[tuple[str, int]] = []
        self.tag_issues: list[tuple[int, str, str]] = []

    def handle_decl(self, decl: str) -> None:
        """Record a valid HTML doctype."""
        if decl.strip().lower() == "doctype html":
            self.has_doctype = True

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """Inspect an opening tag and update completeness state."""
        tag = tag.lower()
        attributes = {
            name.lower(): (value or "")
            for name, value in attrs
        }
        line_number, _ = self.getpos()

        self._auto_close_optional_tag(tag)

        if tag == "html":
            self.has_html = True
            self.has_html_lang = bool(attributes.get("lang", "").strip())

        elif tag == "meta":
            if attributes.get("charset", "").strip():
                self.has_charset = True

            meta_name = attributes.get("name", "").strip().lower()
            meta_property = attributes.get("property", "").strip().lower()
            content = attributes.get("content", "").strip()

            if meta_name == "description" and content:
                self.meta_description = content

            if meta_name == "viewport":
                normalized = content.replace(" ", "").lower()
                if "width=device-width" in normalized:
                    self.has_viewport = True

            if meta_property == "og:title" and content:
                self.og_title = content
            elif meta_property == "og:description" and content:
                self.og_description = content
            elif meta_property == "og:image" and content:
                self.og_image = content
            elif meta_property == "og:url" and content:
                self.og_url = content
            elif meta_property == "og:type" and content:
                self.og_type = content

        elif tag == "title":
            self.in_title = True

        elif tag == "body":
            self.has_body = True

        elif tag == "style":
            self.has_embedded_style = True

        elif tag == "link":
            rel_value = attributes.get("rel", "").strip().lower()
            rel_tokens = set(rel_value.split())
            href = attributes.get("href", "").strip()

            if "stylesheet" in rel_tokens and href:
                self.has_linked_stylesheet = True

            if href and (
                "icon" in rel_tokens
                or rel_value in {
                    "shortcut icon",
                    "apple-touch-icon",
                    "mask-icon",
                }
            ):
                self.has_favicon = True

        if tag not in HTML_VOID_TAGS:
            self.open_tags.append((tag, line_number))

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """Inspect a self-closing tag without leaving it on the stack."""
        self.handle_starttag(tag, attrs)
        tag = tag.lower()

        if (
            tag not in HTML_VOID_TAGS
            and self.open_tags
            and self.open_tags[-1][0] == tag
        ):
            self.open_tags.pop()

    def handle_endtag(self, tag: str) -> None:
        """Match a closing tag against the current stack."""
        tag = tag.lower()

        if tag == "title":
            self.in_title = False

        if tag in HTML_VOID_TAGS:
            return

        line_number, _ = self.getpos()
        matching_index = None

        for index in range(len(self.open_tags) - 1, -1, -1):
            if self.open_tags[index][0] == tag:
                matching_index = index
                break

        if matching_index is None:
            self.tag_issues.append(
                (
                    line_number,
                    "!",
                    f"Closing </{tag}> has no matching opening tag",
                )
            )
            return

        for open_tag, opening_line in self.open_tags[matching_index + 1:]:
            if open_tag in HTML_OPTIONAL_END_TAGS:
                continue

            self.tag_issues.append(
                (
                    opening_line,
                    "!",
                    f"Unclosed <{open_tag}> opened on line {opening_line}",
                )
            )

        del self.open_tags[matching_index:]

    def handle_data(self, data: str) -> None:
        """Collect nonempty title text."""
        if self.in_title:
            self.title_parts.append(data)

    def close(self) -> None:
        """Finish parsing and report strict tags still left open."""
        super().close()

        for tag, opening_line in self.open_tags:
            if tag in HTML_OPTIONAL_END_TAGS:
                continue

            self.tag_issues.append(
                (
                    opening_line,
                    "!",
                    f"Unclosed <{tag}> opened on line {opening_line}",
                )
            )

    def _auto_close_optional_tag(self, incoming_tag: str) -> None:
        """Apply common HTML optional-end-tag behavior."""
        if not self.open_tags:
            return

        current_tag, _ = self.open_tags[-1]
        closing_starters = HTML_AUTO_CLOSE_RULES.get(current_tag)

        if closing_starters and incoming_tag in closing_starters:
            self.open_tags.pop()

    @property
    def title_text(self) -> str:
        """Return normalized title text."""
        return " ".join(
            part.strip()
            for part in self.title_parts
            if part.strip()
        )


def discover_html_files(root: Path) -> list[Path]:
    """Return eligible HTML files in root-first alphabetical order."""
    html_files: list[Path] = []

    for current_root, directory_names, file_names in os.walk(root):
        current_path = Path(current_root)

        directory_names[:] = sorted(
            directory_name
            for directory_name in directory_names
            if not path_component_is_excluded(directory_name)
            and not should_exclude_path(current_path / directory_name, root)
            and not (current_path / directory_name).is_symlink()
        )

        for file_name in sorted(file_names):
            path = current_path / file_name

            if path.suffix.lower() not in {".html", ".htm"}:
                continue

            if path_component_is_excluded(file_name):
                continue

            if should_exclude_path(path, root):
                continue

            html_files.append(path)

    def html_sort_key(path: Path) -> tuple[int, str]:
        relative = path.relative_to(root)
        return (len(relative.parts) > 1, relative.as_posix().lower())

    html_files.sort(key=html_sort_key)
    return html_files


def html_category_passes(parser: HTMLCompletenessParser) -> bool:
    """Return True when all core HTML checks pass."""
    return all(
        (
            parser.has_doctype,
            parser.has_html,
            parser.has_html_lang,
            parser.has_charset,
            bool(parser.title_text),
            bool(parser.meta_description),
            parser.has_body,
        )
    )


def html_css_value(parser: HTMLCompletenessParser) -> str:
    """Return the document's stylesheet arrangement."""
    if parser.has_linked_stylesheet and parser.has_embedded_style:
        return "both"

    if parser.has_linked_stylesheet:
        return "linked"

    if parser.has_embedded_style:
        return "in-page"

    return "—"


def build_html_issues(
    parser: HTMLCompletenessParser,
) -> list[tuple[int, str, str]]:
    """Return missing checks, recommendations, and tag issues."""
    issues: list[tuple[int, str, str]] = []

    if not parser.has_doctype:
        issues.append((0, "—", "Missing doctype"))

    if not parser.has_html:
        issues.append((0, "—", "Missing <html> element"))
    elif not parser.has_html_lang:
        issues.append((0, "—", "Missing html lang attribute"))

    if not parser.has_charset:
        issues.append((0, "—", "Missing charset"))

    if not parser.title_text:
        issues.append((0, "—", "Missing or empty title"))

    if not parser.meta_description:
        issues.append((0, "—", "Missing meta description"))

    if not parser.has_body:
        issues.append((0, "—", "Missing body"))

    if not parser.has_viewport:
        issues.append((0, "—", "Missing viewport metadata"))

    if not (
        parser.has_embedded_style
        or parser.has_linked_stylesheet
    ):
        issues.append((0, "—", "Missing embedded style or linked stylesheet"))

    if not parser.og_title:
        issues.append((0, "—", "Missing Open Graph title"))

    if not parser.og_description:
        issues.append((0, "—", "Missing Open Graph description"))

    if not parser.og_image:
        issues.append((0, "—", "Missing Open Graph image"))

    if not parser.has_favicon:
        issues.append((0, "—", "Missing favicon"))

    # Useful recommendations, but these do not fail the compact OG category.
    if not parser.og_url:
        issues.append((0, "!", "Missing recommended Open Graph URL"))

    if not parser.og_type:
        issues.append((0, "!", "Missing recommended Open Graph type"))

    issues.extend(parser.tag_issues)
    issues.sort(key=lambda issue: (issue[0], issue[2].lower()))
    return issues


def print_html_file_summary(
    relative_path: str,
    parser: HTMLCompletenessParser,
) -> None:
    """Print one checklist row with the file path on the right."""
    headers = (
        f"{'HTML':^6} "
        f"{'</>':^5} "
        f"{'📱':^5} "
        f"{'CSS':^9} "
        f"{'OG':^5} "
        f"{'OG🖼️':^6} "
        f"{'⭐':^5}  "
        "File"
    )
    values = (
        f"{'✓' if html_category_passes(parser) else '—':^6} "
        f"{'✓' if not parser.tag_issues else '!':^5} "
        f"{'OK' if parser.has_viewport else '—':^5} "
        f"{html_css_value(parser):^9} "
        f"{'✓' if parser.og_title and parser.og_description else '—':^5} "
        f"{'✓' if parser.og_image else '—':^6} "
        f"{'✓' if parser.has_favicon else '—':^5}  "
        f"{relative_path}"
    )

    print(headers)
    print(values)


def html_completeness(root: Path) -> None:
    """Scan HTML files for practical completeness and tag structure."""
    html_files = discover_html_files(root)

    print()
    print("HTML Completeness")
    print("=" * 17)

    if not html_files:
        print("No HTML files found.")
        return

    clean_files = 0
    files_with_findings = 0

    for path in html_files:
        relative_path = path.relative_to(root).as_posix()
        parser = HTMLCompletenessParser()

        try:
            parser.feed(path.read_text(encoding="utf-8-sig"))
            parser.close()
        except (OSError, UnicodeDecodeError) as error:
            print()
            print(relative_path)
            print(f"  ! Could not read this file: {error}")
            files_with_findings += 1
            continue
        except Exception as error:
            print()
            print(relative_path)
            print(f"  ! Could not parse this file: {error}")
            files_with_findings += 1
            continue

        findings = build_html_issues(parser)

        print()
        print_html_file_summary(relative_path, parser)

        if findings:
            files_with_findings += 1

            for line_number, symbol, message in findings:
                if line_number:
                    print(f"  {symbol} Line {line_number}: {message}")
                else:
                    print(f"  {symbol} {message}")
        else:
            clean_files += 1
            print("  ✓ No completeness issues found.")

    print()
    print(
        f"{len(html_files):,} HTML "
        f"{'file' if len(html_files) == 1 else 'files'} scanned."
    )
    print(f"{clean_files:,} passed without issues.")
    print(f"{files_with_findings:,} had issues or recommendations.")


# =============================================================================
# PYTHON: Code Counting Functions
# =============================================================================
def indentation_width(line: str) -> int:
    """Measure indentation after treating each tab as four spaces."""
    expanded = line.expandtabs(4)
    return len(expanded) - len(expanded.lstrip())


def count_python_code_lines(path: Path) -> int:
    """
    Count Python lines using CodeCheck's intentionally simple project rules.

    Excluded:
    - blank or whitespace-only lines
    - full-line comments
    - triple-double-quoted blocks
    - if False branches and all more deeply indented lines beneath them

    Inline comments remain code. Triple-single-quoted strings are not special.
    """
    code_lines = 0
    in_docstring_block = False
    dead_branch_indent: int | None = None

    try:
        with path.open("r", encoding="utf-8-sig") as source_file:
            for raw_line in source_file:
                stripped = raw_line.strip()
                left_stripped = raw_line.lstrip()

                # Blank lines never count and never terminate dead-branch mode.
                if not stripped:
                    continue

                current_indent = indentation_width(raw_line)

                # A nonblank line at equal or lesser indentation exits the branch.
                if dead_branch_indent is not None:
                    if current_indent > dead_branch_indent:
                        continue
                    dead_branch_indent = None

                # Skip triple-double-quoted blocks.
                quote_count = raw_line.count('"""')

                if in_docstring_block:
                    if quote_count:
                        in_docstring_block = False
                    continue

                if quote_count:
                    # One-line triple-quoted block: skip without entering mode.
                    if quote_count >= 2:
                        continue

                    in_docstring_block = True
                    continue

                # Skip full-line comments.
                if left_stripped.startswith("#"):
                    continue

                # Skip literal dead branches and their more-indented contents.
                if left_stripped.startswith("if False"):
                    dead_branch_indent = current_indent
                    continue

                # Count this line as code.
                code_lines += 1

    except UnicodeDecodeError:
        print(f"Skipped unreadable file: {path}")

    except OSError as error:
        print(f"Could not read {path}: {error}")

    return code_lines


def discover_python_files(root: Path) -> tuple[list[Path], list[Path]]:
    """Return eligible nonempty Python files and zero-byte Python files."""
    source_files: list[Path] = []
    blank_files: list[Path] = []

    script_path = Path(__file__).resolve()

    for current_root, directory_names, file_names in os.walk(root):
        current_path = Path(current_root)

        directory_names[:] = sorted(
            directory_name
            for directory_name in directory_names
            if not path_component_is_excluded(directory_name)
            and not should_exclude_path(current_path / directory_name, root)
        )

        for file_name in sorted(file_names):
            path = current_path / file_name

            if path.suffix.lower() != ".py":
                continue

            if path.resolve() == script_path:
                continue

            if path_component_is_excluded(file_name):
                continue

            if should_exclude_path(path, root):
                continue

            try:
                if path.stat().st_size == 0:
                    blank_files.append(path)
                else:
                    source_files.append(path)
            except OSError as error:
                print(f"Could not inspect {path}: {error}")

    def python_sort_key(path: Path) -> tuple[int, str]:
        relative = path.relative_to(root)
        return (len(relative.parts) > 1, relative.as_posix().lower())

    source_files.sort(key=python_sort_key)
    blank_files.sort(key=python_sort_key)

    return source_files, blank_files


def print_python_loc_report(root: Path) -> None:
    """Scan Python files and print an alphabetical code-line report."""
    source_files, blank_files = discover_python_files(root)

    results: list[tuple[Path, int]] = [
        (path, count_python_code_lines(path))
        for path in source_files
    ]

    total_lines = sum(count for _, count in results)
    formatted_counts = [f"{count:,}" for _, count in results]
    number_width = max((len(value) for value in formatted_counts), default=1)

    print()
    print("Python Lines of Code")
    print("=" * 20)

    if results:
        for path, count in results:
            relative_path = path.relative_to(root).as_posix()
            print(f"{count:>{number_width},} = {relative_path}")
    else:
        print("No nonempty Python source files found.")

    print()

    source_word = "file" if len(results) == 1 else "files"
    line_word = "line" if total_lines == 1 else "lines"

    print(
        f"{len(results):,} source {source_word} "
        f"totalling {total_lines:,} {line_word} of code."
    )

    blank_word = "file" if len(blank_files) == 1 else "files"
    print(f"{len(blank_files):,} blank {blank_word} found.")

    if blank_files:
        for path in blank_files:
            print(f"  {path.relative_to(root).as_posix()}")
# =============================================================================
# PYTHON: Explore Code Structure Functions
# =============================================================================
def format_function_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
    """Return a compact function or method signature."""
    arguments: list[str] = []
    positional_arguments = list(node.args.posonlyargs) + list(node.args.args)

    for argument in positional_arguments:
        arguments.append(argument.arg)

    if node.args.vararg is not None:
        arguments.append(f"*{node.args.vararg.arg}")
    elif node.args.kwonlyargs:
        arguments.append("*")

    for argument in node.args.kwonlyargs:
        arguments.append(argument.arg)

    if node.args.kwarg is not None:
        arguments.append(f"**{node.args.kwarg.arg}")

    return f"{node.name}({', '.join(arguments)})"


def format_class_name(node: ast.ClassDef) -> str:
    """Return a class name with its base classes when present."""
    base_names: list[str] = []

    for base in node.bases:
        try:
            base_names.append(ast.unparse(base))
        except Exception:
            base_names.append("?")

    if base_names:
        return f"class {node.name}({', '.join(base_names)}):"

    return f"class {node.name}():"


def module_has_main_guard(tree: ast.Module) -> bool:
    """Return True when the module contains an if __name__ == '__main__' guard."""
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue

        test = node.test
        if not isinstance(test, ast.Compare):
            continue

        if len(test.ops) != 1 or len(test.comparators) != 1:
            continue

        if not isinstance(test.ops[0], ast.Eq):
            continue

        left = test.left
        right = test.comparators[0]

        normal_order = (
            isinstance(left, ast.Name)
            and left.id == "__name__"
            and isinstance(right, ast.Constant)
            and right.value == "__main__"
        )
        reverse_order = (
            isinstance(left, ast.Constant)
            and left.value == "__main__"
            and isinstance(right, ast.Name)
            and right.id == "__name__"
        )

        if normal_order or reverse_order:
            return True

    return False


def explore_python_structure(root: Path) -> None:
    """Print public Python classes, functions, and methods for each source file."""
    source_files, blank_files = discover_python_files(root)
    del blank_files

    print()
    print("Python Code Structure")
    print("=" * 21)

    if not source_files:
        print("No nonempty Python source files found.")
        return

    for path in source_files:
        relative_path = path.relative_to(root).as_posix()

        try:
            source = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source, filename=str(path))
        except UnicodeDecodeError:
            print()
            print(relative_path)
            print("Could not decode this file.")
            continue
        except SyntaxError as error:
            print()
            print(relative_path)
            print(
                f"Could not explore due to syntax error on "
                f"line {error.lineno or '?'}: {error.msg}"
            )
            continue
        except OSError as error:
            print()
            print(relative_path)
            print(f"Could not read this file: {error}")
            continue

        classes = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and not node.name.startswith("_")
        ]
        functions = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        ]
        public_method_count = sum(
            1
            for class_node in classes
            for class_item in class_node.body
            if isinstance(class_item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not class_item.name.startswith("_")
        )

        print()
        print(
            f"{'File':<42} {'Classes':>7} {'Functions':>9} "
            f"{'Methods':>7} {'Main':>5}"
        )
        print(
            f"{relative_path:<42} {len(classes):>7,} "
            f"{len(functions):>9,} {public_method_count:>7,} "
            f"{'Yes' if module_has_main_guard(tree) else 'No':>5}"
        )

        for function_node in functions:
            prefix = (
                "async def"
                if isinstance(function_node, ast.AsyncFunctionDef)
                else "def"
            )
            print(f"{prefix} {format_function_signature(function_node)}")

        for class_node in classes:
            print(format_class_name(class_node))

            for class_item in class_node.body:
                if not isinstance(
                    class_item,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                ):
                    continue

                if class_item.name.startswith("_"):
                    continue

                method_prefix = (
                    "async"
                    if isinstance(class_item, ast.AsyncFunctionDef)
                    else "def"
                )
                print(
                    f"  - {method_prefix} "
                    f"{format_function_signature(class_item)}"
                )

# =============================================================================
# PYTHON: Check Syntax Functions
# =============================================================================
def check_python_syntax(root: Path) -> None:
    """Parse every eligible Python file and report syntax errors."""
    source_files, blank_files = discover_python_files(root)
    del blank_files

    successful_files = 0
    syntax_errors: list[tuple[Path, SyntaxError]] = []
    unreadable_files: list[tuple[Path, str]] = []

    for path in source_files:
        try:
            source = path.read_text(encoding="utf-8-sig")
            ast.parse(source, filename=str(path))
            successful_files += 1
        except SyntaxError as error:
            syntax_errors.append((path, error))
        except (OSError, UnicodeDecodeError) as error:
            unreadable_files.append((path, str(error)))

    print()
    print("Python Syntax Check")
    print("=" * 19)
    print(
        f"{successful_files:,} "
        f"{'file' if successful_files == 1 else 'files'} "
        "parsed successfully."
    )

    if syntax_errors:
        print()
        print(
            f"{len(syntax_errors):,} syntax "
            f"{'error' if len(syntax_errors) == 1 else 'errors'} found."
        )

        for path, error in syntax_errors:
            relative_path = path.relative_to(root).as_posix()
            print()
            print(
                f"{relative_path}:{error.lineno or '?'}:"
                f"{error.offset or '?'}"
            )
            print(f"  {error.msg}")

            if error.text:
                print(f"  {error.text.rstrip()}")
    else:
        print("No syntax errors found.")

    if unreadable_files:
        print()
        print("Unreadable files:")

        for path, error_text in unreadable_files:
            relative_path = path.relative_to(root).as_posix()
            print(f"  {relative_path}: {error_text}")

# =============================================================================
# PYTHON: Find markers and disabled code Functions
# =============================================================================
DEVELOPMENT_MARKER_PATTERN = re.compile(
    rf"\\b({'|'.join(DEVELOPMENT_MARKERS)})\\b[:\\-\\s]*(.*)",
    re.IGNORECASE,
)

def find_python_markers(root: Path) -> None:
    """Find development markers, pass statements, and disabled branches."""
    source_files, blank_files = discover_python_files(root)
    del blank_files

    findings: list[tuple[str, int, str, str]] = []

    for path in source_files:
        relative_path = path.relative_to(root).as_posix()

        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeDecodeError) as error:
            print(f"Could not inspect {relative_path}: {error}")
            continue

        for line_number, raw_line in enumerate(lines, start=1):
            stripped = raw_line.strip()

            marker_match = DEVELOPMENT_MARKER_PATTERN.search(raw_line)
            if marker_match:
                marker_name = marker_match.group(1).upper()
                marker_text = marker_match.group(2).strip()
                findings.append(
                    (
                        relative_path,
                        line_number,
                        marker_name,
                        marker_text,
                    )
                )

            if stripped == "pass":
                findings.append(
                    (
                        relative_path,
                        line_number,
                        "PASS",
                        "Empty implementation",
                    )
                )

            if raw_line.lstrip().startswith("if False"):
                findings.append(
                    (
                        relative_path,
                        line_number,
                        "DISABLED",
                        raw_line.strip(),
                    )
                )

    print()
    print("Development Markers")
    print("=" * 19)

    if not findings:
        print("No development markers or disabled code found.")
        return

    location_width = max(
        len(f"{path}:{line_number}")
        for path, line_number, _, _ in findings
    )
    marker_width = max(len(marker) for _, _, marker, _ in findings)

    for path, line_number, marker, marker_text in findings:
        location = f"{path}:{line_number}"
        print(
            f"{location:<{location_width}}  "
            f"{marker:<{marker_width}}  "
            f"{marker_text}"
        )

# =============================================================================
# PYTHON: Discord Scan Functions
# =============================================================================
# =============================================================================
# PYTHON: Discord Scan Functions
# =============================================================================
DISCORD_COMMAND_DECORATORS = {"command", "hybrid_command", "context_menu"}
DISCORD_GROUP_DECORATORS = {"group", "hybrid_group"}
DISCORD_LISTENER_DECORATORS = {"listener", "event"}
DISCORD_UI_DECORATORS = {"button", "select"}
DISCORD_UI_BASES = {
    "discord.ui.Button", "discord.ui.DynamicItem", "discord.ui.Modal",
    "discord.ui.Select", "discord.ui.View", "Button", "DynamicItem",
    "Modal", "Select", "View",
}


def ast_name(node: ast.AST) -> str:
    """Return a readable dotted name for an AST expression."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = ast_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return ast_name(node.func)
    try:
        return ast.unparse(node)
    except Exception:
        return "?"


def decorator_name(decorator: ast.expr) -> str:
    """Return the dotted callable name used by a decorator."""
    return ast_name(decorator.func) if isinstance(decorator, ast.Call) else ast_name(decorator)


def decorator_leaf(decorator: ast.expr) -> str:
    """Return the final component of a decorator name."""
    return decorator_name(decorator).rsplit(".", 1)[-1]


def decorator_keyword(decorator: ast.expr, name: str) -> str | None:
    """Return a simple decorator keyword value as text."""
    if not isinstance(decorator, ast.Call):
        return None
    for keyword in decorator.keywords:
        if keyword.arg != name:
            continue
        if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
        try:
            return ast.unparse(keyword.value)
        except Exception:
            return None
    return None


def class_bases(node: ast.ClassDef) -> list[str]:
    """Return readable base-class names."""
    return [ast_name(base) for base in node.bases]


def class_is_discord_ui(node: ast.ClassDef) -> bool:
    """Return True when a class appears to inherit from a Discord UI base."""
    for base in class_bases(node):
        if base in DISCORD_UI_BASES or base.rsplit(".", 1)[-1] in DISCORD_UI_BASES:
            return True
    return False


def matching_decorator(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    accepted: set[str],
    name_fragments: tuple[str, ...] = (),
) -> ast.expr | None:
    """Return the first matching decorator."""
    for decorator in node.decorator_list:
        if decorator_leaf(decorator) not in accepted:
            continue
        full_name = decorator_name(decorator)
        if not name_fragments or any(fragment in full_name for fragment in name_fragments):
            return decorator
    return None


def command_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.expr | None:
    """Return a discord.py or Beacon command decorator."""
    accepted = DISCORD_COMMAND_DECORATORS | DISCORD_GROUP_DECORATORS
    return matching_decorator(
        node,
        accepted,
        ("commands", "app_commands", "beacon", ".command", ".group"),
    )


def listener_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.expr | None:
    """Return a listener or bot-event decorator."""
    return matching_decorator(node, DISCORD_LISTENER_DECORATORS)


def ui_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.expr | None:
    """Return a Discord UI component decorator."""
    return matching_decorator(node, DISCORD_UI_DECORATORS, ("ui", "button", "select"))


def loop_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.expr | None:
    """Return a discord.ext.tasks.loop decorator."""
    return matching_decorator(node, {"loop"}, ("tasks", "loop"))


def command_name(node: ast.FunctionDef | ast.AsyncFunctionDef, decorator: ast.expr) -> str:
    """Return a configured command name or the function name."""
    return decorator_keyword(decorator, "name") or node.name.replace("_", "-")


def loop_schedule(decorator: ast.expr) -> str:
    """Return a readable tasks.loop schedule."""
    if not isinstance(decorator, ast.Call):
        return "configured schedule"
    parts: list[str] = []
    labels = {
        "seconds": "every {} seconds",
        "minutes": "every {} minutes",
        "hours": "every {} hours",
        "time": "at {}",
        "count": "{} runs",
    }
    for keyword in decorator.keywords:
        if keyword.arg not in labels:
            continue
        try:
            value = ast.unparse(keyword.value)
        except Exception:
            value = "?"
        parts.append(labels[keyword.arg].format(value))
    return ", ".join(parts) if parts else "configured schedule"


def find_beacon_groups(tree: ast.Module) -> dict[str, str]:
    """Return Beacon group variables mapped to their configured names."""
    groups: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or not isinstance(node.value, ast.Call):
            continue
        called = ast_name(node.value.func)
        if not (called.endswith(".Group") and "beacon" in called):
            continue
        variables: list[str] = []
        if isinstance(node, ast.Assign):
            variables.extend(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node.target, ast.Name):
            variables.append(node.target.id)
        group_name = None
        for keyword in node.value.keywords:
            if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                if isinstance(keyword.value.value, str):
                    group_name = keyword.value.value
        for variable in variables:
            groups[variable] = group_name or variable
    return groups


def find_beacon_attachments(tree: ast.Module, groups: dict[str, str]) -> dict[str, list[str]]:
    """Return command function names attached through group.add_command()."""
    attached = {variable: [] for variable in groups}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "add_command" or not node.args:
            continue
        variable = ast_name(node.func.value)
        if variable in groups:
            attached[variable].append(ast_name(node.args[0]))
    return attached


def collect_interfaces(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    owner: str | None = None,
    owner_is_ui: bool = False,
) -> list[tuple[str, str]]:
    """Classify Discord interfaces attached to one function or method."""
    results: list[tuple[str, str]] = []
    target = f"{owner}.{node.name}" if owner else node.name

    decorator = command_decorator(node)
    if decorator is not None:
        name = command_name(node, decorator)
        leaf = decorator_leaf(decorator)
        if leaf in DISCORD_GROUP_DECORATORS:
            display = f"/{name} [group]"
        elif leaf == "context_menu":
            display = f"{name} [context menu]"
        else:
            display = f"/{name}"
        results.append(("Slash commands", f"{display}  {target}"))

    if listener_decorator(node) is not None:
        results.append(("Listeners", f"{node.name}  {target}"))

    decorator = ui_decorator(node)
    if decorator is not None:
        details = [decorator_leaf(decorator)]
        label = decorator_keyword(decorator, "label")
        custom_id = decorator_keyword(decorator, "custom_id")
        if label:
            details.append(f'label="{label}"')
        if custom_id:
            details.append(f"id={custom_id}")
        results.append(("UI callbacks", f"{target}  [{' | '.join(details)}]"))

    if owner_is_ui and node.name == "callback":
        results.append(("UI callbacks", target))

    decorator = loop_decorator(node)
    if decorator is not None:
        results.append(("Scheduled loops", f"{target}  {loop_schedule(decorator)}"))

    return results


def print_discord_group(heading: str, items: list[str], *, indent: str = "") -> None:
    """Print one Discord category when it contains results."""
    if not items:
        return
    print(f"{indent}{heading}:")
    for item in items:
        print(f"{indent}  {item}")


def discord_scan(root: Path) -> None:
    """Scan eligible Python files for discord.py and Beacon interfaces."""
    source_files, blank_files = discover_python_files(root)
    del blank_files

    print()
    print("Discord Interfaces")
    print("=" * 18)
    files_with_results = 0

    for path in source_files:
        relative_path = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except SyntaxError as error:
            print(f"\n{relative_path}\n  Syntax error on line {error.lineno or '?'}: {error.msg}")
            continue
        except (OSError, UnicodeDecodeError) as error:
            print(f"\n{relative_path}\n  Could not read this file: {error}")
            continue

        root_groups = {
            "Slash commands": [], "Listeners": [],
            "UI callbacks": [], "Scheduled loops": [],
        }
        class_results: list[tuple[str, dict[str, list[str]]]] = []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for category, item in collect_interfaces(node):
                    root_groups[category].append(item)
            elif isinstance(node, ast.ClassDef):
                groups = {
                    "Slash commands": [], "Listeners": [],
                    "UI callbacks": [], "Scheduled loops": [],
                }
                for child in node.body:
                    if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    for category, item in collect_interfaces(
                        child,
                        owner=node.name,
                        owner_is_ui=class_is_discord_ui(node),
                    ):
                        if item not in groups[category]:
                            groups[category].append(item)
                if any(groups.values()):
                    bases = class_bases(node)
                    label = f"class {node.name}({', '.join(bases)}):" if bases else f"class {node.name}():"
                    class_results.append((label, groups))

        beacon_groups = find_beacon_groups(tree)
        attachments = find_beacon_attachments(tree, beacon_groups)
        beacon_output: list[str] = []
        function_names: dict[str, str] = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorator = command_decorator(node)
                if decorator is not None:
                    function_names[node.name] = command_name(node, decorator)
        for variable, group_name in beacon_groups.items():
            commands = attachments.get(variable, [])
            if not commands:
                beacon_output.append(f"/{group_name}  {variable} [group]")
            for function in commands:
                shown_name = function_names.get(function, function.replace("_", "-"))
                beacon_output.append(f"/{group_name} {shown_name}  {function}")

        if not (any(root_groups.values()) or class_results or beacon_output):
            continue

        files_with_results += 1
        print(f"\n{relative_path}\n{'-' * len(relative_path)}")
        for heading, items in root_groups.items():
            print_discord_group(heading, items)
        print_discord_group("Beacon groups", beacon_output)

        for class_label, groups in class_results:
            print(f"\n{class_label}")
            for heading, items in groups.items():
                print_discord_group(heading, items, indent="  ")

    if files_with_results == 0:
        print("No Discord interfaces found.")
    else:
        print(f"\n>> {files_with_results:,} files with Discord interfaces found.")

# =============================================================================
# GENERAL: Project structure functions
# =============================================================================
def format_file_size(size_bytes: int) -> str:
    """Format a byte count using an appropriate unit."""
    if size_bytes < 1024:
        return f"{size_bytes:,} {'byte' if size_bytes == 1 else 'bytes'}"

    units = ("kb", "mb", "gb", "tb")
    size = float(size_bytes)

    for unit in units:
        size /= 1024
        if size < 1024 or unit == units[-1]:
            return f"{size:,.2f} {unit}"

    return f"{size_bytes:,} bytes"


def append_right_aligned_size(
    label: str,
    size_bytes: int,
    *,
    directory: bool,
) -> str:
    """Append a size marker aligned to the configured output width."""
    formatted_size = format_file_size(size_bytes)
    marker = (
        f"[ {formatted_size} ]"
        if directory
        else f"( {formatted_size} )"
    )
    padding = max(1, OUTPUT_WIDTH - len(label) - len(marker))
    return f"{label}{' ' * padding}{marker}"


def directory_contents(
    directory: Path,
    root: Path,
) -> tuple[list[Path], list[Path], list[Path]]:
    """Return included directories, ordinary files, and image files."""
    directories: list[Path] = []
    files: list[Path] = []
    images: list[Path] = []

    try:
        entries = list(directory.iterdir())
    except OSError as error:
        print(f"Could not inspect {directory}: {error}")
        return directories, files, images

    for entry in entries:
        # Skip files
        if path_component_is_excluded(entry.name):
            continue
        # Skip folders
        if should_exclude_path(entry, root):
            continue
        # Skip the script itself
        if entry.resolve() == Path(__file__).resolve():
            continue

        if entry.is_symlink():
            files.append(entry)
        elif entry.is_dir():
            directories.append(entry)
        elif entry.is_file():
            if entry.suffix.lower() in IMAGE_EXTENSIONS:
                images.append(entry)
            else:
                files.append(entry)

    directories.sort(key=lambda path: path.name.lower())
    files.sort(key=lambda path: path.name.lower())
    images.sort(key=lambda path: path.name.lower())

    return directories, files, images


def calculate_directory_size(directory: Path, root: Path) -> int:
    """Sum included descendant file sizes without following symlinks."""
    if directory in directory_size_cache:
        return directory_size_cache[directory]

    # Calculate the size of the directory and cache it.
    total_size = 0
    directories, files, images = directory_contents(directory, root)

    for file_path in files + images:
        try:
            if not file_path.is_symlink():
                total_size += file_path.stat().st_size
        except OSError as error:
            print(f"Could not inspect {file_path}: {error}")

    for child_directory in directories:
        total_size += calculate_directory_size(child_directory, root)

    # Store and return it
    directory_size_cache[directory] = total_size
    return total_size


def print_project_tree(
    directory: Path,
    root: Path,
    *,
    show_sizes: bool,
    prefix: str = "",
) -> None:
    """Recursively print a pipe-style directory tree."""
    directories, files, images = directory_contents(directory, root)

    # Directories are intentionally displayed before root or nested files.
    display_entries: list[tuple[str, object]] = [
        ("directory", path)
        for path in directories
    ]

    if images:
        display_entries.append(("images", images))

    display_entries.extend(("file", path) for path in files)

    for index, (entry_type, value) in enumerate(display_entries):
        is_last = index == len(display_entries) - 1
        connector = "└── " if is_last else "├── "
        child_prefix = prefix + ("    " if is_last else "│   ")

        if entry_type == "directory":
            path = value
            assert isinstance(path, Path)

            label = f"{prefix}{connector}{path.name}/"

            if show_sizes:
                label = append_right_aligned_size(
                    label,
                    calculate_directory_size(path, root),
                    directory=True,
                )

            print(label)
            print_project_tree(
                path,
                root,
                show_sizes=show_sizes,
                prefix=child_prefix,
            )

        elif entry_type == "images":
            image_paths = value
            assert isinstance(image_paths, list)

            image_word = "image" if len(image_paths) == 1 else "images"
            label = f"{prefix}{connector}🖼️ {len(image_paths):,} {image_word}"

            if show_sizes:
                image_size = 0
                for image_path in image_paths:
                    try:
                        image_size += image_path.stat().st_size
                    except OSError as error:
                        print(f"Could not inspect {image_path}: {error}")

                label = append_right_aligned_size(
                    label,
                    image_size,
                    directory=False,
                )

            print(label)

        else:
            path = value
            assert isinstance(path, Path)

            if path.is_symlink():
                label = f"{prefix}{connector}{path.name} → [symlink]"
            else:
                label = f"{prefix}{connector}{path.name}"

            if show_sizes and not path.is_symlink():
                try:
                    size_bytes = path.stat().st_size
                except OSError as error:
                    print(f"Could not inspect {path}: {error}")
                    size_bytes = 0

                label = append_right_aligned_size(
                    label,
                    size_bytes,
                    directory=False,
                )

            print(label)


def project_structure(root: Path) -> None:
    """Print the included project directory and file structure."""
    # The global cache is valid for one selected project scan. Clear it here
    # so repeated calls in a future multi-action menu cannot reuse stale sizes.
    directory_size_cache.clear()

    raw_choice = input("Do you want sizes? [y/n]: ").strip().lower()
    show_sizes = raw_choice in {"y", "yes"}

    print()
    root_label = f"[ {root.name}/ ]"

    if show_sizes:
        root_label = append_right_aligned_size(
            root_label,
            calculate_directory_size(root, root),
            directory=True,
        )

    print(root_label)
    print("│")
    print_project_tree(
        root,
        root,
        show_sizes=show_sizes,
    )


# =============================================================================
# Interactive Menu Functions
# =============================================================================
def prompt_for_project_directory() -> Path:
    """Ask for a directory, defaulting to the current working directory."""
    while True:
        raw_value = input(
            f"Project directory [{Path.cwd()}]: "
        ).strip()

        candidate = Path(raw_value).expanduser() if raw_value else Path.cwd()

        try:
            candidate = candidate.resolve()
        except OSError:
            print("That path could not be resolved.")
            continue

        if not candidate.exists():
            print("That path does not exist.")
            continue

        if not candidate.is_dir():
            print("That path is not a directory.")
            continue

        return candidate


def print_menu() -> None:
    """Print the CodeCheck insight menu."""
    show_root()
    print("[ General ]")
    print("1. Project structure")
    print()
    print("[ HTML ]")
    print("2. Check for completeness")
    print()
    print("[ Python ]")
    print("3. Lines of code")
    print("4. Explore code structure")
    print("5. Find markers and disabled code")
    print("6. Check syntax")
    print("7. Discord scan")
    print()
    print("0. Exit")


def main() -> None:
    """Run the interactive CodeCheck menu."""
    global project_root
    sayhello()
    project_root = prompt_for_project_directory()

    if not confirm_large_project(project_root):
        print("Cancelled.")
        return

    actions = {
        "1": project_structure,
        "2": html_completeness,
        "3": print_python_loc_report,
        "4": explore_python_structure,
        "5": find_python_markers,
        "6": check_python_syntax,
        "7": discord_scan,
    }

    took_action = False
    while not took_action:
        print_menu()
        choice = input("Select an option: ").strip()

        if choice == "0":
            print("Goodbye.")
            return

        action = actions.get(choice)

        if action is None:
            print("Please select a menu option from 0 through 7.")
            continue

        action(project_root)
        took_action = True

def show_root() -> None:
    """Print the current working directory."""
    print()
    print(f"Project root: {project_root if project_root else Path.cwd()}")
    print()

def sayhello() -> None:
    """Print a friendly greeting."""
    print("=" * 80)
    leftlength = len(CODECHECK_HI)
    rightlength = len(CODECHECK_VERSION)
    padding = 80 - leftlength - rightlength
    print(f"{CODECHECK_HI}{' ' * padding}{CODECHECK_VERSION}")

if __name__ == "__main__":
    main()
### EOF ###