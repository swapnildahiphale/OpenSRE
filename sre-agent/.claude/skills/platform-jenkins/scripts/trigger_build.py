#!/usr/bin/env python3
import argparse

from jenkins_common import add_env_arg, print_json, trigger_job_build


def _parse_params(raw_params: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for raw_param in raw_params:
        if "=" not in raw_param:
            raise RuntimeError(
                f"Invalid --param value: {raw_param}. Expected KEY=VALUE."
            )
        key, value = raw_param.split("=", 1)
        if not key:
            raise RuntimeError(
                f"Invalid --param value: {raw_param}. Parameter name is empty."
            )
        params[key] = value
    return params


def main() -> int:
    parser = argparse.ArgumentParser(description="Trigger a Jenkins build.")
    add_env_arg(parser)
    parser.add_argument(
        "--job-path", required=True, help="Slash-delimited Jenkins job path."
    )
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        help="Build parameter in KEY=VALUE form. Repeat for multiple parameters.",
    )
    args = parser.parse_args()

    params = _parse_params(args.param)
    print_json(trigger_job_build(args.env, args.job_path, params))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
