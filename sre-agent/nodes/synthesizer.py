"""Synthesizer node -- combines subagent results, decides loop or conclude."""

import json
import logging

from config import AgentConfig, ModelConfig, build_llm
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

SYNTHESIZER_SYSTEM_PROMPT = """You are the Synthesizer agent for an AI SRE system.
Your role is to combine findings from multiple investigation subagents and decide:
1. Is there enough evidence to write a conclusion?
2. Or should we investigate further?

Review the findings below and respond with a JSON object:
{{
    "sufficient_evidence": true/false,
    "confidence": 0.0-1.0,
    "summary": "Brief summary of combined findings",
    "gaps": ["List of information gaps if evidence is insufficient"],
    "feedback": "If insufficient, provide specific guidance for the next investigation round"
}}
"""


def synthesizer(state: dict) -> dict:
    """Combine subagent results and decide whether to loop or conclude.

    If evidence is sufficient or max iterations reached: set status to 'completed'.
    Otherwise: append feedback to messages and increment iteration for planner.
    """
    agent_states = state.get("agent_states", {})
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)
    team_config_raw = state.get("team_config", {})
    alert = state.get("alert", {})

    # Build LLM for synthesis
    agents_config = team_config_raw.get("agents", {})
    writeup_config = agents_config.get("writeup", agents_config.get("planner", {}))

    agent_config = AgentConfig(
        name="synthesizer",
        model=_build_model_config(writeup_config),
    )

    # Build findings summary
    findings_text = f"## Alert\n{json.dumps(alert, indent=2)}\n\n"
    findings_text += f"## Investigation Results (Iteration {iteration})\n\n"

    for agent_id, agent_state in agent_states.items():
        findings_text += f"### {agent_id}\n"
        if isinstance(agent_state, dict):
            findings_text += f"- **Status**: {agent_state.get('status', 'unknown')}\n"
            findings_text += f"- **React loops**: {agent_state.get('react_loops', 0)}\n"
            findings_text += (
                f"- **Duration**: {agent_state.get('duration_seconds', 0):.1f}s\n"
            )
            findings_text += (
                f"- **Findings**:\n{agent_state.get('findings', 'No findings')}\n\n"
            )
        else:
            logger.warning(
                f"[SYNTHESIZER] agent_states[{agent_id}] is "
                f"{type(agent_state).__name__}, expected dict"
            )
            findings_text += f"- **Findings**:\n{agent_state}\n\n"

    try:
        from state import SynthesisDecision

        llm = build_llm(agent_config)
        msgs = [
            SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
            HumanMessage(content=findings_text),
        ]
        run_config = {
            "run_name": "synthesizer",
            "metadata": {"agent_id": "synthesizer"},
        }

        # Primary path: structured output
        try:
            llm_structured = llm.with_structured_output(SynthesisDecision)
            decision = llm_structured.invoke(msgs, config=run_config)
            synthesis = decision.model_dump()
            logger.info("[SYNTHESIZER] Used structured output successfully")
        except Exception as struct_err:
            # Fallback: unstructured call with manual JSON parsing
            logger.warning(
                f"[SYNTHESIZER] Structured output failed ({struct_err}), falling back to JSON parsing"
            )
            response = llm.invoke(msgs, config=run_config)
            response_text = response.content
            try:
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0]
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0]
                synthesis = json.loads(response_text.strip())
            except json.JSONDecodeError:
                synthesis = {
                    "sufficient_evidence": iteration >= max_iterations - 1,
                    "confidence": 0.5,
                    "summary": response.content[:500],
                    "gaps": [],
                    "feedback": "",
                }

        sufficient = synthesis.get("sufficient_evidence", False)

        # Force conclusion at max iterations
        if iteration >= max_iterations - 1:
            sufficient = True
            logger.info(
                f"[SYNTHESIZER] Max iterations ({max_iterations}) reached, forcing conclusion"
            )

        if sufficient:
            logger.info(f"[SYNTHESIZER] Evidence sufficient at iteration {iteration}")
            return {
                "status": "completed",
                "messages": [
                    {
                        "role": "synthesizer",
                        "content": synthesis.get("summary", "Investigation complete."),
                    }
                ],
            }
        else:
            feedback = synthesis.get(
                "feedback", "Continue investigation with more detail."
            )
            gaps = synthesis.get("gaps", [])

            feedback_msg = f"## Synthesizer Feedback (Iteration {iteration})\n"
            feedback_msg += f"**Summary**: {synthesis.get('summary', '')}\n"
            feedback_msg += f"**Confidence**: {synthesis.get('confidence', 0)}\n"
            if gaps:
                feedback_msg += f"**Gaps**: {', '.join(gaps)}\n"
            feedback_msg += f"**Guidance**: {feedback}\n"

            logger.info(
                f"[SYNTHESIZER] Insufficient evidence, requesting iteration {iteration + 1}"
            )

            return {
                "iteration": iteration + 1,
                "status": "running",
                "messages": [{"role": "synthesizer", "content": feedback_msg}],
            }

    except Exception as e:
        logger.error(f"[SYNTHESIZER] LLM call failed: {e}")
        # On error, conclude with available evidence
        return {
            "status": "completed",
            "messages": [
                {
                    "role": "synthesizer",
                    "content": f"Synthesis error: {e}. Proceeding with available evidence.",
                }
            ],
        }


def _build_model_config(raw: dict) -> ModelConfig:
    model_data = raw.get("model", {})
    return ModelConfig(
        name=model_data.get("name", "claude-sonnet-4-20250514"),
        temperature=model_data.get("temperature"),
        max_tokens=model_data.get("max_tokens"),
        top_p=model_data.get("top_p"),
    )
