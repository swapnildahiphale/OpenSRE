#!/usr/bin/env python3
import argparse

from jenkins_common import (
    DEFAULT_BUILD_TIMEOUT_SECONDS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_QUEUE_TIMEOUT_SECONDS,
    add_env_arg,
    print_json,
    wait_for_build_completion,
    wait_for_queue_executable,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Wait for a Jenkins queue item or build to complete."
    )
    add_env_arg(parser)
    parser.add_argument(
        "--job-path", required=True, help="Slash-delimited Jenkins job path."
    )
    parser.add_argument(
        "--queue-id",
        type=int,
        help="Jenkins queue item id to resolve into a build number.",
    )
    parser.add_argument(
        "--build-number", type=int, help="Jenkins build number to wait on directly."
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help="Polling interval while waiting for queue/build state changes.",
    )
    parser.add_argument(
        "--queue-timeout-seconds",
        type=float,
        default=DEFAULT_QUEUE_TIMEOUT_SECONDS,
        help="Maximum time to wait for a queue item to start executing.",
    )
    parser.add_argument(
        "--build-timeout-seconds",
        type=float,
        default=DEFAULT_BUILD_TIMEOUT_SECONDS,
        help="Maximum time to wait for the build to complete.",
    )
    args = parser.parse_args()

    if args.queue_id is None and args.build_number is None:
        raise RuntimeError("Either --queue-id or --build-number is required.")

    queue_result = None
    build_number = args.build_number
    if args.queue_id is not None:
        queue_result = wait_for_queue_executable(
            args.env,
            args.queue_id,
            poll_interval_seconds=args.poll_interval_seconds,
            timeout_seconds=args.queue_timeout_seconds,
        )
        build_number = int(queue_result["buildNumber"])

    if build_number is None:
        raise RuntimeError("Could not determine Jenkins build number.")

    build_info = wait_for_build_completion(
        args.env,
        args.job_path,
        build_number,
        poll_interval_seconds=args.poll_interval_seconds,
        timeout_seconds=args.build_timeout_seconds,
    )

    print_json(
        {
            "build": build_info,
            "buildNumber": build_number,
            "environment": args.env,
            "jobPath": args.job_path,
            "queue": queue_result,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
