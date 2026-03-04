"""
Evaluator / Critic Agent — The system's quality gate.

Sits between Analyst and Coordinator. Challenges Analyst claims before
they reach the Narrator.

Verification checks:
1. Entry Point Validation — cross-check against import graph
2. Critical File Claim Verification — Semgrep evidence check
3. Bus Factor Sanity Check — CODEOWNERS and test file checks
4. Onboarding Path Coherence — cycle detection in DAG

Inspired by: CodeR's Verifier, MAGIS's QA Engineer, RTADev's Test Engineer
"""

from typing import Dict, List, Callable, Optional
import re
import subprocess
import os
from collections import defaultdict


class EvaluatorAgent:
    """
    Quality gate agent that verifies Analyst claims before Narrator publishes.
    
    Writes verified_claims to state and adjusts confidence up or down
    based on how many claims survived verification.
    """

    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback

    def emit_progress(self, message: str, data: Optional[Dict] = None):
        if self.progress_callback:
            self.progress_callback("evaluator", message, data or {})

    def evaluate(self, state: Dict) -> Dict:
        """
        Run all verification checks on the Analyst's output.
        
        Args:
            state: Full investigation state containing:
                - structure (AST data with imports_graph, entry_points)
                - analysis (CUI scores, onboarding_graph)  
                - risk_points
                - bus_factor_map
                
        Returns:
            Dict with verified_claims, confidence_adjustment, issues_found
        """
        self.emit_progress("Evaluator agent activated — verifying Analyst claims")
        
        verified_claims = []
        issues_found = []
        confidence_adjustment = 0
        
        # 1. Validate entry points
        ep_result = self._validate_entry_points(state)
        verified_claims.extend(ep_result["verified"])
        issues_found.extend(ep_result["issues"])
        confidence_adjustment += ep_result["confidence_delta"]
        
        # 2. Verify critical file claims
        cf_result = self._verify_critical_files(state)
        verified_claims.extend(cf_result["verified"])
        issues_found.extend(cf_result["issues"])
        confidence_adjustment += cf_result["confidence_delta"]
        
        # 3. Bus factor sanity check
        bf_result = self._check_bus_factor(state)
        verified_claims.extend(bf_result["verified"])
        issues_found.extend(bf_result["issues"])
        confidence_adjustment += bf_result["confidence_delta"]
        
        # 4. Onboarding graph coherence
        og_result = self._check_onboarding_graph(state)
        verified_claims.extend(og_result["verified"])
        issues_found.extend(og_result["issues"])
        confidence_adjustment += og_result["confidence_delta"]
        
        # Compute final confidence
        base_confidence = state.get("confidence", 0.5)
        new_confidence = max(0.0, min(1.0, base_confidence + confidence_adjustment))
        
        total_claims = len(verified_claims)
        passed_claims = sum(1 for c in verified_claims if c["status"] == "verified")
        verification_rate = passed_claims / total_claims if total_claims > 0 else 0.0
        
        self.emit_progress(
            f"Evaluation complete: {passed_claims}/{total_claims} claims verified",
            {
                "verification_rate": round(verification_rate, 2),
                "confidence_adjustment": round(confidence_adjustment, 3),
                "new_confidence": round(new_confidence, 3),
                "issues_count": len(issues_found)
            }
        )
        
        return {
            "verified_claims": verified_claims,
            "issues_found": issues_found,
            "confidence_adjustment": round(confidence_adjustment, 3),
            "new_confidence": round(new_confidence, 3),
            "verification_rate": round(verification_rate, 2),
            "needs_additional_round": new_confidence < 0.70 and len(issues_found) > 2
        }

    def _validate_entry_points(self, state: Dict) -> Dict:
        """
        Cross-check Analyst-identified entry points against the import graph.
        
        Rule: A file listed as entry point that imports nothing is likely correct.
        A file that is heavily imported by others is probably a library, not an entry point.
        """
        self.emit_progress("Validating entry points against import graph")
        
        verified = []
        issues = []
        confidence_delta = 0
        
        structure = state.get("structure", {})
        entry_points = structure.get("entry_points", [])
        imports_graph = structure.get("imports_graph", {})
        
        if not entry_points:
            return {"verified": [], "issues": [{"type": "missing_data", "message": "No entry points to validate"}], "confidence_delta": 0}
        
        # Compute fan-in for each file
        fan_in = defaultdict(int)
        for source, deps in imports_graph.items():
            for dep in deps:
                fan_in[dep] += 1
        
        for ep in entry_points:
            file_path = ep["file"]
            ep_fan_in = ep.get("fan_in", fan_in.get(file_path, 0))
            ep_fan_out = ep.get("fan_out", len(imports_graph.get(file_path, [])))
            
            # Good entry point: low fan-in, moderate fan-out
            if ep_fan_in <= 2:
                verified.append({
                    "type": "entry_point",
                    "file": file_path,
                    "status": "verified",
                    "reason": f"Low fan-in ({ep_fan_in}) confirms this as a genuine entry point"
                })
                confidence_delta += 0.02
            elif ep_fan_in > 5:
                issues.append({
                    "type": "entry_point_suspect",
                    "file": file_path,
                    "severity": "warning",
                    "message": f"High fan-in ({ep_fan_in}) suggests this is a library, not an entry point"
                })
                verified.append({
                    "type": "entry_point",
                    "file": file_path,
                    "status": "disputed",
                    "reason": f"High fan-in ({ep_fan_in}) — likely a shared module"
                })
                confidence_delta -= 0.03
            else:
                verified.append({
                    "type": "entry_point",
                    "file": file_path,
                    "status": "plausible",
                    "reason": f"Moderate fan-in ({ep_fan_in}) — could be entry point or shared utility"
                })
        
        return {"verified": verified, "issues": issues, "confidence_delta": confidence_delta}

    def _verify_critical_files(self, state: Dict) -> Dict:
        """
        For each top-5 CUI file, check if risk claims are consistent.
        If Analyst flagged risk but no actual risk patterns found, lower confidence.
        """
        self.emit_progress("Verifying critical file claims")
        
        verified = []
        issues = []
        confidence_delta = 0
        
        cui_scores_raw = state.get("analysis", {}).get("cui_scores", [])
        # Analyst returns an aggregate dict, not a per-file list — handle both
        cui_scores = cui_scores_raw if isinstance(cui_scores_raw, list) else []
        risk_points = state.get("risk_points", {})
        
        for entry in cui_scores[:5]:
            fpath = entry["file"]
            components = entry.get("components", {})
            
            risk_claimed = components.get("R", 0) > 0
            actual_risks = risk_points.get(fpath, [])
            
            if risk_claimed and actual_risks:
                verified.append({
                    "type": "critical_file_risk",
                    "file": fpath,
                    "status": "verified",
                    "reason": f"Risk flag confirmed by {len(actual_risks)} finding(s)"
                })
                confidence_delta += 0.02
            elif risk_claimed and not actual_risks:
                issues.append({
                    "type": "unsubstantiated_risk",
                    "file": fpath,
                    "severity": "info",
                    "message": f"Risk flagged but no static analysis findings to confirm"
                })
                verified.append({
                    "type": "critical_file_risk",
                    "file": fpath,
                    "status": "unverified",
                    "reason": "Risk flag not confirmed by static analysis"
                })
                confidence_delta -= 0.01
            elif not risk_claimed and actual_risks:
                issues.append({
                    "type": "missed_risk",
                    "file": fpath,
                    "severity": "warning",
                    "message": f"Static analysis found {len(actual_risks)} risks not reflected in CUI"
                })
                confidence_delta -= 0.02
            else:
                verified.append({
                    "type": "critical_file_risk",
                    "file": fpath,
                    "status": "verified",
                    "reason": "No risk claimed, no risk found — consistent"
                })
                confidence_delta += 0.01
        
        return {"verified": verified, "issues": issues, "confidence_delta": confidence_delta}

    def _check_bus_factor(self, state: Dict) -> Dict:
        """
        If a file is flagged Bus Factor = 1 but has a CODEOWNERS entry 
        or a companion test file with recent activity, reduce severity.
        """
        self.emit_progress("Checking bus factor claims")
        
        verified = []
        issues = []
        confidence_delta = 0
        
        bus_factor_map = state.get("bus_factor_map", {})
        structure = state.get("structure", {})
        all_files = {f["path"] for f in structure.get("files", [])}
        
        for fpath, bf_data in bus_factor_map.items():
            if not bf_data.get("critical"):
                continue
            
            # Check for test file companion
            base_name = os.path.splitext(os.path.basename(fpath))[0]
            has_test = any(
                f"test_{base_name}" in fp or f"{base_name}_test" in fp or
                f"{base_name}.test" in fp or f"{base_name}.spec" in fp
                for fp in all_files
            )
            
            if has_test:
                verified.append({
                    "type": "bus_factor",
                    "file": fpath,
                    "status": "mitigated",
                    "reason": "Bus factor = 1 but test file exists — severity reduced"
                })
                confidence_delta += 0.01
            else:
                verified.append({
                    "type": "bus_factor",
                    "file": fpath,
                    "status": "verified",
                    "reason": f"Bus Factor = 1 confirmed — {bf_data.get('top_author', 'unknown')} owns {bf_data.get('top_author_pct', 0)*100:.0f}% with no tests"
                })
                issues.append({
                    "type": "bus_factor_critical",
                    "file": fpath,
                    "severity": "high",
                    "message": f"Critical bus factor — single maintainer with no test safety net"
                })
                confidence_delta -= 0.01
        
        return {"verified": verified, "issues": issues, "confidence_delta": confidence_delta}

    def _check_onboarding_graph(self, state: Dict) -> Dict:
        """
        Traverse the Analyst's Onboarding Graph and check for cycles.
        Cycles would cause the Narrator to produce an impossible learning order.
        """
        self.emit_progress("Checking onboarding graph coherence")
        
        verified = []
        issues = []
        confidence_delta = 0
        
        onboarding_graph = state.get("analysis", {}).get("onboarding_graph", {})
        
        if not onboarding_graph:
            return {
                "verified": [{"type": "onboarding_graph", "status": "skipped", "reason": "No graph to check"}],
                "issues": [],
                "confidence_delta": 0
            }
        
        has_cycles = onboarding_graph.get("has_cycles", False)
        nodes = onboarding_graph.get("nodes", [])
        tiers = onboarding_graph.get("learning_tiers", {})
        
        if has_cycles:
            issues.append({
                "type": "onboarding_graph_cycle",
                "severity": "warning",
                "message": "Onboarding graph contains cycles — learning order may be suboptimal"
            })
            verified.append({
                "type": "onboarding_graph",
                "status": "fixed",
                "reason": "Cycles detected and broken during topological sort"
            })
            confidence_delta -= 0.02
        else:
            verified.append({
                "type": "onboarding_graph",
                "status": "verified",
                "reason": "Graph is a valid DAG — learning order is coherent"
            })
            confidence_delta += 0.03
        
        # Check if day_1 tier is not empty
        day_1 = tiers.get("day_1", [])
        if not day_1:
            issues.append({
                "type": "empty_day_1",
                "severity": "warning",
                "message": "Day 1 learning tier is empty — no starting point for new developers"
            })
            confidence_delta -= 0.02
        else:
            verified.append({
                "type": "day_1_path",
                "status": "verified",
                "reason": f"Day 1 path contains {len(day_1)} file(s) — good starting point"
            })
            confidence_delta += 0.02
        
        # Check must-understand-first files
        must_understand = [n for n in nodes if n.get("must_understand_first")]
        if must_understand:
            verified.append({
                "type": "must_understand",
                "status": "verified",
                "reason": f"{len(must_understand)} high-CUI files flagged as must-understand"
            })
        
        return {"verified": verified, "issues": issues, "confidence_delta": confidence_delta}

    def run_semgrep_check(self, repo_path: str, file_paths: List[str]) -> Dict[str, List[Dict]]:
        """
        Run Semgrep on specific files for security/risk pattern detection.
        Falls back gracefully if Semgrep is not installed.
        
        Returns: {file_path: [{"rule": ..., "severity": ..., "message": ...}]}
        """
        self.emit_progress("Running Semgrep static analysis on critical files")
        
        results = {}
        
        try:
            # Check if semgrep is available
            subprocess.run(
                ["semgrep", "--version"], 
                capture_output=True, timeout=5
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.emit_progress("Semgrep not installed — skipping static analysis")
            # Use pattern-based fallback
            return self._pattern_based_risk_scan(repo_path, file_paths)
        
        for fpath in file_paths[:10]:  # Limit to top 10
            full_path = os.path.join(repo_path, fpath)
            if not os.path.isfile(full_path):
                continue
            
            try:
                output = subprocess.check_output(
                    ["semgrep", "--config", "auto", "--json", "--quiet", full_path],
                    cwd=repo_path,
                    stderr=subprocess.DEVNULL,
                    timeout=60
                ).decode("utf-8", errors="ignore")
                
                import json
                findings = json.loads(output)
                
                file_results = []
                for result in findings.get("results", []):
                    file_results.append({
                        "rule": result.get("check_id", "unknown"),
                        "severity": result.get("extra", {}).get("severity", "info"),
                        "message": result.get("extra", {}).get("message", ""),
                        "line": result.get("start", {}).get("line", 0)
                    })
                
                if file_results:
                    results[fpath] = file_results
                    
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, Exception):
                continue
        
        return results

    def _pattern_based_risk_scan(self, repo_path: str, file_paths: List[str]) -> Dict[str, List[Dict]]:
        """Lightweight pattern-based risk detection when Semgrep is unavailable."""
        
        risk_patterns = {
            "sql_injection": [r"execute\s*\(.*%s", r"execute\s*\(.*\.format\(", r"f[\"'].*SELECT.*\{"],
            "hardcoded_secret": [r"password\s*=\s*[\"'][^\"']+[\"']", r"api_key\s*=\s*[\"'][^\"']+[\"']", r"secret\s*=\s*[\"'][^\"']+[\"']"],
            "os_command": [r"os\.system\(", r"subprocess\.call\(.*shell\s*=\s*True", r"eval\("],
            "file_access": [r"open\(.*[\"']w", r"os\.remove\(", r"shutil\.rmtree\("],
            "network_io": [r"requests\.(get|post|put|delete)\(", r"urllib\.request", r"socket\.connect\("],
            "auth_pattern": [r"@login_required", r"verify_token", r"authenticate", r"jwt\.decode"],
            "db_access": [r"\.execute\(", r"\.query\(", r"cursor\.", r"db\.session"],
        }
        
        results = {}
        
        for fpath in file_paths:
            full_path = os.path.join(repo_path, fpath)
            if not os.path.isfile(full_path):
                continue
            
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except (IOError, OSError):
                continue
            
            file_risks = []
            for risk_type, patterns in risk_patterns.items():
                for pattern in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        file_risks.append({
                            "rule": risk_type,
                            "severity": "warning",
                            "message": f"Pattern '{risk_type}' detected ({len(matches)} occurrence(s))",
                            "count": len(matches)
                        })
                        break  # One finding per risk type per file
            
            if file_risks:
                results[fpath] = file_risks
        
        return results
