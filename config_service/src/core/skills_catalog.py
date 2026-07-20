"""
Built-in skills catalog metadata.

This module contains static metadata for all built-in skills available in the agent.
Skills are domain-specific knowledge and methodologies that agents can load on-demand.

Each skill includes:
- id: Unique skill identifier (matches SKILL.md frontmatter name)
- name: Human-readable skill name
- description: What the skill provides
- category: Skill category for organization
- required_integrations: List of integration IDs this skill requires
"""

from typing import Any, Dict, List

# === BEGIN GENERATED CATALOG ===
BUILT_IN_SKILLS_METADATA = [
    {
        "id": "alerting-context",
        "name": "Alerting Context",
        "description": "Pull incident context from alerting platforms (PagerDuty). Use when investigating who's on-call, incident history, alert patterns, or MTTR metrics.",
        "category": "Alerting & On-call",
        "required_integrations": ["pagerduty"],
    },
    {
        "id": "alerting-opsgenie",
        "name": "Opsgenie Alerting",
        "description": "Opsgenie alert management and on-call scheduling. Use for listing alerts, checking on-call, computing MTTA/MTTR, and alert fatigue analysis. Supports team and priority filtering.",
        "category": "Alerting & On-call",
        "required_integrations": ["opsgenie"],
    },
    {
        "id": "analytics-amplitude",
        "name": "Amplitude Analytics",
        "description": "Amplitude product analytics. Use when querying user events, funnels, retention, or product usage data. Provides event segmentation, user activity lookup, and annotation queries.",
        "category": "Other Integrations",
        "required_integrations": ["amplitude"],
    },
    {
        "id": "database-bigquery",
        "name": "BigQuery",
        "description": "Google BigQuery data warehouse queries and schema inspection. Use when running SQL queries, listing datasets/tables, or inspecting table schemas in BigQuery.",
        "category": "Databases",
        "required_integrations": ["bigquery"],
    },
    {
        "id": "database-mysql",
        "name": "MySQL",
        "description": "MySQL/MariaDB database inspection and queries. Use when investigating table schemas, running queries, checking processlist, replication status, InnoDB engine status, or lock contention.",
        "category": "Databases",
        "required_integrations": ["mysql"],
    },
    {
        "id": "database-postgresql",
        "name": "PostgreSQL",
        "description": "PostgreSQL database inspection and queries. Use when investigating table schemas, running queries, checking locks, replication status, or long-running queries.",
        "category": "Databases",
        "required_integrations": ["postgresql"],
    },
    {
        "id": "database-snowflake",
        "name": "Snowflake",
        "description": "Snowflake data warehouse queries and schema inspection. Use when running SQL queries against Snowflake, listing tables, or inspecting schemas.",
        "category": "Databases",
        "required_integrations": ["snowflake"],
    },
    {
        "id": "docs-google",
        "name": "Google Docs",
        "description": "Google Docs and Drive integration. Use for reading documents, searching Drive, creating docs, writing content with markdown formatting, and sharing documents.",
        "category": "Docs & Knowledge",
        "required_integrations": ["google"],
    },
    {
        "id": "docs-notion",
        "name": "Notion Docs",
        "description": "Notion page and database management. Use for searching, creating, and writing to Notion pages. Supports creating pages in databases or under parent pages.",
        "category": "Docs & Knowledge",
        "required_integrations": ["notion"],
    },
    {
        "id": "incident-blameless",
        "name": "Blameless Incidents",
        "description": "Blameless incident management and retrospectives. Use for listing incidents, analyzing MTTR, reviewing post-incident retrospectives with contributing factors, action items, and lessons learned.",
        "category": "Incident Management",
        "required_integrations": ["blameless"],
    },
    {
        "id": "incident-comms",
        "name": "Incident Communications",
        "description": "Slack integration for incident communication. Use when searching for context in incident channels, posting status updates, or finding discussions about issues.",
        "category": "Incident Management",
        "required_integrations": ["slack"],
    },
    {
        "id": "incident-firehydrant",
        "name": "FireHydrant",
        "description": "FireHydrant incident management with service catalog. Use for listing incidents, tracking milestones, analyzing MTTR, and service impact analysis across environments.",
        "category": "Incident Management",
        "required_integrations": ["firehydrant"],
    },
    {
        "id": "incident-incidentio",
        "name": "Incident.io",
        "description": "Incident.io incident management and analytics. Use for listing, searching, and analyzing incidents. Supports MTTR calculations, severity analysis, and alert fatigue detection via alert route analytics.",
        "category": "Incident Management",
        "required_integrations": ["incidentio"],
    },
    {
        "id": "infrastructure",
        "name": "Infrastructure Debugging",
        "description": "Infrastructure debugging for Kubernetes and AWS. Use when investigating pod crashes, deployment issues, resource problems, container failures, or cloud infrastructure issues.",
        "category": "Core Methodology",
        "required_integrations": [],
    },
    {
        "id": "infrastructure-aws",
        "name": "AWS",
        "description": "AWS cloud infrastructure inspection. Use when investigating EC2 instances, ECS tasks/services, Lambda functions, CloudWatch logs/metrics, or AWS resource issues.",
        "category": "Infrastructure & Cloud",
        "required_integrations": ["aws"],
    },
    {
        "id": "infrastructure-azure",
        "name": "Azure",
        "description": "Azure cloud infrastructure inspection. Use when investigating Azure VMs, AKS clusters, Log Analytics (KQL), Monitor metrics/alerts, Cost Management, or NSG rules.",
        "category": "Infrastructure & Cloud",
        "required_integrations": ["azure"],
    },
    {
        "id": "infrastructure-docker",
        "name": "Docker",
        "description": "Docker container debugging and management. Use when investigating container issues, checking logs, resource usage, or Docker Compose services.",
        "category": "Infrastructure & Cloud",
        "required_integrations": ["docker"],
    },
    {
        "id": "infrastructure-gcp",
        "name": "GCP",
        "description": "Google Cloud Platform infrastructure inspection. Use when investigating GCP Compute instances, GKE clusters, Cloud Functions, Cloud SQL, or project metadata.",
        "category": "Infrastructure & Cloud",
        "required_integrations": ["gcp"],
    },
    {
        "id": "infrastructure-kubernetes",
        "name": "Kubernetes",
        "description": "Kubernetes debugging methodology and scripts. Use for pod crashes, CrashLoopBackOff, OOMKilled, deployment issues, resource problems, or container failures.",
        "category": "Infrastructure & Cloud",
        "required_integrations": ["kubernetes"],
    },
    {
        "id": "infrastructure-neo4j",
        "name": "Neo4j",
        "description": "Query the OpenSRE knowledge graph for service topology, dependencies, and blast radius. Use after you identify an affected service or deployment — not on vague initial alerts alone.",
        "category": "Infrastructure & Cloud",
        "required_integrations": ["neo4j"],
    },
    {
        "id": "investigate",
        "name": "Investigation Methodology",
        "description": "Systematic incident investigation methodology. Use when investigating production issues, service degradation, errors, latency spikes, or outages. Provides 5-phase framework for evidence-based root cause analysis.",
        "category": "Core Methodology",
        "required_integrations": [],
    },
    {
        "id": "knowledge-base",
        "name": "Knowledge Base",
        "description": "Search runbooks, documentation, and knowledge base articles from Confluence. Use when looking for incident response procedures, service documentation, post-mortems, or troubleshooting guides.",
        "category": "Docs & Knowledge",
        "required_integrations": ["confluence"],
    },
    {
        "id": "knowledge-raptor",
        "name": "RAPTOR Knowledge",
        "description": "Search the RAPTOR knowledge base for runbooks, past incidents, service dependencies, and accumulated team knowledge. Use BEFORE Confluence when investigating incidents — this contains curated, structured knowledge that the system has learned from past investigations.",
        "category": "Docs & Knowledge",
        "required_integrations": [],
    },
    {
        "id": "memory-search",
        "name": "Memory Search",
        "description": "Search OpenSRE memory for past investigations similar to what you are seeing now. Use after you have concrete evidence (error message, failing component, stack trace)—not on vague initial alerts alone.",
        "category": "Memory",
        "required_integrations": [],
    },
    {
        "id": "metrics-analysis",
        "name": "Metrics Analysis",
        "description": "Prometheus/Grafana metrics analysis and PromQL queries. Use when investigating latency, error rates, resource usage, or any time-series metrics.",
        "category": "Observability",
        "required_integrations": ["prometheus", "grafana"],
    },
    {
        "id": "metrics-victoriametrics",
        "name": "VictoriaMetrics",
        "description": "VictoriaMetrics metrics analysis using MetricsQL. Use when querying time-series metrics stored in VictoriaMetrics. Supports PromQL and MetricsQL extensions.",
        "category": "Observability",
        "required_integrations": ["victoriametrics"],
    },
    {
        "id": "observability",
        "name": "Observability Methodology",
        "description": "Log, metric, and trace analysis methodology. Use when analyzing logs, investigating errors, querying metrics, or correlating signals across observability backends (Coralogix, Datadog, CloudWatch).",
        "category": "Core Methodology",
        "required_integrations": [],
    },
    {
        "id": "observability-coralogix",
        "name": "Coralogix",
        "description": "Coralogix log analysis with DataPrime query language. Use when querying Coralogix logs, metrics, or traces. Provides syntax reference and intelligent investigation scripts.",
        "category": "Observability",
        "required_integrations": ["coralogix"],
    },
    {
        "id": "observability-datadog",
        "name": "Datadog",
        "description": "Datadog log and metrics analysis. Use when querying Datadog logs, metrics, or APM data. Provides scripts and query syntax reference.",
        "category": "Observability",
        "required_integrations": ["datadog"],
    },
    {
        "id": "observability-elasticsearch",
        "name": "Elasticsearch",
        "description": "Elasticsearch/OpenSearch log analysis using Lucene query syntax and Query DSL. Use when investigating issues via ELK stack, OpenSearch, or any Elasticsearch-based logging.",
        "category": "Observability",
        "required_integrations": ["elasticsearch"],
    },
    {
        "id": "observability-grafana",
        "name": "Grafana",
        "description": "Grafana dashboard and metrics analysis. Use when querying dashboards, panels, Prometheus metrics via Grafana, checking datasources, reviewing alerts, or creating dashboards from templates.",
        "category": "Observability",
        "required_integrations": ["grafana"],
    },
    {
        "id": "observability-honeycomb",
        "name": "Honeycomb",
        "description": "Honeycomb observability analysis. Use when querying Honeycomb datasets, traces, or metrics. Provides scripts and query syntax reference for high-cardinality exploration.",
        "category": "Observability",
        "required_integrations": ["honeycomb"],
    },
    {
        "id": "observability-jaeger",
        "name": "Jaeger",
        "description": "Jaeger distributed tracing analysis. Use when investigating request latency, tracing errors across services, finding slow spans, or understanding service dependencies.",
        "category": "Observability",
        "required_integrations": ["jaeger"],
    },
    {
        "id": "observability-loki",
        "name": "Loki",
        "description": "Grafana Loki log analysis using LogQL. Use when querying or aggregating logs stored in Loki.",
        "category": "Observability",
        "required_integrations": ["loki"],
    },
    {
        "id": "observability-newrelic",
        "name": "New Relic",
        "description": "New Relic APM and monitoring. Use when running NRQL queries, checking application performance, error rates, or throughput via New Relic.",
        "category": "Observability",
        "required_integrations": ["newrelic"],
    },
    {
        "id": "observability-sentry",
        "name": "Sentry",
        "description": "Sentry error tracking and performance monitoring. Use when investigating application errors, checking error frequency, managing issue status, or reviewing releases.",
        "category": "Observability",
        "required_integrations": ["sentry"],
    },
    {
        "id": "observability-splunk",
        "name": "Splunk",
        "description": "Splunk log analysis using SPL (Search Processing Language). Use when investigating issues via Splunk logs, saved searches, or alerts.",
        "category": "Observability",
        "required_integrations": ["splunk"],
    },
    {
        "id": "observability-victorialogs",
        "name": "VictoriaLogs",
        "description": "VictoriaLogs log analysis using LogsQL. Use when querying logs stored in VictoriaLogs. Provides statistics-first investigation with server-side aggregation.",
        "category": "Observability",
        "required_integrations": ["victorialogs"],
    },
    {
        "id": "platform-argocd",
        "name": "Platform Argocd",
        "description": "Argo CD application inspection, sync, rollback, restart, and diff via CLI. Prod/stg apps have app-name echo gates for state changes; destructive verbs blocked. Use when investigating GitOps deploy failures, out-of-sync apps, or rollout issues.",
        "category": "Other Integrations",
        "required_integrations": ["argocd"],
    },
    {
        "id": "platform-jenkins",
        "name": "Platform Jenkins",
        "description": "Jenkins job discovery, build triggers, console reads, and chained workflows across named Jenkins controllers. Built-in controllers are legacy and aws. Use when investigating CI/CD failures, triggering deploys, or orchestrating build-then-deploy chains.",
        "category": "Other Integrations",
        "required_integrations": ["jenkins"],
    },
    {
        "id": "platform-kronos",
        "name": "Platform Kronos",
        "description": "Kronos env lifecycle — list/check environments, scale up, shut down, and manage recurring schedules. Use when a user asks if a HIX/CCX env is supposed to be up/down, or wants OpenSRE to start/stop/schedule an env. Do NOT use for pod logs, replicas detail, or Argo sync (use kubernetes and ArgoCD skills).",
        "category": "Other Integrations",
        "required_integrations": ["kronos"],
    },
    {
        "id": "platform-vercel",
        "name": "Vercel",
        "description": "Query Vercel deployments, projects, and build logs. Use when investigating Vercel deployment failures, runtime errors, or build issues.",
        "category": "Other Integrations",
        "required_integrations": ["vercel"],
    },
    {
        "id": "project-clickup",
        "name": "ClickUp",
        "description": "ClickUp project management integration for incident tracking and task management",
        "category": "Ticketing & Project",
        "required_integrations": ["clickup"],
    },
    {
        "id": "project-jira",
        "name": "Jira",
        "description": "Jira issue tracking and incident management. Use when creating, searching, or updating Jira issues. Supports JQL queries for incident ticket analysis and alert fatigue tracking.",
        "category": "Ticketing & Project",
        "required_integrations": ["jira"],
    },
    {
        "id": "project-linear",
        "name": "Linear",
        "description": "Linear issue tracking and project management. Use for creating issues, searching issues, and managing projects. Supports GraphQL queries with team and state filtering.",
        "category": "Ticketing & Project",
        "required_integrations": ["linear"],
    },
    {
        "id": "remediation",
        "name": "Remediation Actions",
        "description": "Safe remediation actions for Kubernetes. Use when proposing or executing pod restarts, deployment scaling, or rollbacks. Always use dry-run first.",
        "category": "Core Methodology",
        "required_integrations": [],
    },
    {
        "id": "runtime-config-flagd",
        "name": "flagd Feature Flags",
        "description": "Feature flag management via flagd (OpenFeature). Use to list, inspect, and toggle feature flags in the OTel Demo environment. Flags control incident injection scenarios (payment failures, CPU spikes, memory leaks, etc.) and can be toggled for remediation.",
        "category": "Other Integrations",
        "required_integrations": ["config-flagd"],
    },
    {
        "id": "streaming-kafka",
        "name": "Kafka",
        "description": "Kafka topic and consumer group management. Use when investigating Kafka topics, consumer lag, broker health, or consumer group status.",
        "category": "Other Integrations",
        "required_integrations": ["kafka"],
    },
    {
        "id": "vcs-bitbucket",
        "name": "Vcs Bitbucket",
        "description": "Bitbucket Data Center and Cloud repos, pull requests, branches, issues, webhooks, and pipelines via bkt CLI. Safe read-before-write workflow. Use when investigating PR failures, repo state, or Bitbucket pipeline issues.",
        "category": "Code & Version Control",
        "required_integrations": ["bitbucket"],
    },
    {
        "id": "vcs-github",
        "name": "Vcs Github",
        "description": "GitHub repos, pull requests, Actions workflows, commits, and issues via gh CLI. Safe read-before-write workflow. Use when investigating PR/CI failures, deployment regressions, or repository state on GitHub.",
        "category": "Code & Version Control",
        "required_integrations": ["github"],
    },
    {
        "id": "vcs-gitlab",
        "name": "GitLab",
        "description": "GitLab project management, CI/CD pipelines, merge requests, and code review. Use when investigating GitLab projects, pipeline failures, merge requests, commits, or issues.",
        "category": "Code & Version Control",
        "required_integrations": ["gitlab"],
    },
    {
        "id": "vcs-sourcegraph",
        "name": "Sourcegraph",
        "description": "Sourcegraph code search across repositories. Use for searching code patterns, finding implementations, and exploring codebases. Supports repo and file filters.",
        "category": "Code & Version Control",
        "required_integrations": ["sourcegraph"],
    },
]
# === END GENERATED CATALOG ===


def get_built_in_skills() -> List[Dict[str, Any]]:
    """
    Get list of all built-in skills.

    Returns:
        List of skill metadata dicts with id, name, description, category, source, required_integrations
    """
    return [
        {
            **skill,
            "source": "built-in",
        }
        for skill in BUILT_IN_SKILLS_METADATA
    ]


def get_skills_by_integration(integration_id: str) -> List[Dict[str, Any]]:
    """
    Get all skills that require a specific integration.

    Args:
        integration_id: The integration ID (e.g., "coralogix", "kubernetes", "pagerduty")

    Returns:
        List of skill metadata dicts that require this integration
    """
    return [
        {**skill, "source": "built-in"}
        for skill in BUILT_IN_SKILLS_METADATA
        if integration_id in skill.get("required_integrations", [])
    ]


def get_skills_catalog() -> Dict[str, Any]:
    """
    Get complete skills catalog.

    Returns:
        Dict with 'skills' list and 'count'
    """
    skills = get_built_in_skills()

    return {
        "skills": skills,
        "count": len(skills),
    }
