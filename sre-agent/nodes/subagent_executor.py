"""Subagent executor node -- runs a single investigation subagent's ReAct loop."""

import json
import logging
import os
import time

from config import (
    AgentConfig,
    ModelConfig,
    PromptConfig,
    SkillsConfig,
    TeamConfig,
    build_llm,
    get_skills_for_agent,
)
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from tools.agent_tools import get_skill_catalog, resolve_tools

logger = logging.getLogger(__name__)


def _format_kg_for_agent(agent_id: str, kg_data: dict) -> str:
    """Format KG context for a specific agent type.

    Returns compact markdown tailored to the agent's investigation domain.
    """
    if not kg_data.get("available"):
        return "No service topology available."

    svc_info = kg_data.get("service_info", {})
    if not svc_info:
        return "No service topology available."

    deploy = svc_info.get("deployment", {})
    upstream = svc_info.get("upstream_dependents", [])
    downstream = svc_info.get("downstream_dependencies", [])
    blast = svc_info.get("blast_radius", {})

    svc_name = svc_info.get("resolved_name", kg_data.get("service_name", "unknown"))
    lines = [f"Service: {svc_name}"]

    if deploy:
        lines.append(
            f"Namespace: {deploy.get('namespace', '?')}, Replicas: {deploy.get('replicas', '?')}"
        )

    agent_lower = agent_id.lower()

    if agent_lower in ("k8s", "kubernetes", "planner"):
        # Full deployment details for K8s agent and planner
        if deploy:
            lines.append(
                f"Image: {deploy.get('image', '?')}, Language: {deploy.get('language', '?')}, Port: {deploy.get('port', '?')}"
            )
        if upstream:
            lines.append("Upstream (services that CALL this service):")
            for u in upstream[:8]:
                lines.append(f"  - {u['service']} (via {u.get('via', '?')})")
        if downstream:
            lines.append("Downstream (services this service CALLS):")
            for d in downstream[:8]:
                lines.append(f"  - {d['service']} (via {d.get('via', '?')})")
        if blast.get("upstream_count", 0) > 0:
            lines.append(
                f"Blast radius: {blast['upstream_count']} upstream services affected if this fails"
            )
        lines.append(
            "Use this topology to prioritize dependency checks — verify downstream health before escalating."
        )

    elif agent_lower in ("metrics", "observability"):
        # Metrics agent: service names for PromQL correlation
        all_related = [u["service"] for u in upstream] + [
            d["service"] for d in downstream
        ]
        if all_related:
            lines.append(
                f"Related services for metric correlation: {', '.join(all_related[:10])}"
            )
        lines.append(
            "Query metrics for these related services to check for correlated error/latency spikes."
        )

    elif agent_lower in ("log_analysis", "logs"):
        # Log agent: service names for log grep patterns
        all_names = [u["service"] for u in upstream] + [
            d["service"] for d in downstream
        ]
        if all_names:
            lines.append(
                f"Related service names (search in logs): {', '.join(all_names[:10])}"
            )
        lines.append(
            "These service names may appear in error messages or connection logs."
        )

    else:
        # Default: compact summary
        if upstream:
            lines.append(f"Upstream: {', '.join(u['service'] for u in upstream[:5])}")
        if downstream:
            lines.append(
                f"Downstream: {', '.join(d['service'] for d in downstream[:5])}"
            )

    return "\n".join(lines)


