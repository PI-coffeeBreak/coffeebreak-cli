"""Plugin developer tools for CoffeeBreak CLI."""

import json
import os
import subprocess
from typing import Any, Dict, List, Optional

from coffeebreak.utils.errors import PluginError


class PluginDeveloperTools:
    """Developer tools for plugin quality assurance and development assistance."""

    def __init__(self, verbose: bool = False):
        """Initialize developer tools."""
        self.verbose = verbose
        self.tools = {
            "lint": self._run_linting,
            "format": self._run_formatting,
            "type_check": self._run_type_checking,
            "security": self._run_security_analysis,
            "dependency_check": self._run_dependency_analysis,
            "performance": self._run_performance_analysis,
            "complexity": self._run_complexity_analysis,
        }

    def run_quality_assurance(
        self,
        plugin_dir: str = ".",
        tools: Optional[List[str]] = None,
        fix_issues: bool = False,
        generate_report: bool = True,
    ) -> Dict[str, Any]:
        """
        Run comprehensive quality assurance checks on a plugin.

        Args:
            plugin_dir: Plugin directory to analyze
            tools: Specific tools to run (lint, format, type_check, security, etc.)
            fix_issues: Whether to automatically fix issues where possible
            generate_report: Whether to generate a comprehensive report

        Returns:
            Dict[str, Any]: Quality assurance results
        """
        try:
            plugin_dir = os.path.abspath(plugin_dir)

            if self.verbose:
                print(f"Running quality assurance for plugin at {plugin_dir}")

            # Validate plugin directory
            if not self._is_valid_plugin_directory(plugin_dir):
                raise PluginError(f"Invalid plugin directory: {plugin_dir}")

            # Load plugin configuration
            plugin_config = self._load_plugin_config(plugin_dir)
            plugin_name = plugin_config["plugin"]["name"]

            # Determine which tools to run
            if tools is None:
                tools = self._detect_available_tools(plugin_dir)

            if self.verbose:
                print(f"Running tools: {tools}")

            # Initialize results
            results = {
                "plugin_name": plugin_name,
                "plugin_dir": plugin_dir,
                "tools": tools,
                "overall_score": 0,
                "issues_found": 0,
                "issues_fixed": 0,
                "results": {},
                "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
                "recommendations": [],
            }

            # Run each tool
            for tool in tools:
                if tool in self.tools:
                    if self.verbose:
                        print(f"Running {tool}...")

                    try:
                        tool_result = self.tools[tool](
                            plugin_dir, plugin_config, fix_issues
                        )
                        results["results"][tool] = tool_result

                        # Update summary
                        issues = tool_result.get("issues", [])
                        results["issues_found"] += len(issues)

                        for issue in issues:
                            severity = issue.get("severity", "low")
                            if severity in results["summary"]:
                                results["summary"][severity] += 1

                        # Track fixes
                        results["issues_fixed"] += tool_result.get("fixes_applied", 0)

                        # Collect recommendations
                        recommendations = tool_result.get("recommendations", [])
                        results["recommendations"].extend(recommendations)

                    except Exception as e:
                        results["results"][tool] = {
                            "success": False,
                            "error": str(e),
                            "issues": [],
                        }
                else:
                    if self.verbose:
                        print(f"Unknown tool: {tool}")

            # Calculate overall score
            results["overall_score"] = self._calculate_quality_score(results)

            # Generate report if requested
            if generate_report:
                report_path = self._generate_qa_report(results, plugin_dir)
                results["report_path"] = report_path

            if self.verbose:
                self._print_qa_summary(results)

            return results

        except Exception as e:
            raise PluginError(f"Failed to run quality assurance: {e}") from e

    def _detect_available_tools(self, plugin_dir: str) -> List[str]:
        """Detect which tools are available and applicable."""
        available_tools = []

        # Check for Python files
        src_path = os.path.join(plugin_dir, "src")
        if os.path.exists(src_path):
            python_files = []
            for _root, _dirs, files in os.walk(src_path):
                python_files.extend([f for f in files if f.endswith(".py")])

            if python_files:
                available_tools.extend(["lint", "format", "security", "complexity"])

        # Check for JavaScript/TypeScript files
        js_files = []
        ts_files = []
        if os.path.exists(src_path):
            for _root, _dirs, files in os.walk(src_path):
                js_files.extend([f for f in files if f.endswith((".js", ".jsx"))])
                ts_files.extend([f for f in files if f.endswith((".ts", ".tsx"))])

        if js_files or ts_files:
            available_tools.extend(["lint", "format"])

        if ts_files:
            available_tools.append("type_check")

        # Check for package files
        if os.path.exists(
            os.path.join(plugin_dir, "requirements.txt")
        ) or os.path.exists(os.path.join(plugin_dir, "package.json")):
            available_tools.append("dependency_check")

        # Performance analysis is available for any plugin
        available_tools.append("performance")

        return list(set(available_tools))  # Remove duplicates

    def _run_linting(
        self, plugin_dir: str, plugin_config: Dict[str, Any], fix_issues: bool
    ) -> Dict[str, Any]:
        """Run linting analysis."""
        result = {
            "success": True,
            "issues": [],
            "fixes_applied": 0,
            "recommendations": [],
            "tools_used": [],
        }

        src_path = os.path.join(plugin_dir, "src")
        if not os.path.exists(src_path):
            result["issues"].append(
                {
                    "severity": "medium",
                    "type": "structure",
                    "message": "No src directory found",
                    "file": ".",
                    "line": 0,
                }
            )
            return result

        # Python linting with flake8
        python_files = []
        for _root, _dirs, files in os.walk(src_path):
            python_files.extend(
                [os.path.join(_root, f) for f in files if f.endswith(".py")]
            )

        if python_files:
            try:
                # Run flake8
                cmd = ["flake8", "--max-line-length=100", "--format=json", src_path]
                process_result = subprocess.run(
                    cmd, cwd=plugin_dir, capture_output=True, text=True
                )

                result["tools_used"].append("flake8")

                if process_result.stdout:
                    try:
                        flake8_issues = json.loads(process_result.stdout)
                        for issue in flake8_issues:
                            result["issues"].append(
                                {
                                    "severity": self._map_flake8_severity(
                                        issue.get("code", "")
                                    ),
                                    "type": "lint",
                                    "message": issue.get("text", ""),
                                    "file": issue.get("filename", ""),
                                    "line": issue.get("line_number", 0),
                                    "column": issue.get("column_number", 0),
                                    "code": issue.get("code", ""),
                                }
                            )
                    except json.JSONDecodeError:
                        # Fall back to parsing text output
                        lines = process_result.stdout.split("\n")
                        for line in lines:
                            if ":" in line and len(line.strip()) > 0:
                                parts = line.split(":", 3)
                                if len(parts) >= 4:
                                    result["issues"].append(
                                        {
                                            "severity": "medium",
                                            "type": "lint",
                                            "message": parts[3].strip(),
                                            "file": parts[0],
                                            "line": int(parts[1])
                                            if parts[1].isdigit()
                                            else 0,
                                        }
                                    )

                # Auto-fix with autopep8 if requested
                if fix_issues:
                    try:
                        for py_file in python_files:
                            cmd = [
                                "autopep8",
                                "--in-place",
                                "--max-line-length=100",
                                py_file,
                            ]
                            fix_result = subprocess.run(cmd, capture_output=True)
                            if fix_result.returncode == 0:
                                result["fixes_applied"] += 1

                        result["recommendations"].append(
                            "Applied autopep8 formatting fixes"
                        )
                    except FileNotFoundError:
                        result["recommendations"].append(
                            "Install autopep8 for automatic formatting fixes"
                        )

            except FileNotFoundError:
                result["recommendations"].append(
                    "Install flake8 for Python linting: pip install flake8"
                )

        # JavaScript/TypeScript linting with ESLint
        js_files = []
        ts_files = []
        for _root, _dirs, files in os.walk(src_path):
            js_files.extend([f for f in files if f.endswith((".js", ".jsx"))])
            ts_files.extend([f for f in files if f.endswith((".ts", ".tsx"))])

        if js_files or ts_files:
            try:
                cmd = ["npx", "eslint", "--format=json", src_path]
                process_result = subprocess.run(
                    cmd, cwd=plugin_dir, capture_output=True, text=True
                )

                result["tools_used"].append("eslint")

                if process_result.stdout:
                    try:
                        eslint_results = json.loads(process_result.stdout)
                        for file_result in eslint_results:
                            for message in file_result.get("messages", []):
                                result["issues"].append(
                                    {
                                        "severity": self._map_eslint_severity(
                                            message.get("severity", 1)
                                        ),
                                        "type": "lint",
                                        "message": message.get("message", ""),
                                        "file": file_result.get("filePath", ""),
                                        "line": message.get("line", 0),
                                        "column": message.get("column", 0),
                                        "rule": message.get("ruleId", ""),
                                    }
                                )
                    except json.JSONDecodeError:
                        pass

                # Auto-fix with ESLint if requested
                if fix_issues:
                    cmd = ["npx", "eslint", "--fix", src_path]
                    fix_result = subprocess.run(
                        cmd, cwd=plugin_dir, capture_output=True
                    )
                    if fix_result.returncode == 0:
                        result["fixes_applied"] += len(js_files) + len(ts_files)
                        result["recommendations"].append("Applied ESLint auto-fixes")

            except FileNotFoundError:
                result["recommendations"].append(
                    "Install ESLint for JavaScript/TypeScript linting"
                )

        return result

    def _run_formatting(
        self, plugin_dir: str, plugin_config: Dict[str, Any], fix_issues: bool
    ) -> Dict[str, Any]:
        """Run code formatting checks."""
        result = {
            "success": True,
            "issues": [],
            "fixes_applied": 0,
            "recommendations": [],
            "tools_used": [],
        }

        src_path = os.path.join(plugin_dir, "src")
        if not os.path.exists(src_path):
            return result

        # Python formatting with black
        python_files = []
        for _root, _dirs, files in os.walk(src_path):
            python_files.extend(
                [os.path.join(_root, f) for f in files if f.endswith(".py")]
            )

        if python_files:
            try:
                # Check formatting
                cmd = ["black", "--check", "--line-length=100", src_path]
                process_result = subprocess.run(
                    cmd, cwd=plugin_dir, capture_output=True, text=True
                )

                result["tools_used"].append("black")

                if process_result.returncode != 0:
                    # Parse black output for unformatted files
                    lines = process_result.stderr.split("\n")
                    for line in lines:
                        if "would reformat" in line:
                            filename = (
                                line.split()[2] if len(line.split()) > 2 else "unknown"
                            )
                            result["issues"].append(
                                {
                                    "severity": "low",
                                    "type": "format",
                                    "message": "File needs formatting",
                                    "file": filename,
                                    "line": 0,
                                }
                            )

                # Auto-format if requested
                if fix_issues:
                    cmd = ["black", "--line-length=100", src_path]
                    fix_result = subprocess.run(
                        cmd, cwd=plugin_dir, capture_output=True
                    )
                    if fix_result.returncode == 0:
                        result["fixes_applied"] = len(python_files)
                        result["recommendations"].append("Applied black formatting")

            except FileNotFoundError:
                result["recommendations"].append(
                    "Install black for Python formatting: pip install black"
                )

        # JavaScript/TypeScript formatting with Prettier
        js_ts_files = []
        for _root, _dirs, files in os.walk(src_path):
            js_ts_files.extend(
                [f for f in files if f.endswith((".js", ".jsx", ".ts", ".tsx"))]
            )

        if js_ts_files:
            try:
                cmd = ["npx", "prettier", "--check", src_path]
                process_result = subprocess.run(
                    cmd, cwd=plugin_dir, capture_output=True, text=True
                )

                result["tools_used"].append("prettier")

                if process_result.returncode != 0:
                    unformatted_files = process_result.stdout.split("\n")
                    for filename in unformatted_files:
                        if filename.strip():
                            result["issues"].append(
                                {
                                    "severity": "low",
                                    "type": "format",
                                    "message": "File needs formatting",
                                    "file": filename.strip(),
                                    "line": 0,
                                }
                            )

                # Auto-format if requested
                if fix_issues:
                    cmd = ["npx", "prettier", "--write", src_path]
                    fix_result = subprocess.run(
                        cmd, cwd=plugin_dir, capture_output=True
                    )
                    if fix_result.returncode == 0:
                        result["fixes_applied"] = len(js_ts_files)
                        result["recommendations"].append("Applied Prettier formatting")

            except FileNotFoundError:
                result["recommendations"].append(
                    "Install Prettier for JavaScript/TypeScript formatting"
                )

        return result

    def _run_type_checking(
        self, plugin_dir: str, plugin_config: Dict[str, Any], fix_issues: bool
    ) -> Dict[str, Any]:
        """Run type checking analysis."""
        result = {
            "success": True,
            "issues": [],
            "fixes_applied": 0,
            "recommendations": [],
            "tools_used": [],
        }

        # Python type checking with mypy
        src_path = os.path.join(plugin_dir, "src")
        if os.path.exists(src_path):
            python_files = []
            for _root, _dirs, files in os.walk(src_path):
                python_files.extend([f for f in files if f.endswith(".py")])

            if python_files:
                try:
                    cmd = ["mypy", "--json-report", "/tmp/mypy-report", src_path]
                    process_result = subprocess.run(
                        cmd, cwd=plugin_dir, capture_output=True, text=True
                    )

                    result["tools_used"].append("mypy")

                    # Parse mypy output
                    lines = process_result.stdout.split("\n")
                    for line in lines:
                        if ":" in line and ("error:" in line or "warning:" in line):
                            parts = line.split(":", 3)
                            if len(parts) >= 4:
                                severity = "high" if "error:" in line else "medium"
                                result["issues"].append(
                                    {
                                        "severity": severity,
                                        "type": "type",
                                        "message": parts[3].strip(),
                                        "file": parts[0],
                                        "line": int(parts[1])
                                        if parts[1].isdigit()
                                        else 0,
                                    }
                                )

                except FileNotFoundError:
                    result["recommendations"].append(
                        "Install mypy for Python type checking: pip install mypy"
                    )

        # TypeScript type checking
        tsconfig_path = os.path.join(plugin_dir, "tsconfig.json")
        if os.path.exists(tsconfig_path):
            try:
                cmd = ["npx", "tsc", "--noEmit"]
                process_result = subprocess.run(
                    cmd, cwd=plugin_dir, capture_output=True, text=True
                )

                result["tools_used"].append("tsc")

                if process_result.returncode != 0:
                    lines = process_result.stdout.split("\n")
                    for line in lines:
                        if ":" in line and "error" in line.lower():
                            parts = line.split(":", 3)
                            if len(parts) >= 3:
                                result["issues"].append(
                                    {
                                        "severity": "high",
                                        "type": "type",
                                        "message": parts[2].strip()
                                        if len(parts) > 2
                                        else line,
                                        "file": parts[0] if len(parts) > 0 else "",
                                        "line": int(parts[1])
                                        if len(parts) > 1 and parts[1].isdigit()
                                        else 0,
                                    }
                                )

            except FileNotFoundError:
                result["recommendations"].append("Install TypeScript for type checking")

        return result

    def _run_security_analysis(
        self, plugin_dir: str, plugin_config: Dict[str, Any], fix_issues: bool
    ) -> Dict[str, Any]:
        """Run security analysis."""
        result = {
            "success": True,
            "issues": [],
            "fixes_applied": 0,
            "recommendations": [],
            "tools_used": [],
        }

        # Python security analysis with bandit
        src_path = os.path.join(plugin_dir, "src")
        if os.path.exists(src_path):
            python_files = []
            for _root, _dirs, files in os.walk(src_path):
                python_files.extend([f for f in files if f.endswith(".py")])

            if python_files:
                try:
                    cmd = ["bandit", "-r", "-f", "json", src_path]
                    process_result = subprocess.run(
                        cmd, cwd=plugin_dir, capture_output=True, text=True
                    )

                    result["tools_used"].append("bandit")

                    if process_result.stdout:
                        try:
                            bandit_results = json.loads(process_result.stdout)
                            for issue in bandit_results.get("results", []):
                                result["issues"].append(
                                    {
                                        "severity": self._map_bandit_severity(
                                            issue.get("issue_severity", "LOW")
                                        ),
                                        "type": "security",
                                        "message": issue.get("issue_text", ""),
                                        "file": issue.get("filename", ""),
                                        "line": issue.get("line_number", 0),
                                        "test_id": issue.get("test_id", ""),
                                        "confidence": issue.get("issue_confidence", ""),
                                    }
                                )
                        except json.JSONDecodeError:
                            pass

                except FileNotFoundError:
                    result["recommendations"].append(
                        "Install bandit for Python security analysis: pip install bandit"
                    )

        # Node.js security analysis
        package_json_path = os.path.join(plugin_dir, "package.json")
        if os.path.exists(package_json_path):
            try:
                cmd = ["npm", "audit", "--json"]
                process_result = subprocess.run(
                    cmd, cwd=plugin_dir, capture_output=True, text=True
                )

                result["tools_used"].append("npm audit")

                if process_result.stdout:
                    try:
                        audit_results = json.loads(process_result.stdout)
                        vulnerabilities = audit_results.get("vulnerabilities", {})

                        for pkg_name, vuln_info in vulnerabilities.items():
                            result["issues"].append(
                                {
                                    "severity": self._map_npm_severity(
                                        vuln_info.get("severity", "low")
                                    ),
                                    "type": "security",
                                    "message": f"Vulnerability in {pkg_name}: {vuln_info.get('title', 'Unknown')}",
                                    "file": "package.json",
                                    "line": 0,
                                    "package": pkg_name,
                                    "via": vuln_info.get("via", []),
                                }
                            )
                    except json.JSONDecodeError:
                        pass

                # Auto-fix npm vulnerabilities if requested
                if fix_issues:
                    cmd = ["npm", "audit", "fix"]
                    fix_result = subprocess.run(
                        cmd, cwd=plugin_dir, capture_output=True
                    )
                    if fix_result.returncode == 0:
                        result["fixes_applied"] = 1
                        result["recommendations"].append("Applied npm audit fixes")

            except FileNotFoundError:
                result["recommendations"].append("npm not available for security audit")

        return result

    def _run_dependency_analysis(
        self, plugin_dir: str, plugin_config: Dict[str, Any], fix_issues: bool
    ) -> Dict[str, Any]:
        """Run dependency analysis."""
        result = {
            "success": True,
            "issues": [],
            "fixes_applied": 0,
            "recommendations": [],
            "tools_used": [],
        }

        # Python dependency analysis
        requirements_path = os.path.join(plugin_dir, "requirements.txt")
        if os.path.exists(requirements_path):
            try:
                # Check for outdated packages
                cmd = ["pip", "list", "--outdated", "--format=json"]
                process_result = subprocess.run(cmd, capture_output=True, text=True)

                result["tools_used"].append("pip list")

                if process_result.stdout:
                    try:
                        outdated = json.loads(process_result.stdout)
                        for package in outdated:
                            result["issues"].append(
                                {
                                    "severity": "low",
                                    "type": "dependency",
                                    "message": f"Package {package['name']} is outdated: {package['version']} -> {package['latest_version']}",
                                    "file": "requirements.txt",
                                    "line": 0,
                                    "package": package["name"],
                                    "current_version": package["version"],
                                    "latest_version": package["latest_version"],
                                }
                            )
                    except json.JSONDecodeError:
                        pass

            except FileNotFoundError:
                result["recommendations"].append(
                    "pip not available for dependency analysis"
                )

        # Node.js dependency analysis
        package_json_path = os.path.join(plugin_dir, "package.json")
        if os.path.exists(package_json_path):
            try:
                cmd = ["npm", "outdated", "--json"]
                process_result = subprocess.run(
                    cmd, cwd=plugin_dir, capture_output=True, text=True
                )

                result["tools_used"].append("npm outdated")

                if process_result.stdout:
                    try:
                        outdated = json.loads(process_result.stdout)
                        for package, info in outdated.items():
                            result["issues"].append(
                                {
                                    "severity": "low",
                                    "type": "dependency",
                                    "message": f"Package {package} is outdated: {info['current']} -> {info['latest']}",
                                    "file": "package.json",
                                    "line": 0,
                                    "package": package,
                                    "current_version": info.get("current"),
                                    "latest_version": info.get("latest"),
                                }
                            )
                    except json.JSONDecodeError:
                        pass

            except FileNotFoundError:
                result["recommendations"].append(
                    "npm not available for dependency analysis"
                )

        return result

    def _run_performance_analysis(
        self, plugin_dir: str, plugin_config: Dict[str, Any], fix_issues: bool
    ) -> Dict[str, Any]:
        """Run performance analysis."""
        result = {
            "success": True,
            "issues": [],
            "fixes_applied": 0,
            "recommendations": [],
            "tools_used": ["performance_analyzer"],
        }

        # Analyze plugin size and structure
        src_path = os.path.join(plugin_dir, "src")
        if os.path.exists(src_path):
            total_size = 0
            file_count = 0

            for _root, _dirs, files in os.walk(src_path):
                for file in files:
                    file_path = os.path.join(_root, file)
                    try:
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        file_count += 1

                        # Check for large files
                        if file_size > 100 * 1024:  # 100KB
                            result["issues"].append(
                                {
                                    "severity": "medium",
                                    "type": "performance",
                                    "message": f"Large file detected: {file} ({file_size // 1024}KB)",
                                    "file": os.path.relpath(file_path, plugin_dir),
                                    "line": 0,
                                    "size": file_size,
                                }
                            )
                    except OSError:
                        continue

            # Check overall plugin size
            if total_size > 10 * 1024 * 1024:  # 10MB
                result["issues"].append(
                    {
                        "severity": "high",
                        "type": "performance",
                        "message": f"Plugin is very large: {total_size // (1024 * 1024)}MB",
                        "file": ".",
                        "line": 0,
                        "total_size": total_size,
                    }
                )

            # Check for too many files
            if file_count > 100:
                result["issues"].append(
                    {
                        "severity": "medium",
                        "type": "performance",
                        "message": f"Many files in plugin: {file_count} files",
                        "file": ".",
                        "line": 0,
                        "file_count": file_count,
                    }
                )

        # Check for performance-critical dependencies
        requirements_path = os.path.join(plugin_dir, "requirements.txt")
        if os.path.exists(requirements_path):
            with open(requirements_path) as f:
                requirements = f.read().lower()

                heavy_packages = [
                    "tensorflow",
                    "torch",
                    "opencv",
                    "numpy",
                    "pandas",
                    "scipy",
                ]
                for package in heavy_packages:
                    if package in requirements:
                        result["recommendations"].append(
                            f"Heavy dependency detected: {package}. Consider optimization or lazy loading."
                        )

        return result

    def _run_complexity_analysis(
        self, plugin_dir: str, plugin_config: Dict[str, Any], fix_issues: bool
    ) -> Dict[str, Any]:
        """Run code complexity analysis."""
        result = {
            "success": True,
            "issues": [],
            "fixes_applied": 0,
            "recommendations": [],
            "tools_used": [],
        }

        # Python complexity analysis with radon
        src_path = os.path.join(plugin_dir, "src")
        if os.path.exists(src_path):
            python_files = []
            for _root, _dirs, files in os.walk(src_path):
                python_files.extend(
                    [os.path.join(_root, f) for f in files if f.endswith(".py")]
                )

            if python_files:
                try:
                    # Cyclomatic complexity
                    cmd = ["radon", "cc", "--json", src_path]
                    process_result = subprocess.run(cmd, capture_output=True, text=True)

                    result["tools_used"].append("radon")

                    if process_result.stdout:
                        try:
                            complexity_results = json.loads(process_result.stdout)
                            for file_path, functions in complexity_results.items():
                                for func in functions:
                                    complexity = func.get("complexity", 0)
                                    if complexity > 10:  # High complexity threshold
                                        severity = (
                                            "high" if complexity > 20 else "medium"
                                        )
                                        result["issues"].append(
                                            {
                                                "severity": severity,
                                                "type": "complexity",
                                                "message": f"High complexity function: {func.get('name', 'unknown')} (complexity: {complexity})",
                                                "file": file_path,
                                                "line": func.get("lineno", 0),
                                                "complexity": complexity,
                                                "function": func.get("name", ""),
                                            }
                                        )
                        except json.JSONDecodeError:
                            pass

                except FileNotFoundError:
                    result["recommendations"].append(
                        "Install radon for complexity analysis: pip install radon"
                    )

        return result

    def _calculate_quality_score(self, results: Dict[str, Any]) -> int:
        """Calculate an overall quality score (0-100)."""
        total_issues = results["issues_found"]

        if total_issues == 0:
            return 100

        # Weight issues by severity
        weights = {"critical": 20, "high": 10, "medium": 5, "low": 1, "info": 0.5}

        weighted_score = 0
        for severity, count in results["summary"].items():
            weighted_score += count * weights.get(severity, 1)

        # Calculate score (max deduction of 100 points)
        score = max(0, 100 - min(100, weighted_score))

        return int(score)

    def _generate_qa_report(self, results: Dict[str, Any], plugin_dir: str) -> str:
        """Generate a quality assurance report."""
        report_path = os.path.join(plugin_dir, "qa-report.md")

        lines = [
            f"# Quality Assurance Report: {results['plugin_name']}",
            "",
            f"**Overall Score:** {results['overall_score']}/100",
            f"**Issues Found:** {results['issues_found']}",
            f"**Issues Fixed:** {results['issues_fixed']}",
            "",
            "## Summary",
            "",
            f"- Critical: {results['summary']['critical']}",
            f"- High: {results['summary']['high']}",
            f"- Medium: {results['summary']['medium']}",
            f"- Low: {results['summary']['low']}",
            f"- Info: {results['summary']['info']}",
            "",
            "## Tools Used",
            "",
        ]

        all_tools = set()
        for tool_result in results["results"].values():
            all_tools.update(tool_result.get("tools_used", []))

        for tool in sorted(all_tools):
            lines.append(f"- {tool}")

        lines.extend(["", "## Issues by Tool", ""])

        for tool, tool_result in results["results"].items():
            lines.extend([f"### {tool.title()}", ""])

            issues = tool_result.get("issues", [])
            if issues:
                for issue in issues[:10]:  # Show first 10 issues
                    severity_icon = {
                        "critical": "🔴",
                        "high": "🟠",
                        "medium": "🟡",
                        "low": "🔵",
                        "info": "ℹ️",
                    }.get(issue["severity"], "❓")

                    lines.append(
                        f"{severity_icon} **{issue['severity'].upper()}** - {issue['message']}"
                    )
                    if issue.get("file"):
                        lines.append(
                            f"   - File: {issue['file']}:{issue.get('line', 0)}"
                        )
                    lines.append("")

                if len(issues) > 10:
                    lines.append(f"... and {len(issues) - 10} more issues")
                    lines.append("")
            else:
                lines.extend(["No issues found.", ""])

        if results["recommendations"]:
            lines.extend(["## Recommendations", ""])

            for rec in set(results["recommendations"]):  # Remove duplicates
                lines.append(f"- {rec}")

            lines.append("")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return report_path

    def _print_qa_summary(self, results: Dict[str, Any]) -> None:
        """Print a formatted QA summary."""
        print(f"\n=== Quality Assurance Summary for {results['plugin_name']} ===")
        print(f"Overall Score: {results['overall_score']}/100")
        print(f"Issues Found: {results['issues_found']}")
        print(f"Issues Fixed: {results['issues_fixed']}")

        print("\n=== Issue Breakdown ===")
        for severity, count in results["summary"].items():
            if count > 0:
                icon = {
                    "critical": "🔴",
                    "high": "🟠",
                    "medium": "🟡",
                    "low": "🔵",
                    "info": "ℹ️",
                }.get(severity, "❓")
                print(f"{icon} {severity.title()}: {count}")

        if results.get("report_path"):
            print(f"\nDetailed report: {results['report_path']}")

    def _map_flake8_severity(self, code: str) -> str:
        """Map flake8 error codes to severity levels."""
        if code.startswith("E9") or code.startswith("F"):
            return "high"
        elif code.startswith("E7") or code.startswith("W6"):
            return "medium"
        else:
            return "low"

    def _map_eslint_severity(self, severity: int) -> str:
        """Map ESLint severity to our severity levels."""
        return "high" if severity == 2 else "medium"

    def _map_bandit_severity(self, severity: str) -> str:
        """Map bandit severity to our severity levels."""
        severity_map = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
        return severity_map.get(severity.upper(), "medium")

    def _map_npm_severity(self, severity: str) -> str:
        """Map npm audit severity to our severity levels."""
        severity_map = {
            "critical": "critical",
            "high": "high",
            "moderate": "medium",
            "low": "low",
            "info": "info",
        }
        return severity_map.get(severity.lower(), "medium")

    def _is_valid_plugin_directory(self, plugin_dir: str) -> bool:
        """Check if directory is a valid plugin."""
        manifest_path = os.path.join(plugin_dir, "coffeebreak-plugin.yml")
        return os.path.exists(manifest_path)

    def _load_plugin_config(self, plugin_dir: str) -> Dict[str, Any]:
        """Load plugin configuration."""
        config_path = os.path.join(plugin_dir, "coffeebreak-plugin.yml")
        from coffeebreak.config.manager import ConfigManager

        config_manager = ConfigManager()
        return config_manager.load_config_file(config_path)
