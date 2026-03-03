"""
Planner Agent — Generates an explicit JSON task graph before any analysis begins.
Inspired by CodeR's task-graph approach and CrewAI's Flow construct.

Makes the analysis plan visible, auditable, and deterministic.
Agents execute a data structure, not implicit LLM reasoning.
"""

from typing import Dict, List, Callable, Literal, Optional
from app.agents.persona_router import PersonaMode
import json


class PlannerAgent:
    """
    Generates a task graph (JSON) that the Coordinator enforces.
    
    The plan depends on:
    - persona_mode (SOLO_DEV, STARTUP, ENTERPRISE, OSS_MAINTAINER)
    - repo size (file count)
    - available signals (GitHub token, AST support, etc.)
    """

    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback

    def emit_progress(self, message: str, data: Optional[Dict] = None):
        if self.progress_callback:
            self.progress_callback("planner", message, data or {})

    def create_plan(
        self,
        persona_mode: PersonaMode,
        repo_metadata: Dict,
        available_tools: Optional[Dict] = None
    ) -> Dict:
        """
        Create the task graph for this investigation.
        
        Args:
            persona_mode: One of SOLO_DEV, STARTUP, ENTERPRISE, OSS_MAINTAINER
            repo_metadata: Dict with file_count, languages, has_github_token, etc.
            available_tools: Dict of tool availability flags
            
        Returns:
            Task graph JSON with strategy, max_rounds, and ordered steps
        """
        self.emit_progress("Planner activated — building analysis task graph")
        
        file_count = repo_metadata.get("file_count", 0)
        languages = repo_metadata.get("languages", ["python"])
        has_github_token = repo_metadata.get("has_github_token", False)
        
        # Determine strategy
        if file_count > 5000:
            strategy = "shallow_first"
            top_n = 30
            max_rounds = 3
        elif file_count > 500:
            strategy = "standard"
            top_n = 20
            max_rounds = 3
        else:
            strategy = "deep"
            top_n = 50  # Analyze more files for small repos
            max_rounds = 2
        
        self.emit_progress(f"Strategy: {strategy} (repo has ~{file_count} files)")

        # Build step sequence based on persona
        steps = self._build_steps(persona_mode, strategy, top_n, has_github_token, languages)
        
        task_graph = {
            "strategy": strategy,
            "max_rounds": max_rounds,
            "persona_mode": persona_mode,
            "file_count": file_count,
            "top_n": top_n,
            "steps": steps,
            "confidence_threshold": 0.70,
            "abort_conditions": [
                "max_rounds_exceeded",
                "critical_tool_failure"
            ]
        }
        
        self.emit_progress(
            f"Task graph created: {len(steps)} steps, max {max_rounds} rounds",
            {"task_graph_summary": {
                "strategy": strategy,
                "step_count": len(steps),
                "agents_involved": list(set(s["agent"] for s in steps))
            }}
        )
        
        return task_graph

    def _build_steps(
        self,
        persona_mode: PersonaMode,
        strategy: str,
        top_n: int,
        has_github_token: bool,
        languages: List[str]
    ) -> List[Dict]:
        """Build ordered step list based on persona and strategy."""
        
        step_id = 0
        steps = []
        
        def add_step(agent: str, task: str, params: Optional[Dict] = None, condition: Optional[str] = None):
            nonlocal step_id
            step_id += 1
            step = {"id": step_id, "agent": agent, "task": task}
            if params:
                step["params"] = params
            if condition:
                step["condition"] = condition
            steps.append(step)
        
        # ===== Phase 1: Scout data gathering =====
        add_step("scout", "git_structure")
        add_step("scout", "git_history", {"compute_bus_factor": True})
        
        # AST parsing (skip for monorepos on first pass if shallow_first)
        if strategy == "shallow_first":
            add_step("scout", "ast_parse", {"top_n": min(top_n, 20), "shallow": True})
        else:
            add_step("scout", "ast_parse", {"top_n": top_n, "languages": languages})
        
        # GitHub API mining (if token available)
        if has_github_token:
            add_step("scout", "github_issues_prs")
            add_step("scout", "github_community_health")
        
        # Static risk scan
        add_step("scout", "static_risk_scan", {"tool": "semgrep"})
        
        # ===== Phase 2: Analysis =====
        add_step("analyst", "cui_compute", {"top_n": top_n})
        add_step("analyst", "build_onboarding_graph")
        add_step("analyst", "detect_entry_points")
        
        # Persona-specific analysis
        if persona_mode in ("STARTUP", "ENTERPRISE"):
            add_step("analyst", "business_risk_score")
        
        if persona_mode == "OSS_MAINTAINER":
            add_step("analyst", "contributor_friction_analysis")
        
        # ===== Phase 3: Evaluation =====
        add_step("evaluator", "validate_entry_points")
        add_step("evaluator", "verify_critical_claims")
        add_step("evaluator", "check_onboarding_graph_cycles")
        
        if persona_mode in ("STARTUP", "ENTERPRISE"):
            add_step("evaluator", "verify_risk_claims")
        
        # ===== Phase 4: Report generation =====
        add_step("narrator", f"{persona_mode.lower()}_report")
        
        # ===== Optional: Web evidence (triggered by Coordinator if confidence low) =====
        add_step("scout", "web_evidence_search", 
                 condition="confidence < threshold")
        
        return steps

    def adjust_plan(self, task_graph: Dict, feedback: Dict) -> Dict:
        """
        Adjust the plan based on Evaluator feedback or Coordinator decisions.
        Called when the Evaluator finds low-confidence claims.
        """
        self.emit_progress("Planner adjusting task graph based on feedback")
        
        if feedback.get("needs_deeper_scan"):
            # Insert a deep AST pass for specific packages
            packages = feedback.get("target_packages", [])
            new_step = {
                "id": len(task_graph["steps"]) + 1,
                "agent": "scout",
                "task": "ast_parse_deep",
                "params": {"packages": packages, "shallow": False}
            }
            # Insert before evaluator steps
            evaluator_idx = next(
                (i for i, s in enumerate(task_graph["steps"]) if s["agent"] == "evaluator"),
                len(task_graph["steps"])
            )
            task_graph["steps"].insert(evaluator_idx, new_step)
            
        if feedback.get("needs_web_evidence"):
            # Promote web search from conditional to immediate
            for step in task_graph["steps"]:
                if step.get("task") == "web_evidence_search":
                    step.pop("condition", None)
                    
        return task_graph