def _format_env_for_agent(agent_id: str, manifest: dict) -> str:
    """Format environment manifest for a specific agent type.

    Returns compact markdown with domain-specific environment details.
    If no manifest or no relevant section, returns empty string.
    """
    if not manifest:
        return ""

    agent_lower = agent_id.lower()
    lines = []

    if agent_lower in ("metrics", "observability"):
        m = manifest.get("metrics", {})
        if not m:
            return ""
        lines.append(f"Backend: {m.get('backend', 'unknown')}")
        if m.get("naming_convention"):
            lines.append(f"Naming convention: {m['naming_convention']}")
        km = m.get("key_metrics", {})
        if km:
            lines.append("\nKEY METRICS (use these EXACT names, not generic ones):")
            for purpose, metric in km.items():
                lines.append(f"  {purpose}: {metric}")
        lc = m.get("label_conventions", {})
        if lc:
            lines.append("\nLABEL CONVENTIONS:")
            for purpose, label in lc.items():
                lines.append(f"  {purpose}: {label}")
        if m.get("service_name_format"):
            lines.append(f"\nService name format: {m['service_name_format']}")
        if m.get("notes"):
            lines.append(f"\nIMPORTANT: {m['notes']}")

    elif agent_lower in ("log_analysis", "logs"):
        lg = manifest.get("logs", {})
        if not lg:
            return ""
        lines.append(f"Backend: {lg.get('backend', 'unknown')}")
        lines.append(f"Index: {lg.get('index_pattern', 'unknown')}")
        fm = lg.get("field_mapping", {})
        if fm:
            lines.append("\nFIELD MAPPING (use these EXACT field names):")
            for purpose, field in fm.items():
                lines.append(f"  {purpose}: {field}")
        if lg.get("notes"):
            lines.append(f"\nIMPORTANT: {lg['notes']}")

    elif agent_lower in ("traces",):
        tr = manifest.get("traces", {})
        if not tr:
            return ""
        lines.append(f"Backend: {tr.get('backend', 'unknown')}")
        if tr.get("service_name_format"):
            lines.append(f"Service name format: {tr['service_name_format']}")
        if tr.get("notes"):
            lines.append(f"\nIMPORTANT: {tr['notes']}")

    elif agent_lower in ("kubernetes", "k8s"):
        k = manifest.get("kubernetes", {})
        if not k:
            return ""
        if k.get("namespace"):
            lines.append(f"Namespace: {k['namespace']}")
        if k.get("notes"):
            lines.append(f"\nIMPORTANT: {k['notes']}")

    if not lines:
        return ""

    return "\n".join(lines)


SUBAGENT_SYSTEM_TEMPLATE = """You are the {agent_name} investigation agent for an AI SRE system.
Your role is to INVESTIGATE a production incident — gather evidence from your domain and report findings.

{custom_prompt}

## Investigation Context
Alert: {alert_summary}

## Service Topology (from Knowledge Graph)
{service_topology}

## Your Environment
{environment_context}

## Hypotheses to Test
{hypotheses}

## Available Skills
{skill_catalog}

## How to Work
1. Use `load_skill(name)` to load a skill's documentation and learn its methods
2. Use `run_script(command)` to execute the skill's scripts for data gathering
3. Investigate systematically — test each hypothesis with evidence from your domain
4. When done, provide a clear summary of your findings and confidence level

## Rules
- NEVER modify production resources — investigation is read-only
- Do NOT call the same tool with the same arguments twice
- Do NOT fabricate data — if a query returns nothing, report "no data found"
- If your domain has no relevant signals for this alert, say so and stop
  — do not waste cycles searching when there is nothing to find
- Do NOT suggest remediation actions — your job is investigation only
- Report WHAT you found (or didn't find), with evidence
"""


