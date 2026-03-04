"""
Critical Understanding Index (CUI) v2 Calculator & Bus Factor Extractor.

CUI v2 Formula:
  Criticality = w_C*C + w_F*F + w_H*H + w_I*I + w_T*T + w_R*R + w_B*B + w_D*D

where:
  C = cyclomatic complexity (normalized 0..1)
  F = fan-in / number of callers (normalized 0..1)
  H = normalized churn score (0..1)
  I = normalized issue-mention frequency (0..1)
  T = test gap indicator (1 if no tests, else 1-coverage)
  R = risk flag (0 or 1) from static scan
  B = bus factor score (1 if critical, 0 if safe)
  D = documentation gap (1 if no docs, 0 if well-documented)

Weights are configurable per persona mode.

Also includes:
- Bus Factor extraction from git data
- Onboarding Graph (DAG) construction
- Onboarding Complexity Score (OCS) computation
- Business Risk Score for Startup/Enterprise modes
"""

import os
import subprocess
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import math


# Default CUI v2 weights (can be overridden by persona)
DEFAULT_WEIGHTS = {
    "complexity": 0.20, "fan_in": 0.15, "churn": 0.15,
    "issue_mentions": 0.15, "test_gap": 0.10, "risk_flag": 0.10,
    "bus_factor": 0.10, "doc_gap": 0.05
}

# Persona-specific CUI weight profiles — single source of truth shared across agents
PERSONA_WEIGHTS = {
    "SOLO_DEV": {
        "complexity": 0.25, "fan_in": 0.15, "churn": 0.15,
        "issue_mentions": 0.10, "test_gap": 0.15, "risk_flag": 0.05,
        "bus_factor": 0.05, "doc_gap": 0.10
    },
    "STARTUP": {
        "complexity": 0.15, "fan_in": 0.15, "churn": 0.15,
        "issue_mentions": 0.10, "test_gap": 0.10, "risk_flag": 0.15,
        "bus_factor": 0.15, "doc_gap": 0.05
    },
    "ENTERPRISE": {
        "complexity": 0.20, "fan_in": 0.15, "churn": 0.15,
        "issue_mentions": 0.15, "test_gap": 0.10, "risk_flag": 0.10,
        "bus_factor": 0.10, "doc_gap": 0.05
    },
    "OSS_MAINTAINER": {
        "complexity": 0.15, "fan_in": 0.10, "churn": 0.10,
        "issue_mentions": 0.15, "test_gap": 0.10, "risk_flag": 0.05,
        "bus_factor": 0.15, "doc_gap": 0.20
    }
}


class BusFactorExtractor:
    """
    Computes bus factor per file from git blame data.
    
    Bus Factor = how many contributors would have to leave before
    a file becomes unmaintainable.
    
    Critical if: top contributor owns >60% of commits AND total authors < 3
    """

    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def compute_bus_factor(self, file_paths: List[str]) -> Dict[str, Dict]:
        """
        Compute bus factor for a list of files.
        
        Returns dict of {file_path: {bus_factor: int, critical: bool, top_author: str, 
                                      top_author_pct: float, total_authors: int}}
        """
        results = {}
        
        for fpath in file_paths:
            full_path = os.path.join(self.repo_path, fpath)
            if not os.path.isfile(full_path):
                continue
            
            try:
                # Use git shortlog to get commit counts per author for this file
                output = subprocess.check_output(
                    ["git", "shortlog", "-s", "-n", "--", fpath],
                    cwd=self.repo_path,
                    stderr=subprocess.DEVNULL,
                    timeout=15
                ).decode("utf-8", errors="ignore")
                
                authors = []
                for line in output.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("\t", 1)
                    if len(parts) == 2:
                        count = int(parts[0].strip())
                        name = parts[1].strip()
                        authors.append({"name": name, "commits": count})
                
                if not authors:
                    results[fpath] = {
                        "bus_factor": 0,
                        "critical": True,
                        "top_author": "unknown",
                        "top_author_pct": 1.0,
                        "total_authors": 0
                    }
                    continue
                
                total_commits = sum(a["commits"] for a in authors)
                top_author = authors[0]
                top_pct = top_author["commits"] / total_commits if total_commits > 0 else 1.0
                
                # Bus factor: number of people who contribute meaningfully
                # "Meaningful" = at least 10% of commits
                meaningful_authors = sum(
                    1 for a in authors 
                    if a["commits"] / total_commits >= 0.10
                )
                
                is_critical = (top_pct > 0.60 and len(authors) < 3)
                
                results[fpath] = {
                    "bus_factor": meaningful_authors,
                    "critical": is_critical,
                    "top_author": top_author["name"],
                    "top_author_pct": round(top_pct, 2),
                    "total_authors": len(authors),
                    "authors": authors[:5]  # Top 5 for the report
                }
                
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
                results[fpath] = {
                    "bus_factor": 0,
                    "critical": True,
                    "top_author": "unknown",
                    "top_author_pct": 1.0,
                    "total_authors": 0
                }
        
        return results


