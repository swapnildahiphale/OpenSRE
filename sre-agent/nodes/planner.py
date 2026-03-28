"""Planner node -- LLM-driven hypothesis generation and agent selection."""

import json
import logging
import os

from config import AgentConfig, ModelConfig, PromptConfig, build_llm

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are the Planner agent for an AI SRE system. Your role is to:
1. Analyze the alert and available context (memory, knowledge graph)
2. Generate hypotheses about potential root causes
3. Select which investigation subagents to dispatch

You have access to these investigation subagents:
{available_agents}

Respond with a JSON object:
{{
    "hypotheses": [
        {{
            "hypothesis": "Description of potential root cause",
            "priority": "high|medium|low",
            "agents_to_test": ["agent_name_1", "agent_name_2"]
        }}
    ],
    "selected_agents": ["agent_name_1", "agent_name_2", ...],
    "reasoning": "Brief explanation of your investigation plan"
}}

IMPORTANT: selected_agents must be a subset of the available agents listed above.
Only select agents that are relevant to testing your hypotheses.
"""


def planner(state: dict) -> dict:
    """Generate hypotheses and select subagents for investigation.

    On iteration 0: analyze alert + context to form initial hypotheses.
    On iteration 1+: incorporate feedback from synthesizer to refine plan.
    """
    alert = state.get("alert", {})
    memory_context = state.get("memory_context", {})
    kg_context_data = state.get("kg_context", {})
    team_config_raw = state.get("team_config", {})
    iteration = state.get("iteration", 0)
    messages = state.get("messages", [])

    # Get investigation agent config
    agents_config = team_config_raw.get("agents", {})

    # Find available investigation subagents
    investigation_config = agents_config.get("investigation", {})
    sub_agents = investigation_config.get("sub_agents", {})
    available_agents = [name for name, enabled in sub_agents.items() if enabled]

    # Normalize aliases: "k8s" → "kubernetes" to prevent duplicate subagents
    _AGENT_ALIASES = {"k8s": "kubernetes", "logs": "log_analysis"}
    available_agents = [_AGENT_ALIASES.get(a, a) for a in available_agents]
    # Deduplicate while preserving order
    seen = set()
    available_agents = [
        a for a in available_agents if a not in seen and not seen.add(a)
    ]

    if not available_agents:
        # Fallback: use core investigation agents
        available_agents = ["kubernetes", "metrics", "log_analysis"]

    # Filter out agents that don't have corresponding agent configs with skills
    # (e.g., github/aws may be enabled in config but have no useful tools for K8s investigations)
    agents_with_configs = set(agents_config.keys())
    sub_agents_with_configs = set(
        investigation_config.get("sub_agents_config", {}).keys()
    )
    # Keep agents that have a dedicated config, sub_agents_config, or are core investigation types
    core_agents = {"kubernetes", "metrics", "log_analysis", "log_analysis", "traces"}
    available_agents = [
        a
        for a in available_agents
        if a in agents_with_configs or a in sub_agents_with_configs or a in core_agents
    ]
    if not available_agents:
        available_agents = ["kubernetes", "metrics", "log_analysis", "traces"]

    # Filter out explicitly disabled subagents (comma-separated env var)
    disabled_subagents = os.getenv("DISABLED_SUBAGENTS", "")
    if disabled_subagents:
        disabled_set = {s.strip() for s in disabled_subagents.split(",") if s.strip()}
        available_agents = [a for a in available_agents if a not in disabled_set]
        if not available_agents:
            available_agents = ["kubernetes", "metrics", "log_analysis"]

    # Build planner LLM
    planner_config_raw = agents_config.get("planner", {})
    planner_agent_config = AgentConfig(
        name="planner",
        prompt=_build_prompt_config(planner_config_raw),
        model=_build_model_config(planner_config_raw),
    )

    try:
        llm = build_llm(planner_agent_config)
    except Exception as e:
        logger.error(f"[PLANNER] Failed to build LLM: {e}")
        return {
            "hypotheses": [
                {
                    "hypothesis": "Unable to plan -- LLM unavailable",
                    "priority": "high",
                    "agents_to_test": available_agents,
                }
            ],
            "selected_agents": available_agents,
            "iteration": iteration,
        }

    # Build the prompt
    system_prompt = (
        planner_config_raw.get("prompt", {}).get("system", "") or PLANNER_SYSTEM_PROMPT
    )
    system_prompt = system_prompt.replace(
        "{available_agents}", ", ".join(available_agents)
    )

    user_content = f"## Alert\n```json\n{json.dumps(alert, indent=2)}\n```\n\n"

    if memory_context.get("has_similar_episodes"):
        user_content += (
            f"## Memory Context\n{memory_context.get('enhanced_prompt', '')}\n\n"
        )

    if kg_context_data.get("available"):
        from nodes.subagent_executor import _format_kg_for_agent

        user_content += f"## Service Topology\n{_format_kg_for_agent('planner', kg_context_data)}\n\n"

    if iteration > 0 and messages:
        user_content += f"## Iteration {iteration} -- Previous Feedback\n"
        # Include recent feedback messages
        for msg in messages[-3:]:
            if isinstance(msg, dict):
                user_content += f"\n{msg.get('content', str(msg))}\n"
            else:
                user_content += f"\n{msg}\n"

    user_content += f"\nIteration: {iteration}. Generate hypotheses and select agents to investigate."

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from state import InvestigationPlan

        msgs = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
        run_config = {"run_name": "planner", "metadata": {"agent_id": "planner"}}

        # Primary path: structured output
        try:
            llm_structured = llm.with_structured_output(InvestigationPlan)
            plan_obj = llm_structured.invoke(msgs, config=run_config)
            hypotheses = [h.model_dump() for h in plan_obj.hypotheses]
            selected = [a for a in plan_obj.selected_agents if a in available_agents]
            reasoning = plan_obj.reasoning
            logger.info("[PLANNER] Used structured output successfully")
        except Exception as struct_err:
            # Fallback: unstructured call with manual JSON parsing
            logger.warning(
                f"[PLANNER] Structured output failed ({struct_err}), falling back to JSON parsing"
            )
            response = llm.invoke(msgs, config=run_config)
            response_text = response.content
            try:
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0]
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0]
                plan = json.loads(response_text.strip())
            except json.JSONDecodeError:
                logger.warning(
                    "[PLANNER] Failed to parse JSON response, using fallback"
                )
                plan = {
                    "hypotheses": [
                        {
                            "hypothesis": response.content[:200],
                            "priority": "high",
                            "agents_to_test": available_agents,
                        }
                    ],
                    "selected_agents": available_agents,
                    "reasoning": "Fallback plan",
                }
            hypotheses = plan.get("hypotheses", [])
            selected = plan.get("selected_agents", available_agents)
            reasoning = plan.get("reasoning", "Investigation planned")

        # Normalize aliases and filter to only available agents
        selected = [_AGENT_ALIASES.get(a, a) for a in selected]
        selected = list(dict.fromkeys(a for a in selected if a in available_agents))
        if not selected:
            selected = available_agents

        # On first iteration, always dispatch ALL available agents.
        # Subagents run in parallel (Send fan-out) so there's no cost to starting
        # all of them — each agent has early-exit guidance for when its domain
        # has no relevant signals. This prevents the planner LLM from under-selecting.
        if iteration == 0:
            selected = available_agents

        logger.info(
            f"[PLANNER] Iteration {iteration}: {len(hypotheses)} hypotheses, "
            f"dispatching {len(selected)} agents: {selected}"
        )

        return {
            "hypotheses": hypotheses,
            "selected_agents": selected,
            "iteration": iteration,
            "messages": [
                {"role": "planner", "content": f"Iteration {iteration}: {reasoning}"}
            ],
        }

    except Exception as e:
        logger.error(f"[PLANNER] LLM call failed: {e}")
        return {
            "hypotheses": [
                {
                    "hypothesis": f"Fallback plan due to error: {e}",
                    "priority": "high",
                    "agents_to_test": available_agents,
                }
            ],
            "selected_agents": available_agents,
            "iteration": iteration,
        }


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
