from __future__ import annotations

from agents.base_agent import BaseAgent
from prompts.code_proposal_prompt import CODE_PROPOSAL_SYSTEM, CODE_PROPOSAL_HUMAN_TEMPLATE
from schemas.code_proposal import CodeProposal
from schemas.workflow_state import WorkflowPhase, WorkflowState


class CodeProposalAgent(BaseAgent):
    def run(self, state: WorkflowState) -> dict:
        ticket_context = state.get("ticket_context")
        repo_context = state.get("repo_context")
        implementation_plan = state.get("implementation_plan")
        run_id = state["run_id"]
        ticket_id = state["ticket_id"]

        self.logger.info(
            "agent_node_entered",
            ticket_id=ticket_id,
            run_id=run_id,
            phase=WorkflowPhase.PROPOSING_CODE,
        )

        if not ticket_context or not implementation_plan:
            return {
                "current_phase": WorkflowPhase.FAILED,
                "errors": ["code_proposal: missing required state"],
                "should_stop": True,
            }

        plan_steps_text = "\n".join(
            f"{s.step_number}. {s.title}: {s.description} (files: {', '.join(s.affected_files)})"
            for s in implementation_plan.implementation_steps
        )

        # Build a code snippets summary from repo context
        code_snippets = ""
        if repo_context and repo_context.relevant_files:
            snippets = []
            for f in repo_context.relevant_files[:8]:
                snippet = f"**{f.file_path}**"
                if f.functions_detected:
                    snippet += f" — functions: {', '.join(f.functions_detected[:5])}"
                if f.classes_detected:
                    snippet += f" — classes: {', '.join(f.classes_detected[:3])}"
                snippets.append(snippet)
            code_snippets = "\n".join(snippets)

        human_prompt = CODE_PROPOSAL_HUMAN_TEMPLATE.format(
            ticket_id=ticket_id,
            title=ticket_context.title,
            description=ticket_context.description or "(empty)",
            acceptance_criteria=ticket_context.acceptance_criteria or "(not provided)",
            plan_summary=implementation_plan.summary,
            plan_steps=plan_steps_text,
            code_snippets=code_snippets or "(no code snippets available)",
            code_style_hints=(
                repo_context.code_style_hints if repo_context else "Unknown"
            ) or "Unknown",
        )

        try:
            result, call_id = self.invoke_llm_structured(
                system_prompt=CODE_PROPOSAL_SYSTEM,
                human_prompt=human_prompt,
                output_schema=CodeProposal,
                run_id=run_id,
                ticket_id=ticket_id,
                prompt_template_name="code_proposal_generation",
            )

            if result is None:
                raise ValueError("LLM returned None for CodeProposal")

            result.ticket_id = ticket_id

            self.logger.info(
                "agent_node_completed",
                ticket_id=ticket_id,
                run_id=run_id,
                file_changes=len(result.file_changes),
                confidence=result.confidence_score,
            )

            return {
                "code_proposal": result,
                "current_phase": WorkflowPhase.SUGGESTING_TESTS,
                "llm_call_ids": [call_id],
                "total_llm_calls": state.get("total_llm_calls", 0) + 1,
            }

        except Exception as exc:
            self.logger.error("agent_node_failed", exc=exc, ticket_id=ticket_id, run_id=run_id)
            return {
                "current_phase": WorkflowPhase.FAILED,
                "errors": [f"code_proposal: {exc}"],
                "should_stop": True,
            }


_agent = CodeProposalAgent()


def code_proposal_node(state: WorkflowState) -> dict:
    return _agent.run(state)