class CUICalculator:
    """
    Computes the Critical Understanding Index (CUI) v2 for each file.
    
    Input data comes from Scout (AST, git history, issues) and is combined
    using the weighted formula with persona-specific weights.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or DEFAULT_WEIGHTS

    def compute(self, components: Dict[str, float]) -> Dict:
        """Compute an aggregate codebase-level understandability score (0–100).

        Used by AnalystAgent._compute_cui() which passes pre-computed
        component scores (0–1, higher = better/easier to understand).

        Components expected:
            complexity       – inverse cyclomatic complexity (1=simple, 0=complex)
            file_count       – inverse file count normalised  (1=few, 0=many)
            history          – recent-activity score          (1=active, 0=stale)
            import_complexity– inverse fan-in               (1=low, 0=high)
            test_coverage    – test presence signal          (1=tested, 0=none)
            risk_score       – inverse risk density          (1=safe, 0=risky)
            bus_factor       – inverse bus-factor criticality(1=safe, 0=critical)
            documentation    – doc coverage                  (1=documented, 0=none)
        """
        w = self.weights
        # Map analyst component keys → CUI weight keys (same "goodness" direction)
        mapping = {
            "complexity":        w.get("complexity",    0.20),
            "file_count":        0.05,           # no direct CUI weight; small fixed weight
            "history":           w.get("churn",        0.15),
            "import_complexity": w.get("fan_in",       0.15),
            "test_coverage":     w.get("test_gap",     0.10),
            "risk_score":        w.get("risk_flag",    0.10),
            "bus_factor":        w.get("bus_factor",   0.10),
            "documentation":     w.get("doc_gap",      0.05),
        }
        total_weight = sum(mapping.values())
        weighted_sum = sum(components.get(k, 0.5) * v for k, v in mapping.items())
        normalised = weighted_sum / total_weight if total_weight > 0 else 0.5
        cui_score = round(normalised * 100, 1)

        if cui_score >= 75:
            label = "Easy to Understand"
        elif cui_score >= 55:
            label = "Moderate Complexity"
        elif cui_score >= 35:
            label = "Complex Codebase"
        else:
            label = "Highly Complex"

        return {
            "cui_score": cui_score,
            "understanding_label": label,
            "components": components,
            "normalised_score": round(normalised, 4),
        }

    def compute_cui(
        self,
        structure_data: Dict,
        history_data: Dict,
        community_data: Dict,
        risk_data: Dict,
        bus_factor_data: Dict,
    ) -> List[Dict]:
        """
        Compute CUI for all files and return a ranked list.
        
        Args:
            structure_data: From AST parser (functions, complexity, doc coverage, fan-in)
            history_data: churn scores, last_modified per file
            community_data: issue mentions per file, labels
            risk_data: risk flags per file from static scan
            bus_factor_data: bus factor per file
            
        Returns:
            Sorted list of {file, cui_score, components, rank}
        """
        # Collect all known files
        all_files = set()
        for f in structure_data.get("files", []):
            all_files.add(f["path"])
        for f in history_data.get("churn_score", {}):
            all_files.add(f)
        
        if not all_files:
            return []
        
        # Compute raw values for each file
        raw_scores = []
        for fpath in all_files:
            components = self._compute_components(
                fpath, structure_data, history_data, 
                community_data, risk_data, bus_factor_data
            )
            
            # Weighted sum
            cui = (
                self.weights["complexity"] * components["C"] +
                self.weights["fan_in"] * components["F"] +
                self.weights["churn"] * components["H"] +
                self.weights["issue_mentions"] * components["I"] +
                self.weights["test_gap"] * components["T"] +
                self.weights["risk_flag"] * components["R"] +
                self.weights["bus_factor"] * components["B"] +
                self.weights["doc_gap"] * components["D"]
            )
            
            raw_scores.append({
                "file": fpath,
                "cui_score": round(cui, 4),
                "components": components
            })
        
        # Sort by CUI descending
        raw_scores.sort(key=lambda x: x["cui_score"], reverse=True)
        
        # Add ranks
        for i, entry in enumerate(raw_scores):
            entry["rank"] = i + 1
        
        return raw_scores

    def _compute_components(
        self, fpath: str,
        structure: Dict, history: Dict,
        community: Dict, risk: Dict, bus_factor: Dict
    ) -> Dict[str, float]:
        """Compute normalized 0..1 components for a single file."""
        
        # C: Cyclomatic complexity (normalized)
        file_functions = [
            f for f in structure.get("functions", []) 
            if f.get("file") == fpath
        ]
        if file_functions:
            max_complexity = max(f.get("cyclomatic_complexity", 1) for f in file_functions)
            avg_complexity = sum(f.get("cyclomatic_complexity", 1) for f in file_functions) / len(file_functions)
            C = min(avg_complexity / 20.0, 1.0)  # Normalize: 20+ = max
        else:
            C = 0.0
        
        # F: Fan-in (normalized)
        fan_in_map = structure.get("fan_in", {})
        fan_in_val = fan_in_map.get(fpath, 0)
        max_fan_in = max(fan_in_map.values()) if fan_in_map else 1
        F = fan_in_val / max_fan_in if max_fan_in > 0 else 0.0
        
        # H: Churn score (already normalized 0..1 if provided)
        H = history.get("churn_score", {}).get(fpath, 0.0)
        
        # I: Issue-mention frequency (normalized)
        issue_count = community.get("issue_mentions", {}).get(fpath, 0)
        max_issues = max(community.get("issue_mentions", {}).values()) if community.get("issue_mentions") else 1
        I = issue_count / max_issues if max_issues > 0 else 0.0
        
        # T: Test gap (1 = no tests, 0 = full coverage)
        test_coverage = structure.get("test_coverage", {}).get(fpath, None)
        if test_coverage is not None:
            T = 1.0 - test_coverage
        else:
            # Check if a test file exists for this file
            has_test = self._has_test_file(fpath, structure.get("files", []))
            T = 0.5 if has_test else 1.0
        
        # R: Risk flag from static scan
        risk_flags = risk.get(fpath, [])
        R = 1.0 if risk_flags else 0.0
        
        # B: Bus factor (1 = critical, 0 = safe)
        bf = bus_factor.get(fpath, {})
        B = 1.0 if bf.get("critical", False) else (0.5 if bf.get("bus_factor", 0) <= 1 else 0.0)
        
        # D: Documentation gap
        file_info = next((f for f in structure.get("files", []) if f.get("path") == fpath), {})
        doc_coverage = file_info.get("doc_coverage", 0.0)
        has_module_doc = file_info.get("has_module_docstring", False)
        D = 1.0 - ((doc_coverage * 0.7) + (0.3 if has_module_doc else 0.0))
        
        return {
            "C": round(C, 3), "F": round(F, 3), "H": round(H, 3),
            "I": round(I, 3), "T": round(T, 3), "R": round(R, 3),
            "B": round(B, 3), "D": round(D, 3)
        }

    def _has_test_file(self, fpath: str, files: List[Dict]) -> bool:
        """Check if a test file exists for the given source file."""
        base_name = os.path.splitext(os.path.basename(fpath))[0]
        test_patterns = [
            f"test_{base_name}", f"{base_name}_test",
            f"test_{base_name}.py", f"{base_name}_test.py",
            f"{base_name}.test.js", f"{base_name}.test.ts",
            f"{base_name}.spec.js", f"{base_name}.spec.ts",
        ]
        
        file_names = [os.path.basename(f["path"]) for f in files]
        return any(
            pattern in fname or fname.startswith(f"test_{base_name}")
            for pattern in test_patterns
            for fname in file_names
        )


class OnboardingGraphBuilder:
    """
    Builds a Directed Acyclic Graph (DAG) for onboarding order.
    
    Edges represent "you should understand X before Y":
    - Import edges: If A imports B, add edge B → A
    - Temporal edges: If B committed before A consistently, add soft edge
    - Risk promotion: Files with CUI > 0.75 promoted to "Must Understand First"
    """

    def build_graph(
        self,
        cui_scores: List[Dict],
        imports_graph: Dict[str, List[str]],
        entry_points: List[Dict],
        files: List[Dict]
    ) -> Dict:
        """
        Build the onboarding DAG.
        
        Returns:
            Dict with nodes, edges, topological_order, learning_tiers
        """
        # Build adjacency list: edges are "understand B before A"
        edges = []
        adjacency = defaultdict(list)
        in_degree = defaultdict(int)
        
        # Get all file paths
        all_files = {f["path"] for f in files}
        cui_map = {s["file"]: s["cui_score"] for s in cui_scores}
        
        # Import edges: If A imports B, B should be understood first
        for file_a, imports in imports_graph.items():
            for imp in imports:
                # Try to resolve import to file path
                resolved = self._resolve_to_file(imp, all_files)
                if resolved and resolved != file_a:
                    edges.append({"from": resolved, "to": file_a, "type": "import"})
                    adjacency[resolved].append(file_a)
                    in_degree[file_a] += 1
                    if resolved not in in_degree:
                        in_degree[resolved] = in_degree.get(resolved, 0)
        
        # Topological sort (Kahn's algorithm) with cycle detection
        topo_order = self._topological_sort(adjacency, in_degree, all_files)
        
        # Build learning tiers
        tiers = self._build_learning_tiers(
            topo_order, cui_map, entry_points
        )
        
        # Nodes with metadata
        nodes = []
        for fpath in topo_order:
            cui = cui_map.get(fpath, 0.0)
            is_entry = any(ep["file"] == fpath for ep in entry_points)
            tier = "unknown"
            for tier_name, tier_files in tiers.items():
                if fpath in tier_files:
                    tier = tier_name
                    break
            
            nodes.append({
                "file": fpath,
                "cui_score": cui,
                "is_entry_point": is_entry,
                "tier": tier,
                "must_understand_first": cui > 0.75
            })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "topological_order": topo_order,
            "learning_tiers": tiers,
            "has_cycles": len(topo_order) < len(all_files)
        }

    def _resolve_to_file(self, import_name: str, all_files: set) -> Optional[str]:
        """Resolve an import name to a file path."""
        candidates = [
            import_name.replace(".", "/") + ".py",
            import_name.replace(".", "/") + ".js",
            import_name.replace(".", "/") + ".ts",
            import_name.replace(".", "/") + "/index.js",
            import_name.replace(".", "/") + "/index.ts",
            import_name + ".py",
        ]
        
        for candidate in candidates:
            for fpath in all_files:
                if fpath.endswith(candidate) or fpath == candidate:
                    return fpath
        return None

    def _topological_sort(
        self, 
        adjacency: Dict[str, List[str]], 
        in_degree: Dict[str, int],
        all_files: set
    ) -> List[str]:
        """Kahn's algorithm for topological sort with cycle breaking."""
        # Initialize in_degree for all files
        for f in all_files:
            if f not in in_degree:
                in_degree[f] = 0
        
        queue = [f for f in all_files if in_degree[f] == 0]
        queue.sort()  # Deterministic ordering
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in adjacency.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # If there are remaining nodes (cycle), add them anyway
        remaining = [f for f in all_files if f not in result]
        result.extend(sorted(remaining))
        
        return result

    def build(
        self,
        import_graph: Dict[str, List[str]],
        entry_points: List[Dict],
    ) -> Dict:
        """
        Convenience wrapper called by AnalystAgent — takes just the import graph
        and entry points (no pre-computed CUI scores needed).
        Derives a uniform CUI map from import fan-in as a proxy.
        """
        # Build a proxy CUI map from import fan-in (how many files import each file)
        fan_in: Dict[str, int] = {}
        all_files: set = set(import_graph.keys())
        for imports in import_graph.values():
            for imp in imports:
                fan_in[imp] = fan_in.get(imp, 0) + 1
                all_files.add(imp)
        max_fan = max(fan_in.values(), default=1)
        cui_map = {f: round(fan_in.get(f, 0) / max_fan, 2) for f in all_files}

        files_list = [{"path": f} for f in all_files]
        cui_scores = [{"file": f, "cui_score": cui_map[f]} for f in all_files]
        return self.build_graph(cui_scores, import_graph, entry_points, files_list)

    def _build_learning_tiers(
        self,
        topo_order: List[str],
        cui_map: Dict[str, float],
        entry_points: List[Dict]
    ) -> Dict[str, List[str]]:
        """
        Organize files into learning tiers (keys match frontend expectations):
        - day_1:  Entry points + must-understand-first (CUI > 0.75), max 5
        - week_1: Next critical files (CUI > 0.50), max 10
        - week_2: Supporting files, max 20
        """
        entry_point_files = {ep["file"] for ep in entry_points}

        day_1: List[str] = []
        week_1: List[str] = []
        week_2: List[str] = []

        for fpath in topo_order:
            cui = cui_map.get(fpath, 0.0)

            if fpath in entry_point_files or cui > 0.75:
                if len(day_1) < 5:
                    day_1.append(fpath)
                else:
                    week_1.append(fpath)
            elif cui > 0.50:
                if len(week_1) < 10:
                    week_1.append(fpath)
                else:
                    week_2.append(fpath)
            elif cui > 0.25:
                if len(week_2) < 20:
                    week_2.append(fpath)

        return {
            "day_1": day_1,
            "week_1": week_1,
            "week_2": week_2,
        }


