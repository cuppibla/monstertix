"""Loading the course from content/, in any language it has been translated to.

A step is a folder under content/steps/ named NN-slug; the number is the order.

    step.yaml        meta, parts, exercises and checks, in English
    a-something.md   one part's reading, in English
    step.es.yaml     optional: only the strings that differ in Spanish
    a-something.es.md

A translation never has to be complete. Each file falls back to English on its
own, and a step.<lang>.yaml overlay only needs the keys it translates: maps are
merged key by key, and lists of maps are matched by `id` (or by position when
the entries have none). Commands, probes and file paths are never translated,
so an overlay that leaves them out keeps the English ones.

Content is re-read on every request, so an author sees an edit on reload.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from workbench import config

LANG = re.compile(r"^[a-z]{2}(-[A-Za-z]{2})?$")


def clean(lang: str | None) -> str:
    return lang if lang and LANG.match(lang) else config.DEFAULT_LANG


def merge(base: Any, over: Any) -> Any:
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for key, value in over.items():
            out[key] = merge(base[key], value) if key in base else value
        return out
    if isinstance(base, list) and isinstance(over, list):
        if all(isinstance(x, dict) and "id" in x for x in base + over):
            index = {x["id"]: x for x in over}
            return [merge(x, index[x["id"]]) if x["id"] in index else x for x in base]
        return [merge(b, o) for b, o in zip(base, over)] + base[len(over):]
    return over if over not in (None, "") else base


def _load(path: Path) -> tuple[dict[str, Any], str]:
    """A YAML file as a dict, and the parse error if it has one. A typo in
    one step.yaml must not take the whole course down: the page gets the
    error text where the step would be, and every other step still loads."""
    if not path.exists():
        return {}, ""
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as error:
        return {}, f"{path.relative_to(config.ROOT)}: {error}"
    return (data if isinstance(data, dict) else {}), ""


def _yaml(path: Path, lang: str) -> dict[str, Any]:
    data, _ = _load(path)
    if lang != config.DEFAULT_LANG:
        overlay = path.with_name(f"{path.stem}.{lang}{path.suffix}")
        over, _ = _load(overlay)
        if over:
            data = merge(data, over)
    return data


def _text(path: Path, lang: str) -> str:
    if lang != config.DEFAULT_LANG:
        translated = path.with_name(f"{path.stem}.{lang}{path.suffix}")
        if translated.exists():
            return translated.read_text()
    return path.read_text() if path.exists() else ""


def languages() -> list[str]:
    """English, and every language at least one file has been translated to."""
    found = {config.DEFAULT_LANG}
    for path in config.CONTENT.rglob("*.*.*"):
        code = path.suffixes[-2].lstrip(".") if len(path.suffixes) >= 2 else ""
        if LANG.match(code):
            found.add(code)
    return sorted(found, key=lambda c: (c != config.DEFAULT_LANG, c))


def course(lang: str) -> dict[str, Any]:
    return _yaml(config.CONTENT / "course.yaml", lang)


def _folders() -> list[tuple[int, str, Path]]:
    out = []
    if not config.STEPS.exists():
        return out
    for folder in sorted(config.STEPS.iterdir()):
        prefix, _, slug = folder.name.partition("-")
        if folder.is_dir() and prefix.isdigit() and (folder / "step.yaml").exists():
            out.append((int(prefix), slug, folder))
    return out


def _step(order: int, slug: str, folder: Path, lang: str, full: bool) -> dict[str, Any]:
    meta = _yaml(folder / "step.yaml", lang)
    _, error = _load(folder / "step.yaml")
    parts = []
    for index, part in enumerate(meta.get("parts") or [{"body": "step.md"}]):
        entry = {"id": str(part.get("id", "")), "label": part.get("label", ""),
                 "headline": part.get("headline", ""),
                 # The live venue panel in a left column, for this part only.
                 "venue": bool(part.get("venue"))}
        if full:
            entry |= {
                "body": _text(folder / part["body"], lang) if part.get("body") else "",
                "exercises": part.get("exercises") or {},
                "checks": [_public(c) for c in part.get("checks") or []],
                # What the ADK web UI and the venue should show: the top of the verify card.
                "expect": part.get("expect") or [],
                "checksTitle": part.get("checksTitle", ""),
            }
        else:
            entry["checkCount"] = len(part.get("checks") or [])
        parts.append(entry)
    return {
        "slug": meta.get("slug", slug),
        "order": order,
        "title": meta.get("title", slug),
        "kicker": meta.get("kicker", f"Chapter {order}"),
        "minutes": int(meta.get("minutes", 10)),
        "color": meta.get("color", "cyan"),
        "summary": meta.get("summary", ""),
        "venue": bool(meta.get("venue")),
        "stage": meta.get("stage"),
        # Listed after the chapters, as reference, not as a step of the course.
        "appendix": bool(meta.get("appendix")),
        # A step.yaml that does not parse: the page shows this instead of the step.
        "error": error,
        "parts": parts,
    }


# Probes that look only at the newest session, or at what happened since it
# started, so an old order or an old tool call cannot pass a check.
SESSION_FLAGS = ("--current", "--since-session")
SESSION_QUESTIONS = ("authorization", "guard", "retry", "resumed", "task")


def _public(check: dict[str, Any]) -> dict[str, Any]:
    """A check as the page sees it: the probe stays on the server."""
    probe = str(check.get("probe", ""))
    words = probe.split()
    session_only = any(flag in words for flag in SESSION_FLAGS) or (
        len(words) >= 4 and words[1:3] == ["-m", "workbench.probe"] and words[3] in SESSION_QUESTIONS)
    return {"id": check["id"], "label": check.get("label", ""), "hint": check.get("hint", ""),
            "expected": check.get("expect") == "fail", "note": check.get("note", ""),
            "scope": "session" if session_only else ""}


def all_steps(lang: str) -> list[dict[str, Any]]:
    return [_step(o, s, f, lang, full=False) for o, s, f in _folders()]


def step(slug: str, lang: str) -> dict[str, Any] | None:
    for order, name, folder in _folders():
        meta, _ = _load(folder / "step.yaml")
        if meta.get("slug", name) == slug:
            return _step(order, name, folder, lang, full=True)
    return None


def _raw(slug: str) -> dict[str, Any] | None:
    """The English step.yaml: where commands and probes are looked up."""
    for _, name, folder in _folders():
        meta, _ = _load(folder / "step.yaml")
        if meta.get("slug", name) == slug:
            return meta
    return None


def checks(slug: str, part: str | None) -> list[dict[str, Any]]:
    meta = _raw(slug) or {}
    found = []
    for entry in meta.get("parts") or []:
        if part is None or str(entry.get("id", "")) == part:
            found += entry.get("checks") or []
    return found


def task(slug: str, task_id: str) -> dict[str, Any] | None:
    meta = _raw(slug) or {}
    for part in meta.get("parts") or []:
        for exercise in (part.get("exercises") or {}).values():
            for item in exercise.get("tasks") or []:
                if item.get("id") == task_id:
                    return item
    return None
