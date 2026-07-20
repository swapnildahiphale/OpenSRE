#!/usr/bin/env python3
import argparse

from jenkins_common import add_env_arg, job_api_path, print_json, request_json

DEFAULT_TREE = (
    "number,displayName,fullDisplayName,result,building,duration,estimatedDuration,"
    "timestamp,url,description,builtOn,changeSets[items[msg,author[fullName]]],"
    "artifacts[displayPath,fileName,relativePath]"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Jenkins build details.")
    add_env_arg(parser)
    parser.add_argument(
        "--job-path", required=True, help="Slash-delimited Jenkins job path."
    )
    parser.add_argument(
        "--build-number", required=True, type=int, help="Jenkins build number."
    )
    parser.add_argument(
        "--tree",
        default=DEFAULT_TREE,
        help="Optional Jenkins tree selector for the build response.",
    )
    args = parser.parse_args()

    query = {"tree": args.tree} if args.tree else None
    data = request_json(
        "GET",
        args.env,
        job_api_path(args.job_path, f"{args.build_number}/api/json"),
        query=query,
    )
    print_json(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