class BusinessRiskScorer:
    """
    Translates technical signals into business language.
    Used in STARTUP and ENTERPRISE persona modes.
    """

    RISK_RULES = [
        {
            "name": "Single Point of Failure",
            "condition": lambda c: c["cui"] > 0.85 and c["bus_critical"] and c["T"] > 0.8,
            "level": "CRITICAL",
            "description": "Single point of failure with no safety net"
        },
        {
            "name": "Active Security Instability",
            "condition": lambda c: c["H"] > 0.7 and c["R"] > 0 and c["I"] > 0.5,
            "level": "HIGH",
            "description": "Active instability in security-critical code"
        },
        {
            "name": "Black Box Dependency",
            "condition": lambda c: c["F"] > 0.7 and c["T"] > 0.5 and c["D"] > 0.7,
            "level": "MEDIUM",
            "description": "Core dependency is a black box — onboarding cliff"
        },
        {
            "name": "Abandoned Critical Path",
            "condition": lambda c: c["D"] > 0.7 and c["H"] < 0.1 and c["bus_critical"],
            "level": "MEDIUM",
            "description": "Abandoned critical path — technical debt accumulating"
        },
    ]

    def score_files(
        self, 
        cui_scores: List[Dict], 
        bus_factor_data: Dict
    ) -> List[Dict]:
        """
        Score top CUI files for business risk.
        
        Returns list of {file, risk_level, risk_name, description, cui_score}
        """
        risks = []
        
        for entry in cui_scores[:20]:  # Top 20 files
            fpath = entry["file"]
            components = entry["components"]
            bf = bus_factor_data.get(fpath, {})
            
            context = {
                "cui": entry["cui_score"],
                "bus_critical": bf.get("critical", False),
                **components
            }
            
            for rule in self.RISK_RULES:
                try:
                    if rule["condition"](context):
                        risks.append({
                            "file": fpath,
                            "risk_level": rule["level"],
                            "risk_name": rule["name"],
                            "description": rule["description"],
                            "cui_score": entry["cui_score"],
                            "bus_factor": bf.get("bus_factor", 0),
                            "top_author": bf.get("top_author", "unknown")
                        })
                        break  # Only report highest risk per file
                except (KeyError, TypeError):
                    continue
        
        # Sort by severity
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        risks.sort(key=lambda r: severity_order.get(r["risk_level"], 4))
        
        return risks


