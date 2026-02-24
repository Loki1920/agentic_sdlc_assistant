from __future__ import annotations

from agents.base_agent import BaseAgent
from prompts.planner_prompt import PLANNER_HUMAN_TEMPLATE, PLANNER_SYSTEM
from schemas.plan import ImplementationPlan
from schemas.workflow_state import WorkflowPhase, WorkflowState


class PlannerAgent(BaseAgent):
    def run(self, state: WorkflowState) -> dict:
        ticket_context = state.get("ticket_context")
        repo_context = state.get("repo_context")
        run_id = state["run_id"]
        ticket_id = state["ticket_id"]

        self.logger.info(
            "agent_node_entered",
            ticket_id=ticket_id,
            run_id=run_id,
            phase=WorkflowPhase.PLANNING,
        )

        if ticket_context is None or repo_context is None:
            return {
                "current_phase": WorkflowPhase.FAILED,
                "errors": ["planner: missing ticket_context or repo_context"],
                "should_stop": True,
            }

        relevant_files_text = "\n".join(
            f"- {f.file_path} (relevance: {f.relevance_score:.2f}): {f.relevance_reason}"
            for f in repo_context.relevant_files[:15]
        )

        confluence_context = state.get("confluence_context")
        confluence_summary = (
            confluence_context.summary
            if confluence_context and confluence_context.summary
            else "(not available)"
        )
        confluence_pages_text = (
            "\n".join(
                f"- [{p.title}]({p.url}) — {p.relevance_reason}"
                for p in confluence_context.pages_found
            )
            if confluence_context and confluence_context.pages_found
            else "(none retrieved)"
        )

        human_prompt = PLANNER_HUMAN_TEMPLATE.format(
            ticket_id=ticket_id,
            title=ticket_context.title,
            description=ticket_context.description or "(empty)",
            acceptance_criteria=ticket_context.acceptance_criteria or "(not provided)",
            primary_language=repo_context.primary_language or "Unknown",
            impacted_modules=", ".join(repo_context.impacted_modules) or "(unknown)",
            relevant_files=relevant_files_text or "(none identified)",
            code_style_hints=repo_context.code_style_hints or "(not detected)",
            dependency_hints="\n".join(f"- {d}" for d in repo_context.dependency_hints[:10]),
            existing_tests=(
                "\n".join(f"- {t}" for t in repo_context.existing_test_files[:10])
                or "(none found)"
            ),
            confluence_summary=confluence_summary,
            confluence_pages=confluence_pages_text,
        )

        try:
            result, call_id = self.invoke_llm_structured(
                system_prompt=PLANNER_SYSTEM,
                human_prompt=human_prompt,
                output_schema=ImplementationPlan,
                run_id=run_id,
                ticket_id=ticket_id,
                prompt_template_name="implementation_planning",
            )

            if result is None:
                raise ValueError("LLM returned None for ImplementationPlan")

            result.ticket_id = ticket_id

            self.logger.info(
                "agent_node_completed",
                ticket_id=ticket_id,
                run_id=run_id,
                steps=len(result.implementation_steps),
                risk_level=result.risk_level,
                confidence=result.confidence_score,
            )

            return {
                "implementation_plan": result,
                "current_phase": WorkflowPhase.PROPOSING_CODE,
                "llm_call_ids": [call_id],
                "total_llm_calls": state.get("total_llm_calls", 0) + 1,
            }

        except Exception as exc:
            self.logger.error("agent_node_failed", exc=exc, ticket_id=ticket_id, run_id=run_id)
            return {
                "current_phase": WorkflowPhase.FAILED,
                "errors": [f"planner: {exc}"],
                "should_stop": True,
            }


_agent = PlannerAgent()


def planner_node(state: WorkflowState) -> dict:
    return _agent.run(state)
