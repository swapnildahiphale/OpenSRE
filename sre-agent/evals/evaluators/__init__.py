"""Evaluators for OpenSRE investigation experiments.

Split by cost and by what they can decide:
  code.py   deterministic process/shape checks — free, repeatable
  judge.py  LLM-as-a-judge quality checks — costs a model call, needs calibration
"""

from .code import CODE_EVALUATORS
from .judge import JUDGE_EVALUATORS
from .run_level import RUN_EVALUATORS

__all__ = ["CODE_EVALUATORS", "JUDGE_EVALUATORS", "RUN_EVALUATORS"]
