#!/usr/bin/env python3
import argparse
from typing import Any, Dict, List, Optional

from jenkins_common import add_env_arg, job_api_path, print_json, request_json

DEFAULT_TREE = "jobs[name,fullName,fullDisplayName,url,color,_class]"


def _job_container_path(parent_path: Optional[str]) -> str:
    if parent_path:
        return job_api_path(parent_path, "api/json")
    return "api/json"


def _fetch_child_jobs(env: str, parent_path: Optional[str]) -> List[Dict[str, Any]]:
    data = request_json(
        "GET", env, _job_container_path(parent_path), query={"tree": DEFAULT_TREE}
    )
    jobs = data.get("jobs") or []
    return jobs if isinstance(jobs, list) else []


def _walk_jobs(
    env: str,
    parent_path: Optional[str],
    depth: int,
    max_depth: int,
    recursive: bool,
    jobs: List[Dict[str, Any]],
) -> None:
    for job in _fetch_child_jobs(env, parent_path):
        path = job.get("fullName") or job.get("name")
        if not path:
            continue

        jobs.append(
            {
                "class": job.get("_class"),
                "color": job.get("color"),
                "depth": depth,
                "displayName": job.get("fullDisplayName") or job.get("name"),
                "name": job.get("name"),
                "path": path,
                "url": job.get("url"),
            }
        )

        if recursive and depth < max_depth:
            _walk_jobs(env, path, depth + 1, max_depth, recursive, jobs)


def main() -> int:
    parser = argparse.ArgumentParser(description="List Jenkins jobs.")
    add_env_arg(parser)
    parser.add_argument(
        "--parent-path",
        help="Optional folder/job path to list under instead of the Jenkins root.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Walk into nested folders or multibranch containers.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=5,
        help="Maximum recursion depth when --recursive is used.",
    )
    parser.add_argument(
        "--name-contains",
        help="Case-insensitive substring filter applied to the job path.",
    )
    args = parser.parse_args()

    jobs: List[Dict[str, Any]] = []
    _walk_jobs(
        args.env, args.parent_path, 1, max(args.max_depth, 1), args.recursive, jobs
    )

    if args.name_contains:
        needle = args.name_contains.lower()
        jobs = [job for job in jobs if needle in str(job.get("path", "")).lower()]

    print_json(
        {
            "environment": args.env,
            "jobs": jobs,
            "parentPath": args.parent_path,
            "recursive": args.recursive,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
