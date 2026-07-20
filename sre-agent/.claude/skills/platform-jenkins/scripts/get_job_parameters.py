#!/usr/bin/env python3
import argparse

from jenkins_common import add_env_arg, job_api_path, print_json, request_json

DEFAULT_TREE = (
    "name,fullName,url,"
    "property[_class,parameterDefinitions[_class,name,description,defaultParameterValue[value],choices[name,value]]]"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List parameter definitions for a Jenkins job."
    )
    add_env_arg(parser)
    parser.add_argument(
        "--job-path", required=True, help="Slash-delimited Jenkins job path."
    )
    args = parser.parse_args()

    data = request_json(
        "GET",
        args.env,
        job_api_path(args.job_path, "api/json"),
        query={"tree": DEFAULT_TREE},
    )
    properties = data.get("property") or []
    definitions = []
    for prop in properties:
        for definition in prop.get("parameterDefinitions") or []:
            definitions.append(definition)

    print_json(
        {
            "environment": args.env,
            "jobPath": args.job_path,
            "parameterDefinitions": definitions,
            "url": data.get("url"),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
