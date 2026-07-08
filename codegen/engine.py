"""Codegen engine — Jinja2 template rendering with AST-targeted diffs.

Renders templates against stub coordinates found by the AST parser.
The engine is restricted to processing only the target block, outputting
exactly the replacement code with AST replacements injected.
"""

import os
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from codegen.ast_parser import StubCoordinate, find_stubs, validate_patch_is_surgical


TEMPLATE_DIR = Path(__file__).parent / "templates"

STUB_LINE_PATTERNS = {
    "pass",
    "...",
    "raise NotImplementedError",
    "raise NotImplementedError()",
    "return",
    "return None",
}


class CodegenEngine:
    """Template rendering engine for AST-targeted code generation."""

    def __init__(self, template_dir: Optional[Path] = None):
        self.template_dir = template_dir or TEMPLATE_DIR
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def list_templates(self) -> list[str]:
        return self.env.list_templates()

    def render(self, template_name: str, context: dict) -> str:
        template = self.env.get_template(template_name)
        return template.render(**context)

    def generate_patch(
        self,
        stub: StubCoordinate,
        implementation: str,
        template_name: str = "fix_stub.j2",
        extra_context: Optional[dict] = None,
    ) -> str:
        """Generate a surgical patch for a stub using a template.

        Builds a replacement string by taking the original stub function
        source, finding the line containing the stub pattern, and replacing
        it with the implementation. This is then rendered through the template.

        Args:
            stub: StubCoordinate of the target stub.
            implementation: The replacement code for the stub body line.
            template_name: Template to render with.
            extra_context: Additional template variables.

        Returns:
            The rendered replacement code.

        Raises:
            ValueError: If the generated patch fails surgical validation.
        """
        original_lines = stub.source_lines

        # Build replacement: keep all lines, but replace stub body lines
        replacement_lines = []
        for line in original_lines:
            stripped = line.strip()
            if stripped in STUB_LINE_PATTERNS:
                replacement_lines.append(implementation)
            else:
                replacement_lines.append(line.rstrip("\n"))

        replacement = "\n".join(replacement_lines)

        context = {
            "original_code": "\n".join(stub.source_lines) if stub.source_lines else "",
            "replacement": replacement,
            "function_name": stub.name,
            "stub_type": stub.stub_type,
            "implementation": implementation,
            "indent": stub.indent,
        }
        if extra_context:
            context.update(extra_context)

        rendered = self.render(template_name, context)
        rendered_lines = rendered.splitlines()

        if not validate_patch_is_surgical(stub, rendered_lines):
            raise ValueError(
                f"Generated patch for '{stub.name}' failed surgical validation: "
                f"{len(rendered_lines)} lines vs {len(stub.source_lines)} original lines"
            )

        return rendered


def find_stubs_in_file(source_path: str) -> list[StubCoordinate]:
    """Convenience wrapper around ast_parser.find_stubs."""
    return find_stubs(source_path)
