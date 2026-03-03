from typing import Dict, Callable, Optional, List
import os
import requests
from app.utils.git_analyzer import GitAnalyzer
from app.utils.web_search import WebSearcher
from app.utils.ast_parser import ASTParser
from app.utils.cui_calculator import BusFactorExtractor
from app.config import settings


class ScoutAgent:
    """Scout Agent v2 - Multi-source intelligence gathering across 4 extraction modules:
    1. Git Intelligence  - commit history, patterns, contributors
    2. AST Structural Analysis - code structure, entry points, dependency graph
    3. Static Risk Scan - security patterns, complexity, tech debt signals
    4. Issue & PR Mining - community health, velocity, open issues
    """

    def __init__(self, progress_callback: Callable = None):
        self.progress_callback = progress_callback
        self._github_headers = self._build_github_headers()

    def _build_github_headers(self) -> Dict:
        headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "NeuralArchaeologist"}
        token = getattr(settings, "GITHUB_TOKEN", None)
        if token:
            headers["Authorization"] = f"token {token}"
        return headers

    def emit_progress(self, message: str, data: Dict = None):
        if self.progress_callback:
            self.progress_callback("scout", message, data or {})

    # ─────────────────────────────────────────────────────────────────────────
    # Module 1: Git Intelligence
    # ─────────────────────────────────────────────────────────────────────────

    def _run_git_intelligence(self, repo_url: str) -> Dict:
        """Gather deep git commit history and patterns."""
        self.emit_progress("Module 1/4 — Git Intelligence")
        analyzer = GitAnalyzer(repo_url)
        git_data = analyzer.analyze()
        self.emit_progress(
            f"  ✓ {git_data['total_commits']} commits • "
            f"{git_data['contributors_count']} contributors • "
            f"{git_data['active_period_months']:.1f} active months"
        )

        patterns = git_data.get("patterns_detected", {})
        if "activity_spike" in patterns:
            spike = patterns["activity_spike"]
            self.emit_progress(f"  ↑ Activity spike: {spike['month']} ({spike['commit_count']} commits)")
        if "sudden_stop" in patterns:
            stop = patterns["sudden_stop"]
            self.emit_progress(
                f"  ⚠ Sudden halt: last activity {stop['last_activity']} "
                f"({stop['months_since']:.0f} months ago)"
            )
        if "gradual_decay" in patterns:
            decay = patterns["gradual_decay"]
            self.emit_progress(f"  ↓ Gradual decay: {decay['decline_percentage']:.0f}% decline")

        # Augment with Bus Factor data if repo is cloned locally
        temp_dir = git_data.get("local_path")
        bus_factor_map: Dict = {}
        if temp_dir and os.path.exists(str(temp_dir)):
            try:
                # Collect source file paths for bus-factor computation
                source_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go"}
                skip_dirs = {"node_modules", ".git", "__pycache__", "venv", "dist", "build"}
                file_paths: List[str] = []
                for root, dirs, files in os.walk(str(temp_dir)):
                    dirs[:] = [d for d in dirs if d not in skip_dirs]
                    for fname in files:
                        if any(fname.endswith(ext) for ext in source_exts):
                            rel = os.path.relpath(os.path.join(root, fname), str(temp_dir))
                            file_paths.append(rel)
                if file_paths:
                    extractor = BusFactorExtractor(str(temp_dir))
                    bus_factor_map = extractor.compute_bus_factor(file_paths[:80])
                    critical_files = sum(
                        1 for v in bus_factor_map.values() if v.get("critical", False)
                    )
                    self.emit_progress(f"  ↳ Bus factor computed: {critical_files} critical-ownership files")
            except Exception as e:
                self.emit_progress(f"  Bus factor extraction skipped: {e}")

        return {**git_data, "bus_factor_map": bus_factor_map}

    # ─────────────────────────────────────────────────────────────────────────
    # Module 2: AST Structural Analysis
    # ─────────────────────────────────────────────────────────────────────────

    def _run_ast_analysis(self, repo_local_path: Optional[str]) -> Dict:
        """Parse code structure, entry points and dependency graph."""
        self.emit_progress("Module 2/4 — AST Structural Analysis")
        if not repo_local_path or not os.path.exists(repo_local_path):
            self.emit_progress("  ✗ Local repo path unavailable — skipping AST")
            return {}

        try:
            parser = ASTParser(repo_local_path)
            ast_result = parser.scan_repository()
            self.emit_progress(
                f"  ✓ {ast_result['total_files']} files analyzed • "
                f"{ast_result['total_functions']} functions • "
                f"{len(ast_result.get('entry_points', []))} entry points"
            )
            self.emit_progress(
                f"  ↳ Languages: {', '.join(ast_result.get('languages_found', []))}"
            )
            lang_stats = ast_result.get("language_stats", {})
            doc_cov = ast_result.get("doc_coverage", {})
            self.emit_progress(
                f"  ↳ Doc coverage: {doc_cov.get('coverage_percentage', 0):.1f}%"
            )
            return ast_result
        except Exception as e:
            self.emit_progress(f"  AST analysis failed: {e}")
            return {}

    # ─────────────────────────────────────────────────────────────────────────
    # Module 3: Static Risk Scan
    # ─────────────────────────────────────────────────────────────────────────

    def _run_static_risk_scan(self, repo_local_path: Optional[str]) -> Dict:
        """Detect security patterns, high complexity hotspots, tech debt signals."""
        self.emit_progress("Module 3/4 — Static Risk Scan")
        if not repo_local_path or not os.path.exists(repo_local_path):
            self.emit_progress("  ✗ Local path unavailable — skipping static scan")
            return {}

        risk_findings: List[Dict] = []
        high_complexity: List[Dict] = []

        RISK_PATTERNS = {
            "sql_injection": (
                r"(execute|cursor\.execute|raw\(|format_sql|%s.*where|f['\"].*select)",
                "HIGH",
            ),
            "hardcoded_secret": (
                r"(password\s*=\s*['\"][^'\"]{4,}|secret\s*=\s*['\"][^'\"]{4,}|api_key\s*=\s*['\"])",
                "CRITICAL",
            ),
            "os_command": (r"(os\.system|subprocess\.call|shell=True|popen)", "HIGH"),
            "eval_exec": (r"\b(eval|exec)\s*\(", "HIGH"),
            "insecure_random": (r"random\.random|random\.randint", "MEDIUM"),
            "debug_flag": (r"DEBUG\s*=\s*True|debug=True", "LOW"),
            "todo_fixme": (r"(TODO|FIXME|HACK|XXX)\s*:", "LOW"),
        }

        import re

        source_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go"}
        skip_dirs = {"node_modules", ".git", "__pycache__", "venv", "dist", "build", ".tox"}

        scanned = 0
        for root, dirs, files in os.walk(repo_local_path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fname in files:
                if not any(fname.endswith(ext) for ext in source_exts):
                    continue
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, repo_local_path)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    scanned += 1
                    for pattern_name, (pattern, severity) in RISK_PATTERNS.items():
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        if matches:
                            risk_findings.append(
                                {
                                    "file": rel_path,
                                    "pattern": pattern_name,
                                    "severity": severity,
                                    "occurrences": len(matches),
                                }
                            )
                except Exception:
                    pass

        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for f in risk_findings:
            severity_counts[f["severity"]] = severity_counts.get(f["severity"], 0) + 1

        self.emit_progress(
            f"  ✓ {scanned} files scanned • "
            f"{len(risk_findings)} risk patterns • "
            f"CRITICAL:{severity_counts['CRITICAL']} HIGH:{severity_counts['HIGH']}"
        )

        return {
            "risk_findings": risk_findings[:100],  # cap at 100 for payload
            "severity_summary": severity_counts,
            "files_scanned": scanned,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Module 4: Issue & PR Mining (GitHub API)
    # ─────────────────────────────────────────────────────────────────────────

    def _run_issue_pr_mining(self, owner: Optional[str], repo_name: Optional[str]) -> Dict:
        """Fetch open issues, PRs, stale issues and community health signals."""
        self.emit_progress("Module 4/4 — Issue & PR Mining")
        if not owner or not repo_name:
            self.emit_progress("  ✗ No owner/repo info — skipping issue mining")
            return {}

        base_url = f"https://api.github.com/repos/{owner}/{repo_name}"
        result: Dict = {}

        try:
            # Fetch open issues (not PRs)
            resp = requests.get(
                f"{base_url}/issues",
                headers=self._github_headers,
                params={"state": "open", "per_page": 30, "pulls": False},
                timeout=10,
            )
            if resp.status_code == 200:
                issues = [i for i in resp.json() if not i.get("pull_request")]
                result["open_issues"] = len(issues)
                # Label frequency
                label_counts: Dict[str, int] = {}
                for issue in issues:
                    for lbl in issue.get("labels", []):
                        label_counts[lbl["name"]] = label_counts.get(lbl["name"], 0) + 1
                result["top_labels"] = sorted(label_counts.items(), key=lambda x: -x[1])[:10]

            # Fetch open PRs
            resp = requests.get(
                f"{base_url}/pulls",
                headers=self._github_headers,
                params={"state": "open", "per_page": 20},
                timeout=10,
            )
            if resp.status_code == 200:
                prs = resp.json()
                result["open_prs"] = len(prs)
                # Identify stale PRs (>90 days without update)
                from datetime import datetime, timezone
                stale_prs = []
                for pr in prs:
                    updated = pr.get("updated_at", "")
                    if updated:
                        try:
                            dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                            age_days = (datetime.now(timezone.utc) - dt).days
                            if age_days > 90:
                                stale_prs.append(
                                    {
                                        "number": pr["number"],
                                        "title": pr["title"][:80],
                                        "age_days": age_days,
                                    }
                                )
                        except Exception:
                            pass
                result["stale_prs"] = stale_prs[:10]

            # Fetch community health
            resp = requests.get(
                f"{base_url}/community/profile",
                headers=self._github_headers,
                timeout=10,
            )
            if resp.status_code == 200:
                health = resp.json()
                result["community_health"] = {
                    "health_percentage": health.get("health_percentage", 0),
                    "has_readme": health.get("files", {}).get("readme") is not None,
                    "has_contributing": health.get("files", {}).get("contributing") is not None,
                    "has_code_of_conduct": health.get("files", {}).get("code_of_conduct") is not None,
                    "has_issue_template": health.get("files", {}).get("issue_template") is not None,
                }

            # Identify "safe first PR" candidates: good-first-issue + help-wanted labels
            resp = requests.get(
                f"{base_url}/issues",
                headers=self._github_headers,
                params={
                    "state": "open",
                    "labels": "good first issue,help wanted",
                    "per_page": 10,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                gfi = [i for i in resp.json() if not i.get("pull_request")]
                result["good_first_issues"] = [
                    {
                        "number": i["number"],
                        "title": i["title"][:100],
                        "url": i["html_url"],
                        "labels": [l["name"] for l in i.get("labels", [])],
                    }
                    for i in gfi[:5]
                ]

            self.emit_progress(
                f"  ✓ {result.get('open_issues', 0)} open issues • "
                f"{result.get('open_prs', 0)} open PRs • "
                f"{len(result.get('good_first_issues', []))} good-first-issues"
            )
        except Exception as e:
            self.emit_progress(f"  Issue mining failed: {e}")

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Web Search
    # ─────────────────────────────────────────────────────────────────────────

    def _run_web_search(self, repo_name: str, owner: Optional[str]) -> Dict:
        self.emit_progress("Web search — gathering external context...")
        try:
            searcher = WebSearcher()
            results = searcher.search_repo_context(repo_name, owner)
            total = sum(len(v) for v in results.values())
            self.emit_progress(f"  ✓ {total} web sources found")
            return results
        except Exception as e:
            self.emit_progress(f"  Web search failed: {e}")
            return {}

    # ─────────────────────────────────────────────────────────────────────────
    # Main entry point
    # ─────────────────────────────────────────────────────────────────────────

    def investigate(
        self,
        repo_url: str,
        include_web_search: bool = True,
        persona_mode: str = "SOLO_DEV",
        task_graph: Optional[Dict] = None,
    ) -> Dict:
        """Run all 4 extraction modules and return combined intelligence."""
        self.emit_progress("Scout Agent v2 activated", {"persona": persona_mode})
        self.emit_progress(f"Target: {repo_url}")

        # Module 1: Git Intelligence (includes cloning)
        git_data = self._run_git_intelligence(repo_url)

        # Local path is embedded in git_data — still alive for AST + risk scan
        repo_local_path: Optional[str] = git_data.get("local_path")

        # Module 2: AST Structural Analysis
        ast_data = self._run_ast_analysis(repo_local_path)

        # Module 3: Static Risk Scan
        risk_data = self._run_static_risk_scan(repo_local_path)

        # Module 4: Issue & PR Mining
        parts = repo_url.rstrip("/").replace(".git", "").split("/")
        owner = parts[-2] if len(parts) >= 2 else None
        repo_name = git_data.get("repo_name", parts[-1] if parts else "unknown")
        issue_data = self._run_issue_pr_mining(owner, repo_name)

        # Optional: Web Search
        web_results: Dict = {}
        if include_web_search:
            web_results = self._run_web_search(repo_name, owner)

        merged = {
            **git_data,
            "structure": ast_data,
            "risk_points": risk_data,
            "community": issue_data,
            "web_search_results": web_results,
        }

        # Cleanup cloned repo — no longer needed after all modules have run
        if repo_local_path and os.path.exists(repo_local_path):
            try:
                import shutil as _shutil
                _shutil.rmtree(repo_local_path)
            except Exception:
                pass
        # Strip local_path from merged so callers don't attempt to use a deleted dir
        merged.pop("local_path", None)

        self.emit_progress(
            "Scout investigation complete",
            {
                "confidence_boost": 40,
                "modules_run": 4,
                "has_ast": bool(ast_data),
                "has_risk_scan": bool(risk_data),
                "has_issue_data": bool(issue_data),
            },
        )
        return merged