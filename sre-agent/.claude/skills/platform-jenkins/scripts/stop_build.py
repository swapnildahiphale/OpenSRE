#!/usr/bin/env python3
import argparse

from jenkins_common import add_env_arg, print_json, stop_job_build


def main() -> int:
    parser = argparse.ArgumentParser(description="Request Jenkins build stop.")
    add_env_arg(parser)
    parser.add_argument(
        "--job-path", required=True, help="Slash-delimited Jenkins job path."
    )
    parser.add_argument(
        "--build-number", required=True, type=int, help="Jenkins build number."
    )
    args = parser.parse_args()

    print_json(stop_job_build(args.env, args.job_path, args.build_number))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
