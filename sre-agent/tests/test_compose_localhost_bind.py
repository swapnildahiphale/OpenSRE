"""Static checks for docker-compose localhost host-port binding."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"

LOCALHOST = "127.0.0.1"


def _load_compose() -> dict:
    with COMPOSE_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _port_strings(service: dict) -> list[str]:
    ports = service.get("ports") or []
    return [str(p) for p in ports]


def test_postgres_and_neo4j_ports_bound_to_localhost():
    compose = _load_compose()
    services = compose["services"]

    postgres_ports = _port_strings(services["postgres"])
    assert any(p.startswith(f"{LOCALHOST}:5433:") for p in postgres_ports), postgres_ports

    neo4j_ports = _port_strings(services["neo4j"])
    assert any(p.startswith(f"{LOCALHOST}:7475:") for p in neo4j_ports), neo4j_ports
    assert any(p.startswith(f"{LOCALHOST}:7688:") for p in neo4j_ports), neo4j_ports


def test_config_service_and_sre_agent_ports_bound_to_localhost():
    compose = _load_compose()
    services = compose["services"]

    config_ports = _port_strings(services["config-service"])
    assert any(p.startswith(f"{LOCALHOST}:8081:") for p in config_ports), config_ports

    agent_ports = _port_strings(services["sre-agent"])
    assert any(p.startswith(f"{LOCALHOST}:8001:") for p in agent_ports), agent_ports

    web_ports = _port_strings(services["web-ui"])
    assert any(p.startswith(f"{LOCALHOST}:3002:") for p in web_ports), web_ports


def test_teams_bot_port_bound_to_localhost():
    compose = _load_compose()
    teams_ports = _port_strings(compose["services"]["teams-bot"])
    assert any(p.startswith(f"{LOCALHOST}:3978:") for p in teams_ports), teams_ports


def test_datastore_services_join_default_network_for_host_ports():
    """Custom-only networks skip host publish on Docker Desktop; join default too."""
    compose = _load_compose()
    for name in ("postgres", "neo4j"):
        nets = compose["services"][name].get("networks") or []
        assert "default" in nets, f"{name} networks={nets}"


def test_impersonation_jwt_secret_is_env_overridable_with_dev_default():
    compose = _load_compose()
    secret = compose["services"]["config-service"]["environment"]["IMPERSONATION_JWT_SECRET"]
    assert secret.startswith("${IMPERSONATION_JWT_SECRET:-")
    assert "local-dev-impersonation-secret-32chars!!" in secret
