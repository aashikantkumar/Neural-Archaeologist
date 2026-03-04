"""
AST Parser Utility — Multi-language AST parsing using tree-sitter.

Extracts:
- File structure and entry point candidates
- Function signatures, docstrings, complexity estimates
- Module imports and exported APIs
- Import/dependency graph
"""

import os
import re
import subprocess
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


# Language-specific entry point patterns
ENTRY_POINT_PATTERNS = {
    "python": [
        r'if\s+__name__\s*==\s*["\']__main__["\']',
        r'app\s*=\s*FastAPI\(',
        r'app\s*=\s*Flask\(',
        r'app\.run\(',
        r'uvicorn\.run\(',
    ],
    "javascript": [
        r'app\.listen\(',
        r'express\(\)',
        r'createServer\(',
        r'module\.exports',
        r'export\s+default',
    ],
    "typescript": [
        r'app\.listen\(',
        r'express\(\)',
        r'createServer\(',
        r'export\s+default',
    ],
    "java": [
        r'public\s+static\s+void\s+main\s*\(',
        r'@SpringBootApplication',
    ],
    "go": [
        r'func\s+main\s*\(\s*\)',
        r'func\s+init\s*\(\s*\)',
    ],
}

# Language-specific import patterns
IMPORT_PATTERNS = {
    "python": [
        r'^import\s+([\w.]+)',
        r'^from\s+([\w.]+)\s+import',
    ],
    "javascript": [
        r'require\(["\']([^"\']+)["\']\)',
        r'import\s+.*?from\s+["\']([^"\']+)["\']',
        r'import\s+["\']([^"\']+)["\']',
    ],
    "typescript": [
        r'import\s+.*?from\s+["\']([^"\']+)["\']',
        r'require\(["\']([^"\']+)["\']\)',
    ],
    "java": [
        r'^import\s+([\w.]+);',
    ],
    "go": [
        r'"([\w./]+)"',
    ],
}

# Function definition patterns
FUNCTION_PATTERNS = {
    "python": r'(?:^|\n)([ \t]*)(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)',
    "javascript": r'(?:^|\n)([ \t]*)(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)|(?:^|\n)([ \t]*)(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(?([^)]*)\)?\s*=>',
    "typescript": r'(?:^|\n)([ \t]*)(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)|(?:^|\n)([ \t]*)(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(?([^)]*)\)?\s*=>',
    "java": r'(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\(([^)]*)\)',
    "go": r'func\s+(?:\([\w\s*]+\)\s+)?(\w+)\s*\(([^)]*)\)',
}

# File extension to language mapping
EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
}

# Directories to skip
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build", ".next",
    ".nuxt", "vendor", "target", "bin", "obj", ".idea", ".vscode",
    "coverage", ".coverage", "htmlcov", ".eggs", "*.egg-info"
}


