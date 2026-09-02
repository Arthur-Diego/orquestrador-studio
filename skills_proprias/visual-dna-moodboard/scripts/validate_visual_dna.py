#!/usr/bin/env python3
"""Validate a Visual DNA JSON artifact without external dependencies."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


CONFIDENCE = {"low", "medium", "high"}
OBSERVATION_TYPES = {"observed", "inferred", "unknown"}
HEX_RE = re.compile(r"^#[0-9A-F]{6}$")
REQUIRED_TOP_LEVEL = {
    "schema_version",
    "source",
    "summary",
    "visual_dna",
    "aesthetics",
    "palette",
    "observations",
    "search_queries",
    "moodboard_plan",
    "references",
    "uncertainties",
}


def is_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Root must be a JSON object."]

    missing = sorted(REQUIRED_TOP_LEVEL - data.keys())
    if missing:
        errors.append(f"Missing top-level fields: {', '.join(missing)}")

    if data.get("schema_version") != "1.0":
        errors.append("schema_version must be '1.0'.")

    source = data.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object.")
    elif source.get("url") is not None and not is_http_url(source.get("url")):
        errors.append("source.url must be null or an absolute HTTP(S) URL.")

    aesthetics = data.get("aesthetics")
    if not isinstance(aesthetics, dict) or not isinstance(aesthetics.get("primary"), dict):
        errors.append("aesthetics.primary must be an object.")
    else:
        confidence = aesthetics["primary"].get("confidence")
        if confidence not in CONFIDENCE:
            errors.append("aesthetics.primary.confidence must be low, medium, or high.")

    palette = data.get("palette")
    if not isinstance(palette, list):
        errors.append("palette must be an array.")
    else:
        if not 4 <= len(palette) <= 8:
            errors.append("palette should contain 4 to 8 colors.")
        for index, color in enumerate(palette):
            if not isinstance(color, dict):
                errors.append(f"palette[{index}] must be an object.")
                continue
            if not HEX_RE.fullmatch(str(color.get("hex", ""))):
                errors.append(f"palette[{index}].hex must match #RRGGBB in uppercase.")
            if not isinstance(color.get("approximate"), bool):
                errors.append(f"palette[{index}].approximate must be boolean.")

    observations = data.get("observations")
    if not isinstance(observations, list):
        errors.append("observations must be an array.")
    else:
        for index, item in enumerate(observations):
            if not isinstance(item, dict):
                errors.append(f"observations[{index}] must be an object.")
                continue
            if item.get("observation_type") not in OBSERVATION_TYPES:
                errors.append(
                    f"observations[{index}].observation_type must be observed, inferred, or unknown."
                )
            if item.get("confidence") not in CONFIDENCE:
                errors.append(f"observations[{index}].confidence must be low, medium, or high.")

    queries = data.get("search_queries")
    if not isinstance(queries, list):
        errors.append("search_queries must be an array.")
    else:
        for index, item in enumerate(queries):
            if not isinstance(item, dict) or not str(item.get("query", "")).strip():
                errors.append(f"search_queries[{index}].query must be a non-empty string.")

    plan = data.get("moodboard_plan")
    if not isinstance(plan, dict):
        errors.append("moodboard_plan must be an object.")
    else:
        target_count = plan.get("target_count")
        if not isinstance(target_count, int) or isinstance(target_count, bool) or target_count < 1:
            errors.append("moodboard_plan.target_count must be a positive integer.")

    references = data.get("references")
    if not isinstance(references, list):
        errors.append("references must be an array.")
    else:
        for index, item in enumerate(references):
            if not isinstance(item, dict):
                errors.append(f"references[{index}] must be an object.")
                continue
            url = item.get("url")
            if url is not None and not is_http_url(url):
                errors.append(f"references[{index}].url must be an absolute HTTP(S) URL.")
            scores = item.get("scores", {})
            if scores is not None and not isinstance(scores, dict):
                errors.append(f"references[{index}].scores must be an object when provided.")
            elif isinstance(scores, dict):
                for key, score in scores.items():
                    if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 5:
                        errors.append(f"references[{index}].scores.{key} must be an integer from 0 to 5.")

    for key in ("summary",):
        if key in data and not isinstance(data[key], str):
            errors.append(f"{key} must be a string.")
    for key in ("references", "uncertainties"):
        if key in data and not isinstance(data[key], list):
            errors.append(f"{key} must be an array.")

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_visual_dna.py <visual-dna.json>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read valid UTF-8 JSON: {exc}", file=sys.stderr)
        return 2

    errors = validate(data)
    if errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
        return 1

    print("VALID: Visual DNA JSON conforms to schema version 1.0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
