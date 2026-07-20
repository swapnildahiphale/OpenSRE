#!/usr/bin/env python3
import argparse

from jenkins_common import add_env_arg, job_api_path, print_json, request_json

DEFAULT_TREE = (
    "name,fullName,fullDisplayName,description,url,buildable,inQueue,color,nextBuildNumber,"
    "healthReport[description,score],"
    "lastBuild[number,url],"
    "lastCompletedBuild[number,result,url],"
    "lastSuccessfulBuild[number,url],"
    "lastFailedBuild[number,url],"
    "builds[number,url,result,building,duration,timestamp]"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Jenkins job details.")
    add_env_arg(parser)
    parser.add_argument(
        "--job-path", required=True, help="Slash-delimited Jenkins job path."
    )
    parser.add_argument(
        "--tree",
        default=DEFAULT_TREE,
        help="Optional Jenkins tree selector for a narrower response.",
    )
    args = parser.parse_args()

    query = {"tree": args.tree} if args.tree else None
    data = request_json(
        "GET", args.env, job_api_path(args.job_path, "api/json"), query=query
    )
    print_json(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