def compute_onboarding_complexity_score(cui_scores: List[Dict], file_count: int) -> Dict:
    """
    Compute the Onboarding Complexity Score (OCS) — a single headline number
    representing how hard it is to onboard onto a codebase.
    
    OCS = weighted average of top-N CUI scores * scale factor
    
    Returns:
        Dict with ocs_score (0-100), difficulty_label, contributing_factors
    """
    if not cui_scores:
        return {"ocs_score": 0, "difficulty_label": "Unknown", "contributing_factors": []}
    
    # Use top 10% of files or at least top 10
    n = max(10, int(len(cui_scores) * 0.10))
    top_scores = [s["cui_score"] for s in cui_scores[:n]]
    
    # Weighted average (higher-ranked files matter more)
    weighted_sum = sum(
        score * (n - i) for i, score in enumerate(top_scores)
    )
    max_weight = sum(range(1, n + 1))
    avg_cui = weighted_sum / max_weight if max_weight > 0 else 0
    
    # Scale to 0-100, factoring in repo size
    size_factor = min(math.log10(max(file_count, 1)) / 4.0, 1.0)
    ocs = round(avg_cui * 100 * (0.6 + 0.4 * size_factor), 1)
    ocs = min(max(ocs, 0), 100)
    
    # Label
    if ocs < 25:
        label = "Easy"
    elif ocs < 50:
        label = "Moderate"
    elif ocs < 75:
        label = "Complex"
    else:
        label = "Very Complex"
    
    # Contributing factors
    factors = []
    avg_components = defaultdict(float)
    for s in cui_scores[:n]:
        for k, v in s.get("components", {}).items():
            avg_components[k] += v
    
    component_names = {
        "C": "High complexity", "F": "Tight coupling (high fan-in)",
        "H": "High code churn", "I": "Many issue mentions",
        "T": "Poor test coverage", "R": "Security risk patterns",
        "B": "Knowledge silos (bus factor)", "D": "Documentation gaps"
    }
    
    for k, total in sorted(avg_components.items(), key=lambda x: -x[1]):
        avg_val = total / n
        if avg_val > 0.5:
            factors.append(component_names.get(k, k))
    
    return {
        "ocs_score": ocs,
        "difficulty_label": label,
        "contributing_factors": factors[:5]
    }
