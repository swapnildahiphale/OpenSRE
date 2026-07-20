#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict

from jenkins_common import (
    DEFAULT_BUILD_TIMEOUT_SECONDS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_QUEUE_TIMEOUT_SECONDS,
    job_api_path,
    print_json,
    request_text,
    trigger_job_build,
    wait_for_build_completion,
    wait_for_queue_executable,
)

PLACEHOLDER_RE = re.compile(r"\$\{([^}]+)\}")


def _load_workflow(path: str) -> Dict[str, Any]:
    workflow_path = Path(path)
    try:
        data = json.loads(workflow_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Workflow file not found: {workflow_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Workflow file is not valid JSON: {workflow_path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError("Workflow file must contain a JSON object at the top level.")
    return data


def _resolve_expr(expr: str, context: Dict[str, Any]) -> Any:
    value: Any = context
    for segment in expr.split("."):
        if isinstance(value, dict) and segment in value:
            value = value[segment]
            continue
        raise RuntimeError(f"Unknown workflow placeholder: {expr}")
    return value


def _resolve_value(value: Any, context: Dict[str, Any]) -> Any:
    if isinstance(value, str):
        matches = list(PLACEHOLDER_RE.finditer(value))
        if not matches:
            return value
        if len(matches) == 1 and matches[0].span() == (0, len(value)):
            return _resolve_expr(matches[0].group(1), context)

        rendered = value
        for match in matches:
            resolved = _resolve_expr(match.group(1), context)
            rendered = rendered.replace(match.group(0), str(resolved))
        return rendered

    if isinstance(value, list):
        return [_resolve_value(item, context) for item in value]

    if isinstance(value, dict):
        return {key: _resolve_value(item, context) for key, item in value.items()}

    return value


def _normalize_step_id(step: Dict[str, Any], index: int) -> str:
    raw_value = step.get("id") or step.get("name") or f"step-{index}"
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", str(raw_value)).strip("_").lower()
    return normalized or f"step_{index}"


def _tail_console(env: str, job_path: str, build_number: int, tail_lines: int) -> str:
    console_text = request_text(
        "GET",
        env,
        job_api_path(job_path, f"{build_number}/consoleText"),
        follow_redirects=True,
    )
    lines = console_text.splitlines()
    return "\n".join(lines[-max(tail_lines, 0) :])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a chained Jenkins workflow from a JSON file."
    )
    parser.add_argument(
        "--workflow-file", required=True, help="Path to a JSON workflow definition."
    )
    parser.add_argument(
        "--default-env",
        choices=("legacy", "aws"),
        help="Optional fallback Jenkins environment for steps that omit env.",
    )
    args = parser.parse_args()

    workflow = _load_workflow(args.workflow_file)
    steps = workflow.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RuntimeError("Workflow file must contain a non-empty steps array.")

    workflow_name = str(workflow.get("name") or Path(args.workflow_file).stem)
    stop_on_failure = bool(workflow.get("stopOnFailure", True))
    default_env = args.default_env or workflow.get("defaultEnv")
    default_poll_interval = float(
        workflow.get("pollIntervalSeconds", DEFAULT_POLL_INTERVAL_SECONDS)
    )
    default_queue_timeout = float(
        workflow.get("queueTimeoutSeconds", DEFAULT_QUEUE_TIMEOUT_SECONDS)
    )
    default_build_timeout = float(
        workflow.get("buildTimeoutSeconds", DEFAULT_BUILD_TIMEOUT_SECONDS)
    )

    context: Dict[str, Any] = {"steps": {}, "workflow": {"name": workflow_name}}
    results = []
    failed = False
    continued_after_failure = False

    for index, raw_step in enumerate(steps, start=1):
        if not isinstance(raw_step, dict):
            raise RuntimeError(f"Workflow step #{index} must be a JSON object.")

        step_id = _normalize_step_id(raw_step, index)
        if step_id in context["steps"]:
            raise RuntimeError(f"Duplicate workflow step id: {step_id}")

        resolved_step = _resolve_value(raw_step, context)
        env = resolved_step.get("env") or default_env
        if not env:
            raise RuntimeError(
                f"Workflow step {step_id} is missing env and no default env was provided."
            )

        job_path = resolved_step.get("jobPath")
        if not job_path:
            raise RuntimeError(f"Workflow step {step_id} is missing jobPath.")

        parameters = resolved_step.get("parameters") or {}
        if not isinstance(parameters, dict):
            raise RuntimeError(
                f"Workflow step {step_id} parameters must be a JSON object."
            )

        wait_for_build = bool(resolved_step.get("waitForBuild", True))
        required_result = resolved_step.get(
            "requireResult", "SUCCESS" if wait_for_build else None
        )
        poll_interval = float(
            resolved_step.get("pollIntervalSeconds", default_poll_interval)
        )
        queue_timeout = float(
            resolved_step.get("queueTimeoutSeconds", default_queue_timeout)
        )
        build_timeout = float(
            resolved_step.get("buildTimeoutSeconds", default_build_timeout)
        )
        console_tail_lines = resolved_step.get("consoleTailLinesOnFailure")
        continue_on_failure = bool(resolved_step.get("continueOnFailure", False))

        step_result: Dict[str, Any] = {
            "environment": env,
            "id": step_id,
            "jobPath": job_path,
            "name": resolved_step.get("name") or step_id,
            "parameters": parameters,
            "status": "TRIGGERING",
        }

        try:
            trigger_result = trigger_job_build(env, job_path, parameters)
            step_result.update(trigger_result)
            step_result["status"] = "TRIGGERED"

            if wait_for_build:
                queue_id = trigger_result.get("queueId")
                if queue_id is None:
                    raise RuntimeError(
                        f"Workflow step {step_id} did not return a Jenkins queue id. "
                        "Cannot chain reliably without queue tracking."
                    )

                queue_result = wait_for_queue_executable(
                    env,
                    int(queue_id),
                    poll_interval_seconds=poll_interval,
                    timeout_seconds=queue_timeout,
                )
                build_number = int(queue_result["buildNumber"])
                step_result["queue"] = queue_result["queueItem"]
                step_result["buildNumber"] = build_number
                step_result["buildUrl"] = queue_result.get("buildUrl")
                step_result["status"] = "RUNNING"

                build_info = wait_for_build_completion(
                    env,
                    job_path,
                    build_number,
                    poll_interval_seconds=poll_interval,
                    timeout_seconds=build_timeout,
                )
                step_result["build"] = build_info
                step_result["result"] = build_info.get("result")
                step_result["status"] = "COMPLETED"

                if required_result and step_result.get("result") != required_result:
                    if console_tail_lines:
                        step_result["consoleTail"] = _tail_console(
                            env,
                            job_path,
                            build_number,
                            int(console_tail_lines),
                        )
                    raise RuntimeError(
                        f"Workflow step {step_id} completed with Jenkins result "
                        f"{step_result.get('result')} but required {required_result}."
                    )
            else:
                step_result["status"] = "QUEUED"

        except Exception as exc:
            step_result["status"] = "FAILED"
            step_result["error"] = str(exc)
            failed = True
            results.append(step_result)
            context["steps"][step_id] = step_result
            if stop_on_failure and not continue_on_failure:
                break
            continued_after_failure = True
            continue

        results.append(step_result)
        context["steps"][step_id] = step_result

    workflow_status = "SUCCESS"
    if failed and (len(results) < len(steps) or not continued_after_failure):
        workflow_status = "FAILED"
    elif failed:
        workflow_status = "PARTIAL_FAILURE"

    print_json(
        {
            "name": workflow_name,
            "status": workflow_status,
            "steps": results,
            "stopOnFailure": stop_on_failure,
            "workflowFile": str(Path(args.workflow_file).resolve()),
        }
    )
    return 0 if workflow_status == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
