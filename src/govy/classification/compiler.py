"""Ruleset compiler: loads core + tribunal overlay, merges, validates, and returns a compiled ruleset.

Handles the tabs-based structure: CLASSES, PROCEDURES, TIE_BREAKERS, EQUIVALENCES, DESCARTE.
Merge is deterministic: append+dedupe by default, replace when overlay specifies _replace.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Root of the rules directory (repo_root/rules/)
_RULES_DIR = Path(__file__).resolve().parents[3] / "rules"

# Tabs that merge by "id" (core + overlay items with same id get merged)
_MERGEABLE_TABS = ("CLASSES", "PROCEDURES", "TEMAS", "EFEITO", "RESULTADO", "STANCE", "ALVO", "QUOTES", "DESCARTE")

# Tabs that come only from overlay (appended, not merged by id)
_OVERLAY_ONLY_TABS = ("TIE_BREAKERS", "EQUIVALENCES")

# Pattern strength keys
_PATTERN_STRENGTHS = ("strong", "weak", "negative")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompiledClass:
    """A single document class with pre-compiled regex patterns."""

    id: str
    label: str
    priority: int
    enabled: bool
    whitelist: bool
    confidence_rules: Dict[str, float]
    sources_priority: List[str]
    strong_patterns: tuple[re.Pattern[str], ...]
    weak_patterns: tuple[re.Pattern[str], ...]
    negative_patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class CompiledProcedure:
    """A procedure/flag with pre-compiled patterns."""

    id: str
    label: str
    priority: int
    enabled: bool
    scoring: Dict[str, float]
    sources_priority: List[str]
    strong_patterns: tuple[re.Pattern[str], ...]
    weak_patterns: tuple[re.Pattern[str], ...]
    negative_patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class CompiledRuleset:
    """Immutable compiled ruleset ready for classification."""

    tribunal_id: str
    classes: Dict[str, CompiledClass]
    procedures: Dict[str, CompiledProcedure]
    tie_breakers: List[Dict[str, Any]]
    equivalences: List[Dict[str, Any]]
    discard_rules: List[Dict[str, Any]]
    globals: Dict[str, Any]
    tabs_raw: Dict[str, Any]
    ruleset_hash: str
    core_version: str
    tribunal_version: Optional[str]
    compiled_at: str
    meta: Dict[str, Any]


class RulesetCompilationError(Exception):
    """Raised when ruleset compilation fails."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_ruleset(
    tribunal_id: str,
    *,
    rules_dir: Optional[Path] = None,
) -> CompiledRuleset:
    """Load core rules + tribunal overlay, merge, validate, and compile.

    Args:
        tribunal_id: Tribunal identifier (e.g. "tce-sp"). Use "core" to load
            only the base rules without any overlay.
        rules_dir: Override the default rules directory (useful for testing).

    Returns:
        A compiled, immutable ruleset with pre-compiled regex patterns.

    Raises:
        FileNotFoundError: If core.json or the tribunal overlay is missing.
        RulesetCompilationError: If validation fails (bad regex, missing fields, etc.).
    """
    base = rules_dir or _RULES_DIR

    # 1. Load core
    core_path = base / "core.json"
    if not core_path.exists():
        raise FileNotFoundError(f"Core rules not found: {core_path}")
    core = _load_json(core_path)

    # 2. Load overlay (optional for "core" tribunal)
    overlay: Optional[Dict[str, Any]] = None
    tribunal_version: Optional[str] = None
    if tribunal_id != "core":
        overlay_path = base / "tribunals" / f"{tribunal_id}.json"
        if not overlay_path.exists():
            raise FileNotFoundError(f"Tribunal overlay not found: {overlay_path}")
        overlay = _load_json(overlay_path)
        tribunal_version = overlay.get("version")

    # 3. Merge
    merged = _merge(core, overlay)

    # 4. Hash (on the merged JSON, before compiling patterns)
    ruleset_hash = hashlib.sha256(
        json.dumps(merged, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()

    # 5. Validate regex in all tabs
    _validate_all_patterns(merged)

    # 6. Compile classes and procedures
    tabs = merged.get("tabs", {})
    compiled_classes = _compile_classes(tabs.get("CLASSES", []))
    compiled_procedures = _compile_procedures(tabs.get("PROCEDURES", []))

    return CompiledRuleset(
        tribunal_id=tribunal_id,
        classes=compiled_classes,
        procedures=compiled_procedures,
        tie_breakers=tabs.get("TIE_BREAKERS", []),
        equivalences=tabs.get("EQUIVALENCES", []),
        discard_rules=tabs.get("DESCARTE", []),
        globals=merged.get("globals", {}),
        tabs_raw=tabs,
        ruleset_hash=ruleset_hash,
        core_version=core.get("version", "unknown"),
        tribunal_version=tribunal_version,
        compiled_at=datetime.now(timezone.utc).isoformat(),
        meta=merged.get("meta", {}),
    )


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _deep_merge_dict(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge dict b into a (b wins on conflict)."""
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_dict(out[k], v)
        else:
            out[k] = v
    return out


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    """Deduplicate a list preserving insertion order."""
    seen: set[str] = set()
    out: List[str] = []
    for x in items:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def _merge_pattern_lists(
    base_list: List[str],
    overlay_list: List[str],
    replace: bool = False,
) -> List[str]:
    if replace:
        return _dedupe_preserve_order(overlay_list)
    return _dedupe_preserve_order(list(base_list) + list(overlay_list))


def _merge_patterns_dict(
    base_patterns: Dict[str, Any],
    ov_patterns: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge pattern dicts with _replace support."""
    out = dict(base_patterns)
    replace_flags = ov_patterns.get("_replace", {})
    if not isinstance(replace_flags, dict):
        replace_flags = {}

    for strength in _PATTERN_STRENGTHS:
        if strength in ov_patterns:
            out[strength] = _merge_pattern_lists(
                base_patterns.get(strength, []),
                ov_patterns[strength],
                replace=bool(replace_flags.get(strength, False)),
            )

    # Copy other keys (e.g. mode) but skip internal ones
    for k, v in ov_patterns.items():
        if k in _PATTERN_STRENGTHS or k == "_replace":
            continue
        out[k] = v

    return out


def _merge_rule_item(base: Dict[str, Any], ov: Dict[str, Any]) -> Dict[str, Any]:
    """Merge a single rule item (class/procedure/theme)."""
    out = dict(base)

    for k, v in ov.items():
        if k == "patterns" and isinstance(v, dict):
            out["patterns"] = _merge_patterns_dict(base.get("patterns", {}), v)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_dict(out[k], v)
        else:
            out[k] = v

    return out


def _merge_tab_by_id(
    base_items: List[Dict[str, Any]],
    overlay_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge two lists of items by 'id' key."""
    base_map = {x["id"]: x for x in base_items}
    order = [x["id"] for x in base_items]

    for ov in overlay_items:
        oid = ov["id"]
        if oid not in base_map:
            base_map[oid] = ov
            order.append(oid)
        else:
            base_map[oid] = _merge_rule_item(base_map[oid], ov)

    return [base_map[i] for i in order]


def _merge(
    core: Dict[str, Any],
    overlay: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Merge core + overlay into a single dict."""
    if overlay is None:
        return json.loads(json.dumps(core))  # deep copy

    merged = json.loads(json.dumps(core))  # deep copy

    # Merge globals (deep)
    if "globals" in overlay:
        merged["globals"] = _deep_merge_dict(
            merged.get("globals", {}),
            overlay["globals"],
        )

    # Merge meta
    if "meta" in overlay:
        merged["meta"] = _deep_merge_dict(
            merged.get("meta", {}),
            overlay["meta"],
        )

    # Merge tabs
    core_tabs = merged.get("tabs", {})
    ov_tabs = overlay.get("tabs", {})

    # Mergeable tabs: merge by id
    for tab_name in _MERGEABLE_TABS:
        if tab_name in ov_tabs:
            core_tabs[tab_name] = _merge_tab_by_id(
                core_tabs.get(tab_name, []),
                ov_tabs[tab_name],
            )

    # Overlay-only tabs: core items + overlay items (overlay appended, higher priority wins)
    for tab_name in _OVERLAY_ONLY_TABS:
        core_items = core_tabs.get(tab_name, [])
        ov_items = ov_tabs.get(tab_name, [])
        if ov_items:
            core_tabs[tab_name] = list(core_items) + list(ov_items)

    merged["tabs"] = core_tabs
    return merged


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_all_patterns(merged: Dict[str, Any]) -> None:
    """Validate that all regex patterns in all tabs compile."""
    tabs = merged.get("tabs", {})

    # Validate patterns in CLASSES and PROCEDURES
    for tab_name in ("CLASSES", "PROCEDURES"):
        for item in tabs.get(tab_name, []):
            item_id = item.get("id", "unknown")
            patterns = item.get("patterns", {})
            for strength in _PATTERN_STRENGTHS:
                for raw in patterns.get(strength, []):
                    _try_compile_pattern(f"{tab_name}/{item_id}", strength, raw)

    # Validate regex in TIE_BREAKERS conditions
    for rule in tabs.get("TIE_BREAKERS", []):
        rule_id = rule.get("id", "unknown")
        for cond_key in ("when_all", "when_any", "when_none"):
            for cond in rule.get(cond_key, []):
                if "regex" in cond:
                    _try_compile_pattern(f"TIE_BREAKERS/{rule_id}", cond_key, cond["regex"])

    # Validate regex in DESCARTE match patterns
    for rule in tabs.get("DESCARTE", []):
        rule_id = rule.get("id", "unknown")
        match = rule.get("match", {})
        for key in ("pattern_all", "pattern_any", "guardrail_none"):
            for raw in match.get(key, []):
                _try_compile_pattern(f"DESCARTE/{rule_id}", key, raw)


def _try_compile_pattern(context: str, strength: str, raw: str) -> None:
    """Try to compile a single regex, raising RulesetCompilationError on failure."""
    try:
        re.compile(raw, re.IGNORECASE | re.UNICODE | re.MULTILINE)
    except re.error as exc:
        raise RulesetCompilationError(
            f"{context}, {strength} pattern invalid: '{raw}' -> {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Compilation (patterns -> re.Pattern)
# ---------------------------------------------------------------------------


def _compile_pattern_list(
    context: str,
    strength: str,
    raw_patterns: List[str],
) -> tuple[re.Pattern[str], ...]:
    """Compile a list of regex strings into Pattern objects."""
    compiled = []
    for raw in raw_patterns:
        compiled.append(re.compile(raw, re.IGNORECASE | re.UNICODE | re.MULTILINE))
    return tuple(compiled)


def _compile_classes(
    classes_raw: List[Dict[str, Any]],
) -> Dict[str, CompiledClass]:
    """Compile all CLASSES items."""
    compiled: Dict[str, CompiledClass] = {}

    for cls in classes_raw:
        cid = cls.get("id", "unknown")

        # Required fields
        for req in ("id", "label", "priority", "patterns", "confidence_rules"):
            if req not in cls:
                raise RulesetCompilationError(
                    f"Class '{cid}' missing required field: '{req}'"
                )

        patterns = cls["patterns"]
        compiled[cid] = CompiledClass(
            id=cid,
            label=cls["label"],
            priority=cls["priority"],
            enabled=cls.get("enabled", True),
            whitelist=cls.get("whitelist", True),
            confidence_rules=cls["confidence_rules"],
            sources_priority=cls.get("sources_priority", ["text_head"]),
            strong_patterns=_compile_pattern_list(cid, "strong", patterns.get("strong", [])),
            weak_patterns=_compile_pattern_list(cid, "weak", patterns.get("weak", [])),
            negative_patterns=_compile_pattern_list(cid, "negative", patterns.get("negative", [])),
        )

    return compiled


def _compile_procedures(
    procedures_raw: List[Dict[str, Any]],
) -> Dict[str, CompiledProcedure]:
    """Compile all PROCEDURES items."""
    compiled: Dict[str, CompiledProcedure] = {}

    for proc in procedures_raw:
        pid = proc.get("id", "unknown")

        for req in ("id", "patterns"):
            if req not in proc:
                raise RulesetCompilationError(
                    f"Procedure '{pid}' missing required field: '{req}'"
                )

        patterns = proc["patterns"]
        compiled[pid] = CompiledProcedure(
            id=pid,
            label=proc.get("label", pid),
            priority=proc.get("priority", 0),
            enabled=proc.get("enabled", True),
            scoring=proc.get("scoring", {"strong_hit": 1.0, "weak_hit": 0.6, "neg_hit_penalty": -0.3}),
            sources_priority=proc.get("sources_priority", ["text_head"]),
            strong_patterns=_compile_pattern_list(pid, "strong", patterns.get("strong", [])),
            weak_patterns=_compile_pattern_list(pid, "weak", patterns.get("weak", [])),
            negative_patterns=_compile_pattern_list(pid, "negative", patterns.get("negative", [])),
        )

    return compiled
