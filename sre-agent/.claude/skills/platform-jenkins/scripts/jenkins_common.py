#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
import sys
import time
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

SUPPORTED_ENVS = ("legacy", "aws")
REDIRECT_STATUS_CODES = (301, 302, 303, 307, 308)
DEFAULT_QUEUE_TIMEOUT_SECONDS = 1800.0
DEFAULT_BUILD_TIMEOUT_SECONDS = 14400.0
DEFAULT_POLL_INTERVAL_SECONDS = 10.0
DEFAULT_WAIT_BUILD_TREE = (
    "number,displayName,fullDisplayName,result,building,duration,estimatedDuration,"
    "timestamp,url,description,builtOn"
)
DEFAULT_BASE_URLS: dict[str, str] = {}


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def add_env_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--env",
        required=True,
        choices=SUPPORTED_ENVS,
        help="Target Jenkins environment.",
    )


def normalize_env(env: str) -> str:
    normalized = env.strip().lower()
    if normalized not in SUPPORTED_ENVS:
        raise RuntimeError(
            f"Unsupported Jenkins environment: {env}. Expected one of {', '.join(SUPPORTED_ENVS)}."
        )
    return normalized


def _env_var_name(env: str, suffix: str) -> str:
    return f"JENKINS_{normalize_env(env).upper()}_{suffix}"


def get_base_url(env: str) -> str:
    env_var = _env_var_name(env, "BASE_URL")
    normalized = normalize_env(env)
    base_url = os.getenv(env_var) or DEFAULT_BASE_URLS.get(normalized)
    if not base_url:
        raise RuntimeError(
            f"Missing {env_var}. Export the Jenkins controller URL for the {normalized} environment."
        )
    return base_url.rstrip("/")


def get_username(env: str) -> str:
    env_var = _env_var_name(env, "USERNAME")
    username = os.getenv(env_var) or os.getenv("JENKINS_USERNAME")
    if not username:
        raise RuntimeError(
            f"Missing {env_var}. Export an environment-specific Jenkins username or JENKINS_USERNAME."
        )
    return username


def get_api_token(env: str) -> str:
    env_var = _env_var_name(env, "API_TOKEN")
    token = os.getenv(env_var) or os.getenv("JENKINS_API_TOKEN")
    if token:
        return token

    raise RuntimeError(
        f"Missing {env_var}. Set it in repo root .env (or export JENKINS_API_TOKEN)."
    )


def get_timeout(env: str) -> float:
    env_var = _env_var_name(env, "HTTP_TIMEOUT")
    raw_value = os.getenv(env_var) or os.getenv("JENKINS_HTTP_TIMEOUT", "20")
    try:
        return float(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid timeout value for {env_var} or JENKINS_HTTP_TIMEOUT: {raw_value}"
        ) from exc


def get_auth_header(env: str) -> str:
    username = get_username(env)
    token = get_api_token(env)
    credentials = f"{username}:{token}".encode("utf-8")
    return "Basic " + base64.b64encode(credentials).decode("ascii")


def build_url(env: str, path: str, query: Optional[Dict[str, Any]] = None) -> str:
    base_url = get_base_url(env)
    trimmed_path = path.lstrip("/")
    url = f"{base_url}/{trimmed_path}" if trimmed_path else base_url
    if query:
        url += "?" + urlencode(query, doseq=True)
    return url


