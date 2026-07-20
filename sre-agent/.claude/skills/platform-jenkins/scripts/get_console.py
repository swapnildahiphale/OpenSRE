#!/usr/bin/env python3
import argparse

from jenkins_common import add_env_arg, job_api_path, request_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Jenkins console output.")
    add_env_arg(parser)
    parser.add_argument(
        "--job-path", required=True, help="Slash-delimited Jenkins job path."
    )
    parser.add_argument(
        "--build-number", required=True, type=int, help="Jenkins build number."
    )
    parser.add_argument(
        "--tail-lines",
        type=int,
        help="If set, only print the last N lines of console output.",
    )
    args = parser.parse_args()

    console_text = request_text(
        "GET",
        args.env,
        job_api_path(args.job_path, f"{args.build_number}/consoleText"),
    )
    if args.tail_lines is not None:
        lines = console_text.splitlines()
        console_text = "\n".join(lines[-max(args.tail_lines, 0) :])
        if console_text:
            console_text += "\n"

    print(console_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
