#!/usr/bin/env python3
import argparse

from jenkins_common import add_env_arg, print_json, queue_item_api_path, request_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Jenkins queue item details.")
    add_env_arg(parser)
    parser.add_argument(
        "--queue-id", required=True, type=int, help="Jenkins queue item id."
    )
    args = parser.parse_args()

    data = request_json("GET", args.env, queue_item_api_path(args.queue_id))
    print_json(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
