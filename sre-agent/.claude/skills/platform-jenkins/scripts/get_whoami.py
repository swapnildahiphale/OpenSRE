#!/usr/bin/env python3
import argparse

from jenkins_common import add_env_arg, print_json, request_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get the current Jenkins identity.")
    add_env_arg(parser)
    args = parser.parse_args()

    data = request_json("GET", args.env, "whoAmI/api/json")
    print_json(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
