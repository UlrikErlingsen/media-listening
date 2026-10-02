"""Load and validate brands.yaml and sources.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from .errors import DataProblem


def _home() -> Path:
    """Project folder holding brands.yaml, sources.yaml and data/: LISTENSIGNAL_HOME, the repo checkout, or cwd."""
    if os.getenv("LISTENSIGNAL_HOME"):
        return Path(os.environ["LISTENSIGNAL_HOME"]).expanduser().resolve()
    checkout = Path(__file__).resolve().parents[2]
    return checkout if (checkout / "sources.yaml").exists() else Path.cwd()


ROOT = _home()
DEFAULT_BRANDS = ROOT / "brands.yaml"
DEFAULT_SOURCES = ROOT / "sources.yaml"
DEFAULT_DB = ROOT / "data" / "listensignal.db"
# Copy of the seeded sources.yaml that ships inside the package (kept identical by a test). Signal Hub shows this
# list instead of reading a project folder on the server.
SEED_SOURCES = Path(__file__).resolve().parent / "seed_sources.yaml"

# The brief caps polling at once every 30 minutes per feed. The collector never goes below this.
MIN_POLL_MINUTES = 30
BRAND_ROLES = ("own", "competitor")


@dataclass(frozen=True)
class Brand:
    name: str
    aliases: tuple[str, ...]
    exclude: tuple[str, ...] = ()
    role: str = "competitor"
    case_sensitive: bool = False
    inflect: bool = True


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    enabled: bool = True
    kind: str = "news"
    note: str = ""
    verified: str = ""


@dataclass(frozen=True)
class SourceConfig:
    sources: tuple[Source, ...]
    min_interval_minutes: int = MIN_POLL_MINUTES
    extra: dict = field(default_factory=dict)

    @property
    def enabled(self) -> tuple[Source, ...]:
        return tuple(source for source in self.sources if source.enabled)


def _read_yaml(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise DataProblem(f"Configuration file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise DataProblem(f"{path.name} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise DataProblem(f"{path.name} must contain a mapping at the top level.")
    return data


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise DataProblem(f"{label} must be a list of strings.")
    items = tuple(str(item).strip() for item in value if str(item).strip())
    return items


def parse_brands(data: dict) -> tuple[Brand, ...]:
    """Validate a brands mapping (as read from YAML) into Brand objects."""
    raw = data.get("brands")
    if not isinstance(raw, list) or not raw:
        raise DataProblem("brands.yaml needs a non-empty 'brands:' list.")
    brands: list[Brand] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict) or not str(entry.get("name", "")).strip():
            raise DataProblem(f"Brand #{index} needs a 'name'.")
        name = str(entry["name"]).strip()
        if name.casefold() in seen:
            raise DataProblem(f"Brand '{name}' is defined twice.")
        seen.add(name.casefold())
        aliases = _string_list(entry.get("aliases"), f"Aliases for {name}") or (name,)
        if name not in aliases:
            aliases = (name, *aliases)
        role = str(entry.get("role", "competitor")).strip().lower()
        if role not in BRAND_ROLES:
            raise DataProblem(f"Brand '{name}' has role '{role}'; use 'own' or 'competitor'.")
        brands.append(
            Brand(
                name=name,
                aliases=aliases,
                exclude=_string_list(entry.get("exclude"), f"Exclusions for {name}"),
                role=role,
                case_sensitive=bool(entry.get("case_sensitive", False)),
                inflect=bool(entry.get("inflect", True)),
            )
        )
    return tuple(brands)


def load_brands(path: Path | str = DEFAULT_BRANDS) -> tuple[Brand, ...]:
    return parse_brands(_read_yaml(Path(path)))


def parse_sources(data: dict) -> SourceConfig:
    raw = data.get("sources")
    if not isinstance(raw, list) or not raw:
        raise DataProblem("sources.yaml needs a non-empty 'sources:' list.")
    sources: list[Source] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict):
            raise DataProblem(f"Source #{index} must be a mapping with name and url.")
        name = str(entry.get("name", "")).strip()
        url = str(entry.get("url", "")).strip()
        if not name or not url:
            raise DataProblem(f"Source #{index} needs both 'name' and 'url'.")
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise DataProblem(f"Source '{name}' needs an http(s) URL; got '{url}'.")
        if name.casefold() in seen:
            raise DataProblem(f"Source '{name}' is defined twice.")
        seen.add(name.casefold())
        sources.append(
            Source(
                name=name,
                url=url,
                enabled=bool(entry.get("enabled", True)),
                kind=str(entry.get("kind", "news")).strip() or "news",
                note=str(entry.get("note", "") or "").strip(),
                verified=str(entry.get("verified", "") or "").strip(),
            )
        )
    defaults = data.get("defaults") or {}
    try:
        interval = int(defaults.get("min_interval_minutes", MIN_POLL_MINUTES))
    except (TypeError, ValueError) as exc:
        raise DataProblem("defaults.min_interval_minutes must be a whole number of minutes.") from exc
    # Never poll more often than the 30-minute floor, whatever the file says.
    return SourceConfig(sources=tuple(sources), min_interval_minutes=max(interval, MIN_POLL_MINUTES))


def load_sources(path: Path | str = DEFAULT_SOURCES) -> SourceConfig:
    return parse_sources(_read_yaml(Path(path)))


def brands_to_yaml(brands: tuple[Brand, ...] | list[Brand]) -> str:
    """Serialize brands back to brands.yaml format (round-trips through parse_brands)."""
    entries = []
    for brand in brands:
        entry: dict = {"name": brand.name, "role": brand.role, "aliases": list(brand.aliases)}
        if brand.exclude:
            entry["exclude"] = list(brand.exclude)
        if brand.case_sensitive:
            entry["case_sensitive"] = True
        if not brand.inflect:
            entry["inflect"] = False
        entries.append(entry)
    return yaml.safe_dump({"brands": entries}, allow_unicode=True, sort_keys=False, default_flow_style=None, width=110)


def parse_brands_yaml(text: str) -> tuple[Brand, ...]:
    """Parse brands from YAML text (e.g. typed into the dashboard)."""
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise DataProblem(f"The brand list is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise DataProblem("The brand list must start with 'brands:'.")
    return parse_brands(data)