def _parse_response_bytes(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def request(
    method: str,
    env: str,
    path: str,
    *,
    query: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    form: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    accept: str = "application/json",
    use_crumb: bool = False,
    follow_redirects: bool = True,
    send_empty_body: bool = False,
) -> Tuple[int, Dict[str, str], bytes]:
    if payload is not None and form is not None:
        raise RuntimeError("Only one of payload or form may be provided.")

    request_headers = {
        "Authorization": get_auth_header(env),
        "Accept": accept,
        "User-Agent": "opensre-jenkins/1.0",
    }
    if headers:
        request_headers.update(headers)

    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    elif form is not None:
        body = urlencode(form, doseq=True).encode("utf-8")
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif send_empty_body:
        body = b""

    if use_crumb:
        request_headers.update(get_crumb_headers(env))

    req = Request(
        build_url(env, path, query=query),
        data=body,
        headers=request_headers,
        method=method.upper(),
    )
    opener = build_opener() if follow_redirects else build_opener(_NoRedirectHandler())

    try:
        with opener.open(req, timeout=get_timeout(env)) as resp:
            return resp.status, dict(resp.headers.items()), resp.read()
    except HTTPError as err:
        body = err.read() if err.fp else b""
        if not follow_redirects and err.code in REDIRECT_STATUS_CODES:
            return err.code, dict(err.headers.items()), body
        response_text = _parse_response_bytes(body)
        raise RuntimeError(f"HTTP {err.code} {err.reason}: {response_text}") from err
    except URLError as err:
        raise RuntimeError(f"Network error: {err.reason}") from err


def request_json(
    method: str,
    env: str,
    path: str,
    *,
    query: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    form: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    use_crumb: bool = False,
    follow_redirects: bool = True,
    send_empty_body: bool = False,
) -> Any:
    _, _, body = request(
        method,
        env,
        path,
        query=query,
        payload=payload,
        form=form,
        headers=headers,
        accept="application/json",
        use_crumb=use_crumb,
        follow_redirects=follow_redirects,
        send_empty_body=send_empty_body,
    )
    if not body:
        return {}
    response_text = _parse_response_bytes(body)
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as exc:
        snippet = response_text[:500].replace("\n", " ")
        raise RuntimeError(f"Non-JSON response: {snippet}") from exc


def request_text(
    method: str,
    env: str,
    path: str,
    *,
    query: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    follow_redirects: bool = True,
) -> str:
    _, _, body = request(
        method,
        env,
        path,
        query=query,
        headers=headers,
        accept="text/plain, */*",
        follow_redirects=follow_redirects,
    )
    return _parse_response_bytes(body)


def get_crumb_headers(env: str) -> Dict[str, str]:
    try:
        data = request_json("GET", env, "crumbIssuer/api/json")
    except RuntimeError as err:
        message = str(err)
        if "HTTP 404" in message:
            return {}
        raise

    crumb_field = data.get("crumbRequestField")
    crumb_value = data.get("crumb")
    if crumb_field and crumb_value:
        return {crumb_field: crumb_value}
    return {}


def split_job_path(job_path: str) -> list[str]:
    segments = [
        segment.strip() for segment in job_path.strip("/").split("/") if segment.strip()
    ]
    if not segments:
        raise RuntimeError("Job path must contain at least one non-empty segment.")
    return segments


def job_api_path(job_path: str, suffix: str = "api/json") -> str:
    segments = split_job_path(job_path)
    encoded = "/".join(f"job/{quote(segment, safe='')}" for segment in segments)
    cleaned_suffix = suffix.lstrip("/")
    return f"{encoded}/{cleaned_suffix}" if cleaned_suffix else encoded


def queue_item_api_path(queue_id: int) -> str:
    return f"queue/item/{queue_id}/api/json"


def extract_queue_id(location: Optional[str]) -> Optional[int]:
    if not location:
        return None
    match = re.search(r"/queue/item/(\d+)/", location)
    if not match:
        return None
    return int(match.group(1))


def build_api_path(job_path: str, build_number: int, suffix: str = "api/json") -> str:
    return job_api_path(job_path, f"{build_number}/{suffix.lstrip('/')}")


def get_queue_item(env: str, queue_id: int) -> Dict[str, Any]:
    data = request_json("GET", env, queue_item_api_path(queue_id))
    return data if isinstance(data, dict) else {"value": data}


def get_build_info(
    env: str, job_path: str, build_number: int, tree: Optional[str] = None
) -> Dict[str, Any]:
    query = {"tree": tree} if tree else None
    data = request_json("GET", env, build_api_path(job_path, build_number), query=query)
    return data if isinstance(data, dict) else {"value": data}


def trigger_job_build(
    env: str, job_path: str, parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    params = dict(parameters or {})
    endpoint = "buildWithParameters" if params else "build"
    status, headers, _ = request(
        "POST",
        env,
        job_api_path(job_path, endpoint),
        form=params or None,
        use_crumb=True,
        follow_redirects=False,
        send_empty_body=not params,
    )
    queue_url = headers.get("Location")
    return {
        "environment": env,
        "jobPath": job_path,
        "parameters": params,
        "queueId": extract_queue_id(queue_url),
        "queueUrl": queue_url,
        "status": status,
        "writeAction": "trigger-build",
    }


def stop_job_build(env: str, job_path: str, build_number: int) -> Dict[str, Any]:
    status, headers, _ = request(
        "POST",
        env,
        job_api_path(job_path, f"{build_number}/stop"),
        use_crumb=True,
        follow_redirects=False,
        send_empty_body=True,
    )
    return {
        "buildNumber": build_number,
        "environment": env,
        "jobPath": job_path,
        "location": headers.get("Location"),
        "status": status,
        "writeAction": "stop-build",
    }


def wait_for_queue_executable(
    env: str,
    queue_id: int,
    *,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    timeout_seconds: float = DEFAULT_QUEUE_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    started_at = time.monotonic()
    while True:
        queue_item = get_queue_item(env, queue_id)
        executable = queue_item.get("executable") or {}
        build_number = executable.get("number")
        if build_number is not None:
            return {
                "buildNumber": build_number,
                "buildUrl": executable.get("url"),
                "queueItem": queue_item,
                "queueId": queue_id,
            }

        if queue_item.get("cancelled"):
            reason = queue_item.get("why") or "Queue item was cancelled."
            raise RuntimeError(f"Jenkins queue item {queue_id} was cancelled: {reason}")

        if time.monotonic() - started_at > timeout_seconds:
            raise RuntimeError(
                f"Timed out waiting for Jenkins queue item {queue_id} in {env} to start executing "
                f"after {timeout_seconds} seconds."
            )

        time.sleep(max(poll_interval_seconds, 0.1))


def wait_for_build_completion(
    env: str,
    job_path: str,
    build_number: int,
    *,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    timeout_seconds: float = DEFAULT_BUILD_TIMEOUT_SECONDS,
    tree: str = DEFAULT_WAIT_BUILD_TREE,
) -> Dict[str, Any]:
    started_at = time.monotonic()
    while True:
        build_info = get_build_info(env, job_path, build_number, tree=tree)
        if not build_info.get("building", False):
            return build_info

        if time.monotonic() - started_at > timeout_seconds:
            raise RuntimeError(
                f"Timed out waiting for Jenkins build {job_path} #{build_number} in {env} "
                f"after {timeout_seconds} seconds."
            )

        time.sleep(max(poll_interval_seconds, 0.1))


def print_json(data: Any) -> None:
    json.dump(data, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
