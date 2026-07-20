#!/usr/bin/env python3
import argparse

from jenkins_common import add_env_arg, job_api_path, print_json, request_json

DEFAULT_TREE = (
    "name,fullName,url,"
    "builds[number,displayName,url,result,building,duration,timestamp]"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="List builds for a Jenkins job.")
    add_env_arg(parser)
    parser.add_argument(
        "--job-path", required=True, help="Slash-delimited Jenkins job path."
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="Maximum number of builds to return."
    )
    parser.add_argument(
        "--tree",
        default=DEFAULT_TREE,
        help="Optional Jenkins tree selector for the job response.",
    )
    args = parser.parse_args()

    data = request_json(
        "GET",
        args.env,
        job_api_path(args.job_path, "api/json"),
        query={"tree": args.tree} if args.tree else None,
    )
    builds = data.get("builds") or []
    data["builds"] = builds[: max(args.limit, 0)]
    print_json(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