def make_subagent_executor():
    """Create the subagent executor function for use with Send() fan-out."""

    def subagent_executor(state: dict) -> dict:
        """Execute a single investigation subagent's ReAct loop.

        Receives Send() payload with agent_id and context.
        Returns agent_states update with findings.
        """
        agent_id = state.get("agent_id", "unknown")
        alert = state.get("alert", {})
        hypotheses = state.get("hypotheses", [])
        team_config_raw = state.get("team_config", {})
        max_react_loops = state.get(
            "max_react_loops", int(os.getenv("SUBAGENT_MAX_REACT_LOOPS", "25"))
        )

        logger.info(
            f"[SUBAGENT:{agent_id}] Starting investigation (max {max_react_loops} loops)"
        )
        start_time = time.time()

        # Get agent config
        agents_config = team_config_raw.get("agents", {})
        investigation_config = agents_config.get("investigation", {})
        sub_agents_config = investigation_config.get("sub_agents_config", {})
        agent_raw_config = sub_agents_config.get(
            agent_id, agents_config.get(agent_id, {})
        )

        # Build agent config
        agent_config = AgentConfig(
            name=agent_id,
            prompt=_build_prompt_config(agent_raw_config),
            model=_build_model_config(agent_raw_config),
        )

        # Get skills for this agent
        team_config_obj = _build_team_config(team_config_raw)
        enabled_skills = get_skills_for_agent(agent_id, team_config_obj)

        # Resolve skills directory
        skills_dir = os.getenv(
            "SKILLS_DIR",
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)), ".claude", "skills"
            ),
        )

        # Build tools and skill catalog
        tools = resolve_tools(agent_id, enabled_skills, skills_dir)
        skill_catalog = get_skill_catalog(enabled_skills, skills_dir)

        # Build LLM with tool binding
        try:
            llm = build_llm(agent_config)
            llm_with_tools = llm.bind_tools(tools)
        except Exception as e:
            logger.error(f"[SUBAGENT:{agent_id}] Failed to build LLM: {e}")
            return {
                "agent_states": {
                    agent_id: {
                        "status": "error",
                        "findings": f"Failed to initialize: {e}",
                        "evidence": [],
                        "confidence": 0.0,
                        "react_loops": 0,
                        "duration_seconds": time.time() - start_time,
                    }
                }
            }

        # Build system prompt
        custom_prompt = agent_raw_config.get("prompt", {}).get("system", "")
        hypotheses_text = (
            "\n".join(
                f"- {h.get('hypothesis', str(h)) if isinstance(h, dict) else str(h)}"
                for h in hypotheses
            )
            if hypotheses
            else "No specific hypotheses -- investigate broadly."
        )

        kg_context_data = state.get("kg_context", {})
        service_topology = _format_kg_for_agent(agent_id, kg_context_data)

        env_manifest = team_config_raw.get("environment_manifest", {})
        environment_context = _format_env_for_agent(agent_id, env_manifest)

        system_prompt = SUBAGENT_SYSTEM_TEMPLATE.format(
            agent_name=agent_id,
            custom_prompt=custom_prompt,
            alert_summary=json.dumps(alert, indent=2),
            service_topology=service_topology,
            environment_context=environment_context
            or "No environment manifest available. Use discovery queries from your skills.",
            hypotheses=hypotheses_text,
            skill_catalog=skill_catalog,
        )

        # Run ReAct loop
        messages_list = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=f"Begin your investigation of the alert. Agent: {agent_id}"
            ),
        ]

        react_timeline = []
        tool_map = {t.name: t for t in tools}
        seen_calls = set()  # Track (tool_name, args_hash) to prevent duplicates
        tool_call_count = 0  # Running count of actual tool executions

        # Pass agent_id in config so astream_events() attributes events correctly
        agent_run_config = {"run_name": agent_id, "metadata": {"agent_id": agent_id}}

        for loop_idx in range(max_react_loops):
            try:
                response = llm_with_tools.invoke(messages_list, config=agent_run_config)
                messages_list.append(response)

                # Check for tool calls
                if response.tool_calls:
                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]

                        # Deduplication check
                        call_key = (
                            f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"
                        )
                        if call_key in seen_calls:
                            messages_list.append(
                                ToolMessage(
                                    content="DUPLICATE: You already called this tool with identical arguments. Use the previous result instead of calling again.",
                                    tool_call_id=tool_call["id"],
                                )
                            )
                            react_timeline.append(
                                {
                                    "loop": loop_idx,
                                    "action": "duplicate_skipped",
                                    "tool": tool_name,
                                }
                            )
                            logger.info(
                                f"[SUBAGENT:{agent_id}] Duplicate tool call skipped: {tool_name}"
                            )
                            continue

                        seen_calls.add(call_key)

                        react_timeline.append(
                            {
                                "loop": loop_idx,
                                "action": "tool_call",
                                "tool": tool_name,
                                "args": {k: str(v)[:200] for k, v in tool_args.items()},
                            }
                        )

                        # Execute tool
                        if tool_name in tool_map:
                            try:
                                tool_result = tool_map[tool_name].invoke(
                                    tool_args, config=agent_run_config
                                )
                            except Exception as e:
                                tool_result = f"Error: {e}"
                        else:
                            tool_result = f"Unknown tool: {tool_name}"

                        # Add tool result as message
                        messages_list.append(
                            ToolMessage(
                                content=str(tool_result)[:10000],
                                tool_call_id=tool_call["id"],
                            )
                        )

                        tool_call_count += 1

                    # Reflection checkpoint every 5 tool executions
                    if tool_call_count > 0 and tool_call_count % 5 == 0:
                        messages_list.append(
                            HumanMessage(
                                content=(
                                    "REFLECTION CHECKPOINT: Before making more tool calls, briefly assess:\n"
                                    "1. What have you learned so far?\n"
                                    "2. Which hypotheses can you confirm or eliminate?\n"
                                    "3. What is the single most valuable next action?\n"
                                    "4. Are you going in circles or making progress?\n"
                                    "State your assessment concisely, then continue investigating."
                                )
                            )
                        )
                        logger.info(
                            f"[SUBAGENT:{agent_id}] Reflection checkpoint at {tool_call_count} tool calls"
                        )
                else:
                    # No tool calls -- agent is done
                    react_timeline.append(
                        {
                            "loop": loop_idx,
                            "action": "final_response",
                        }
                    )
                    break

            except Exception as e:
                logger.error(f"[SUBAGENT:{agent_id}] Loop {loop_idx} error: {e}")
                react_timeline.append(
                    {
                        "loop": loop_idx,
                        "action": "error",
                        "error": str(e),
                    }
                )
                break
        else:
            logger.warning(
                f"[SUBAGENT:{agent_id}] Hit max react loops ({max_react_loops})"
            )

        hit_max_loops = loop_idx >= max_react_loops - 1

        # Extract final findings from last AI message
        findings = ""

        # Tier 1: Look for a clean final response (no tool_calls) — always reliable
        for msg in reversed(messages_list):
            if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                findings = msg.content
                break

        # Tier 2: On max-loop exit, ALWAYS do forced summarization.
        # Tier 2 content from messages with tool_calls is just reasoning text, not findings.
        # Only use Tier 2 (content from tool_call messages) for non-max-loop exits (exceptions).
        if not findings and hit_max_loops:
            try:
                summary_msgs = messages_list + [
                    HumanMessage(
                        content=(
                            "You have reached the maximum number of investigation steps. "
                            "Based on all the evidence gathered above, provide a concise summary of:\n"
                            "1. What you found\n"
                            "2. The likely root cause\n"
                            "3. Your confidence level\n"
                            "Do NOT call any tools. Just summarize your findings."
                        )
                    )
                ]
                summary_response = llm.invoke(summary_msgs, config=agent_run_config)
                if summary_response.content:
                    findings = summary_response.content
                    logger.info(
                        f"[SUBAGENT:{agent_id}] Forced summary generated ({len(findings)} chars)"
                    )
            except Exception as e:
                logger.warning(f"[SUBAGENT:{agent_id}] Forced summary failed: {e}")

        # Tier 3: Fallback — extract content from any AIMessage (even with tool_calls)
        if not findings:
            for msg in reversed(messages_list):
                if isinstance(msg, AIMessage) and msg.content:
                    findings = msg.content
                    break

        if not findings:
            findings = f"Agent {agent_id} completed {len(react_timeline)} actions but did not produce a final summary."

        duration = time.time() - start_time
        logger.info(
            f"[SUBAGENT:{agent_id}] Completed in {duration:.1f}s, "
            f"{len(react_timeline)} actions"
        )

        return {
            "agent_states": {
                agent_id: {
                    "status": "completed",
                    "findings": findings,
                    "evidence": [
                        entry
                        for entry in react_timeline
                        if entry.get("action") == "tool_call"
                    ],
                    "confidence": 0.7,  # Default, will be refined by synthesizer
                    "react_loops": len(react_timeline),
                    "duration_seconds": duration,
                }
            }
        }

    return subagent_executor


def _build_prompt_config(raw: dict) -> PromptConfig:
    prompt_data = raw.get("prompt", {})
    return PromptConfig(
        system=prompt_data.get("system", ""),
        prefix=prompt_data.get("prefix", ""),
        suffix=prompt_data.get("suffix", ""),
    )


def _build_model_config(raw: dict) -> ModelConfig:
    model_data = raw.get("model", {})
    return ModelConfig(
        name=model_data.get("name", "claude-sonnet-4-20250514"),
        temperature=model_data.get("temperature"),
        max_tokens=model_data.get("max_tokens"),
        top_p=model_data.get("top_p"),
    )


def _build_team_config(raw: dict) -> TeamConfig:
    """Build a TeamConfig from raw dict for skill resolution."""
    agents = {}
    for name, cfg in raw.get("agents", {}).items():
        agents[name] = AgentConfig(
            enabled=cfg.get("enabled", True),
            name=name,
            skills={k: bool(v) for k, v in cfg.get("skills", {}).items()},
        )

    skills_data = raw.get("skills", {})
    return TeamConfig(
        agents=agents,
        skills=SkillsConfig(
            enabled=skills_data.get("enabled", ["*"]),
            disabled=skills_data.get("disabled", []),
        ),
        raw_config=raw,
    )
