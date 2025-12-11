"""Helpers for loading agent prompts/instructions."""

from pathlib import Path
from typing import Union

import yaml


DEFAULT_PROMPTS_FILE = Path(__file__).parent / "prompts.yaml"


def load_instruction(prompts_file: Union[str, Path] = DEFAULT_PROMPTS_FILE) -> str:
    path = Path(prompts_file)
    prompts_data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if isinstance(prompts_data, dict) and "instruction" in prompts_data:
        return str(prompts_data["instruction"])

    if isinstance(prompts_data, str):
        return prompts_data

    raise ValueError(f"Instruction not found in {path}")