class ASTParser:
    """
    Multi-language AST parser that extracts structural information from repos.
    Uses regex-based parsing as a lightweight alternative to tree-sitter
    for hackathon MVP, with the same output interface.
    """

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.files: List[Dict] = []
        self.functions: List[Dict] = []
        self.imports_graph: Dict[str, List[str]] = {}
        self.entry_points: List[Dict] = []
        self.languages: Dict[str, int] = defaultdict(int)

    def scan_repository(self, top_n: int = 50, shallow: bool = False) -> Dict:
        """
        Scan the repository and extract structural data.
        
        Args:
            top_n: Max files to deeply analyze
            shallow: If True, only build file tree + language stats (for monorepos)
        
        Returns:
            Dict with files, functions, imports_graph, entry_points, languages
        """
        # Phase 1: Build file tree
        self._scan_file_tree()
        
        if shallow:
            return self._build_result()
        
        # Phase 2: Parse top-N files by size/importance
        files_to_parse = self._select_files_for_deep_parse(top_n)
        
        for file_info in files_to_parse:
            self._parse_file(file_info)
        
        # Phase 3: Detect entry points
        self._detect_entry_points()
        
        return self._build_result()

    def _scan_file_tree(self):
        """Walk the directory tree and catalog all source files."""
        for root, dirs, files in os.walk(self.repo_path):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
            
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in EXT_TO_LANG:
                    full_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(full_path, self.repo_path)
                    lang = EXT_TO_LANG[ext]
                    
                    try:
                        size = os.path.getsize(full_path)
                    except OSError:
                        size = 0
                    
                    self.languages[lang] += 1
                    self.files.append({
                        "path": rel_path,
                        "language": lang,
                        "size_bytes": size,
                        "extension": ext
                    })

    def _select_files_for_deep_parse(self, top_n: int) -> List[Dict]:
        """Select the most important files for deep parsing."""
        # Sort by size (larger files tend to be more important)
        # but skip very large files (likely generated)
        candidates = [
            f for f in self.files 
            if f["size_bytes"] < 500_000  # Skip files > 500KB
        ]
        candidates.sort(key=lambda f: f["size_bytes"], reverse=True)
        return candidates[:top_n]

    def _parse_file(self, file_info: Dict):
        """Parse a single file for functions, imports, docstrings."""
        full_path = os.path.join(self.repo_path, file_info["path"])
        lang = file_info["language"]
        
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (IOError, OSError):
            return
        
        lines = content.split("\n")
        file_info["line_count"] = len(lines)
        
        # Extract imports
        imports = self._extract_imports(content, lang)
        if imports:
            self.imports_graph[file_info["path"]] = imports
        
        # Extract functions
        functions = self._extract_functions(content, lang, file_info["path"])
        self.functions.extend(functions)
        
        # Check for docstrings / documentation
        file_info["has_module_docstring"] = self._has_module_docstring(content, lang)
        file_info["function_count"] = len(functions)
        documented_funcs = sum(1 for f in functions if f.get("has_docstring"))
        file_info["documented_functions"] = documented_funcs
        file_info["doc_coverage"] = (
            round(documented_funcs / len(functions), 2) if functions else 0.0
        )

    def _extract_imports(self, content: str, language: str) -> List[str]:
        """Extract import statements from source code."""
        imports = []
        patterns = IMPORT_PATTERNS.get(language, [])
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            imports.extend(matches)
        
        return list(set(imports))

    def _extract_functions(self, content: str, language: str, file_path: str) -> List[Dict]:
        """Extract function definitions from source code."""
        functions = []
        pattern = FUNCTION_PATTERNS.get(language)
        
        if not pattern:
            return functions
        
        lines = content.split("\n")
        
        if language == "python":
            matches = re.finditer(pattern, content)
            for match in matches:
                indent = match.group(1) or ""
                name = match.group(2)
                params = match.group(3)
                
                # Find the line number
                start_pos = match.start()
                start_line = content[:start_pos].count("\n") + 1
                
                # Estimate end line (next function or end of indent block)
                end_line = self._estimate_function_end(lines, start_line - 1, len(indent))
                
                # Check for docstring
                has_docstring = self._function_has_docstring(lines, start_line - 1, language)
                
                # Estimate cyclomatic complexity
                func_body = "\n".join(lines[start_line - 1:end_line])
                complexity = self._estimate_cyclomatic_complexity(func_body, language)
                
                functions.append({
                    "file": file_path,
                    "name": name,
                    "params": params.strip(),
                    "start_line": start_line,
                    "end_line": end_line,
                    "cyclomatic_complexity": complexity,
                    "has_docstring": has_docstring,
                    "is_async": "async" in content[max(0, start_pos - 10):start_pos + 5]
                })
        
        elif language in ("javascript", "typescript"):
            # Handle both function declarations and arrow functions
            for match in re.finditer(pattern, content):
                groups = match.groups()
                # Regular function: groups 0-2, Arrow: groups 3-5
                if groups[1]:  # Regular function
                    name = groups[1]
                    params = groups[2] or ""
                elif groups[4]:  # Arrow function
                    name = groups[4]
                    params = groups[5] or ""
                else:
                    continue
                
                start_pos = match.start()
                start_line = content[:start_pos].count("\n") + 1
                end_line = min(start_line + 30, len(lines))  # Approximate
                
                func_body = "\n".join(lines[start_line - 1:end_line])
                complexity = self._estimate_cyclomatic_complexity(func_body, language)
                
                functions.append({
                    "file": file_path,
                    "name": name,
                    "params": params.strip(),
                    "start_line": start_line,
                    "end_line": end_line,
                    "cyclomatic_complexity": complexity,
                    "has_docstring": self._function_has_docstring(lines, start_line - 1, language),
                    "is_async": "async" in content[max(0, start_pos - 10):start_pos + 5]
                })
        
        else:
            # Generic extraction for Java, Go, etc.
            for match in re.finditer(pattern, content):
                name = match.group(1) if match.group(1) else "unknown"
                params = match.group(2) if len(match.groups()) > 1 else ""
                
                start_pos = match.start()
                start_line = content[:start_pos].count("\n") + 1
                
                functions.append({
                    "file": file_path,
                    "name": name,
                    "params": params.strip(),
                    "start_line": start_line,
                    "end_line": start_line + 20,
                    "cyclomatic_complexity": 1,
                    "has_docstring": False,
                    "is_async": False
                })
        
        return functions

    def _estimate_function_end(self, lines: List[str], start_idx: int, base_indent: int) -> int:
        """Estimate where a Python function ends based on indentation."""
        for i in range(start_idx + 1, min(start_idx + 200, len(lines))):
            line = lines[i]
            stripped = line.strip()
            
            if not stripped or stripped.startswith("#"):
                continue
            
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= base_indent and stripped:
                return i
        
        return min(start_idx + 50, len(lines))

    def _function_has_docstring(self, lines: List[str], func_line_idx: int, language: str) -> bool:
        """Check if a function has a docstring."""
        if language == "python":
            # Look for triple-quote on the line after def
            for i in range(func_line_idx + 1, min(func_line_idx + 3, len(lines))):
                line = lines[i].strip()
                if '"""' in line or "'''" in line:
                    return True
                if line and not line.startswith("#"):
                    break
        elif language in ("javascript", "typescript"):
            # Look for JSDoc comment above function
            if func_line_idx > 0:
                prev_line = lines[func_line_idx - 1].strip()
                if prev_line.endswith("*/") or prev_line.startswith("/**"):
                    return True
        return False

    def _has_module_docstring(self, content: str, language: str) -> bool:
        """Check if a file has a module-level docstring."""
        if language == "python":
            stripped = content.lstrip()
            return stripped.startswith('"""') or stripped.startswith("'''")
        elif language in ("javascript", "typescript"):
            stripped = content.lstrip()
            return stripped.startswith("/**") or stripped.startswith("/*")
        return False

    def _estimate_cyclomatic_complexity(self, code: str, language: str) -> int:
        """
        Estimate cyclomatic complexity by counting decision points.
        McCabe: M = E − N + 2P (simplified to counting branches + 1)
        """
        complexity = 1  # Base complexity
        
        # Common decision keywords across languages  
        decision_patterns = [
            r'\bif\b', r'\belif\b', r'\belse\s+if\b', r'\bfor\b', r'\bwhile\b',
            r'\bcatch\b', r'\bexcept\b', r'\bcase\b', r'\b&&\b', r'\b\|\|\b',
            r'\band\b', r'\bor\b', r'\?\s*[^:]+\s*:',  # ternary
        ]
        
        for pattern in decision_patterns:
            complexity += len(re.findall(pattern, code))
        
        return min(complexity, 50)  # Cap at 50

    def _detect_entry_points(self):
        """Detect entry point candidates across all parsed files."""
        for file_info in self.files:
            lang = file_info["language"]
            patterns = ENTRY_POINT_PATTERNS.get(lang, [])
            
            if not patterns:
                continue
            
            full_path = os.path.join(self.repo_path, file_info["path"])
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except (IOError, OSError):
                continue
            
            for pattern in patterns:
                if re.search(pattern, content):
                    # Calculate import fan-out (how many modules this file imports)
                    imports = self.imports_graph.get(file_info["path"], [])
                    
                    # Check if this file is imported by others (fan-in)
                    fan_in = sum(
                        1 for deps in self.imports_graph.values()
                        if any(file_info["path"].replace(".py", "").replace("/", ".") in dep 
                               or os.path.splitext(os.path.basename(file_info["path"]))[0] in dep
                               for dep in deps)
                    )
                    
                    self.entry_points.append({
                        "file": file_info["path"],
                        "language": lang,
                        "pattern_matched": pattern,
                        "fan_out": len(imports),
                        "fan_in": fan_in,
                        "confidence": self._entry_point_confidence(fan_in, len(imports), file_info)
                    })
                    break  # One entry point per file

    def _entry_point_confidence(self, fan_in: int, fan_out: int, file_info: Dict) -> float:
        """
        Score entry point confidence.
        True entry points: low fan-in (few files import them), high fan-out (they import many).
        """
        score = 0.5
        
        # Low fan-in is good for entry points
        if fan_in == 0:
            score += 0.3
        elif fan_in <= 2:
            score += 0.1
        else:
            score -= 0.2  # Likely a library, not entry point
        
        # High fan-out is good
        if fan_out >= 5:
            score += 0.2
        elif fan_out >= 2:
            score += 0.1
        
        return round(min(max(score, 0.0), 1.0), 2)

    def compute_fan_in(self) -> Dict[str, int]:
        """Compute fan-in (number of callers/importers) for each file."""
        fan_in = defaultdict(int)
        
        for source_file, imports in self.imports_graph.items():
            for imp in imports:
                # Try to resolve import to a file path
                resolved = self._resolve_import(imp)
                if resolved:
                    fan_in[resolved] += 1
        
        return dict(fan_in)

    def _resolve_import(self, import_name: str) -> Optional[str]:
        """Try to resolve an import name to a file path in the repo."""
        # Convert dot notation to path
        candidates = [
            import_name.replace(".", "/") + ".py",
            import_name.replace(".", "/") + "/index.js",
            import_name.replace(".", "/") + "/index.ts",
            import_name.replace(".", "/") + ".js",
            import_name.replace(".", "/") + ".ts",
            import_name + ".py",
            import_name + ".js",
        ]
        
        for candidate in candidates:
            for f in self.files:
                if f["path"].endswith(candidate) or f["path"] == candidate:
                    return f["path"]
        
        return None

    def _build_result(self) -> Dict:
        """Build the final result dictionary."""
        return {
            "files": self.files,
            "file_count": len(self.files),
            "functions": self.functions,
            "function_count": len(self.functions),
            "imports_graph": self.imports_graph,
            "entry_points": sorted(
                self.entry_points,
                key=lambda x: x["confidence"],
                reverse=True
            ),
            "languages": dict(self.languages),
            "primary_language": (
                max(self.languages, key=lambda k: self.languages[k])
                if self.languages else "unknown"
            )
        }
