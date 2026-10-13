"""Versioned catalog for the checked-in Master and Modular workbooks.

The web layer must use this catalog instead of accepting filesystem paths or
guessing a template from a user supplied filename.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = (ROOT / "templates").resolve()


@dataclass(frozen=True)
class TemplateDefinition:
    template_id: str
    template_type: str
    module: str
    filename: str
    path: str
    sha256: str
    size_bytes: int

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("path", None)
        return data


def _definition(path: Path, template_type: str, module: str) -> TemplateDefinition:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return TemplateDefinition(
        template_id=f"{template_type}:{module}",
        template_type=template_type,
        module=module,
        filename=path.name,
        path=str(path),
        sha256=digest,
        size_bytes=path.stat().st_size,
    )


def list_templates() -> List[TemplateDefinition]:
    entries: List[TemplateDefinition] = []
    master_dir = TEMPLATE_ROOT / "master"
    modular_dir = TEMPLATE_ROOT / "modular"
    # Only one canonical master workbook is exposed; the *_updated copy is a
    # checked-in historical artifact and must not create a second UI option.
    master = master_dir / "Master_Client_Onboarding_Template_updated.xlsx"
    if not master.exists():
        master = master_dir / "Master_Client_Onboarding_Template.xlsx"
    if master.exists():
        entries.append(_definition(master, "master", "all"))
    for path in sorted(modular_dir.glob("*.xlsx")):
        module = path.stem.removeprefix("template_")
        entries.append(_definition(path, "modular", module))
    return entries


def get_template(template_type: str, module: Optional[str] = None) -> TemplateDefinition:
    template_type = template_type.strip().lower()
    module = (module or "all").strip().lower()
    for definition in list_templates():
        if definition.template_type == template_type and definition.module == module:
            return definition
    raise KeyError(f"Unknown template selection: {template_type}:{module}")

