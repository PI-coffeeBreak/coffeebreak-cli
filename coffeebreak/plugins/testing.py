"""Plugin testing framework for CoffeeBreak CLI."""

import json
import os
import subprocess
from typing import Any, Dict, List, Optional

from coffeebreak.utils.errors import PluginError


class PluginTestFramework:
    """Framework for testing CoffeeBreak plugins."""

    def __init__(self, verbose: bool = False):
        """Initialize testing framework."""
        self.verbose = verbose
        self.test_runners = {
            "python": self._run_python_tests,
            "node": self._run_node_tests,
            "integration": self._run_integration_tests,
            "lint": self._run_lint_tests,
            "security": self._run_security_tests,
        }

    def run_plugin_tests(
        self,
        plugin_dir: str = ".",
        test_types: Optional[List[str]] = None,
        coverage: bool = False,
        fail_fast: bool = False,
    ) -> Dict[str, Any]:
        """
        Run comprehensive tests for a plugin.

        Args:
            plugin_dir: Plugin directory to test
            test_types: Specific test types to run (python, node, integration, lint, security)
            coverage: Whether to generate coverage reports
            fail_fast: Whether to stop on first test failure

        Returns:
            Dict[str, Any]: Test results
        """
        try:
            plugin_dir = os.path.abspath(plugin_dir)

            if self.verbose:
                print(f"Running plugin tests for {plugin_dir}")

            # Validate plugin directory
            if not self._is_valid_plugin_directory(plugin_dir):
                raise PluginError(f"Invalid plugin directory: {plugin_dir}")

            # Load plugin configuration
            plugin_config = self._load_plugin_config(plugin_dir)
            plugin_name = plugin_config["plugin"]["name"]

            # Determine which tests to run
            if test_types is None:
                test_types = self._detect_available_test_types(
                    plugin_dir, plugin_config
                )

            if self.verbose:
                print(f"Running test types: {test_types}")

            # Initialize results
            results = {
                "plugin_name": plugin_name,
                "plugin_dir": plugin_dir,
                "test_types": test_types,
                "overall_success": True,
                "summary": {
                    "total_tests": 0,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "errors": 0,
                },
                "results": {},
                "coverage": {},
                "execution_time": 0,
            }

            import time

            start_time = time.time()

            # Run each test type
            for test_type in test_types:
                if test_type in self.test_runners:
                    if self.verbose:
                        print(f"Running {test_type} tests...")

                    try:
                        test_result = self.test_runners[test_type](
                            plugin_dir, plugin_config, coverage
                        )
                        results["results"][test_type] = test_result

                        # Update summary
                        if test_result.get("success", False):
                            results["summary"]["passed"] += test_result.get(
                                "test_count", 0
                            )
                        else:
                            results["summary"]["failed"] += test_result.get(
                                "test_count", 0
                            )
                            results["overall_success"] = False

                            if fail_fast:
                                break

                        results["summary"]["total_tests"] += test_result.get(
                            "test_count", 0
                        )

                        # Collect coverage data
                        if coverage and "coverage" in test_result:
                            results["coverage"][test_type] = test_result["coverage"]

                    except Exception as e:
                        results["results"][test_type] = {
                            "success": False,
                            "error": str(e),
                            "test_count": 0,
                        }
                        results["summary"]["errors"] += 1
                        results["overall_success"] = False

                        if fail_fast:
                            break
                else:
                    if self.verbose:
                        print(f"Unknown test type: {test_type}")

            results["execution_time"] = time.time() - start_time

            if self.verbose:
                self._print_test_summary(results)

            return results

        except Exception as e:
            raise PluginError(f"Failed to run plugin tests: {e}") from e

    def _detect_available_test_types(
        self, plugin_dir: str, plugin_config: Dict[str, Any]
    ) -> List[str]:
        """Detect which test types are available for the plugin."""
        available_tests = []

        # Check for Python tests
        python_test_paths = [
            os.path.join(plugin_dir, "tests"),
            os.path.join(plugin_dir, "test"),
            os.path.join(plugin_dir, "src", "tests"),
        ]

        for test_path in python_test_paths:
            if os.path.exists(test_path):
                python_files = [f for f in os.listdir(test_path) if f.endswith(".py")]
                if python_files:
                    available_tests.append("python")
                    break

        # Check for pytest.ini or setup.cfg
        if os.path.exists(os.path.join(plugin_dir, "pytest.ini")) or os.path.exists(
            os.path.join(plugin_dir, "setup.cfg")
        ):
            if "python" not in available_tests:
                available_tests.append("python")

        # Check for Node.js tests
        package_json_path = os.path.join(plugin_dir, "package.json")
        if os.path.exists(package_json_path):
            try:
                with open(package_json_path) as f:
                    package_data = json.load(f)

                scripts = package_data.get("scripts", {})
                if "test" in scripts or any(
                    "test" in script for script in scripts.keys()
                ):
                    available_tests.append("node")
            except (OSError, json.JSONDecodeError):
                pass

        # Check for integration tests
        integration_paths = [
            os.path.join(plugin_dir, "integration"),
            os.path.join(plugin_dir, "tests", "integration"),
            os.path.join(plugin_dir, "e2e"),
        ]

        for integration_path in integration_paths:
            if os.path.exists(integration_path):
                available_tests.append("integration")
                break

        # Always include lint and security if source files exist
        src_path = os.path.join(plugin_dir, "src")
        if os.path.exists(src_path):
            available_tests.extend(["lint", "security"])

        return available_tests

    def _run_python_tests(
        self, plugin_dir: str, plugin_config: Dict[str, Any], coverage: bool
    ) -> Dict[str, Any]:
        """Run Python tests using pytest."""
        result = {
            "success": False,
            "test_count": 0,
            "details": [],
            "output": "",
            "coverage": {},
        }

        try:
            # Look for pytest configuration or test directories
            test_dirs = []
            for test_dir in ["tests", "test", "src/tests"]:
                full_path = os.path.join(plugin_dir, test_dir)
                if os.path.exists(full_path):
                    test_dirs.append(test_dir)

            if not test_dirs:
                result["details"].append("No Python test directories found")
                return result

            # Build pytest command
            cmd = ["python", "-m", "pytest"]

            # Add coverage if requested
            if coverage:
                cmd.extend(["--cov=src", "--cov-report=json", "--cov-report=term"])

            # Add test directories
            cmd.extend(test_dirs)

            # Add verbose output if needed
            if self.verbose:
                cmd.append("-v")

            # Add JSON report for parsing
            cmd.extend(["--json-report", "--json-report-file=test-report.json"])

            if self.verbose:
                print(f"Running: {' '.join(cmd)}")

            # Run pytest
            process_result = subprocess.run(
                cmd, cwd=plugin_dir, capture_output=True, text=True
            )

            result["output"] = process_result.stdout

            # Parse JSON report if available
            report_path = os.path.join(plugin_dir, "test-report.json")
            if os.path.exists(report_path):
                try:
                    with open(report_path) as f:
                        test_report = json.load(f)

                    result["test_count"] = test_report.get("summary", {}).get(
                        "total", 0
                    )
                    result["success"] = process_result.returncode == 0

                    # Extract test details
                    summary = test_report.get("summary", {})
                    result["details"].append(f"Total tests: {summary.get('total', 0)}")
                    result["details"].append(f"Passed: {summary.get('passed', 0)}")
                    result["details"].append(f"Failed: {summary.get('failed', 0)}")
                    result["details"].append(f"Skipped: {summary.get('skipped', 0)}")

                    # Clean up report file
                    os.remove(report_path)

                except (OSError, json.JSONDecodeError):
                    result["details"].append("Could not parse test report")
                    result["success"] = process_result.returncode == 0
            else:
                # Fall back to return code
                result["success"] = process_result.returncode == 0
                result["details"].append(
                    "Test completed (no detailed report available)"
                )

            # Parse coverage if available
            if coverage:
                coverage_path = os.path.join(plugin_dir, "coverage.json")
                if os.path.exists(coverage_path):
                    try:
                        with open(coverage_path) as f:
                            coverage_data = json.load(f)

                        result["coverage"] = {
                            "percent_covered": coverage_data.get("totals", {}).get(
                                "percent_covered", 0
                            ),
                            "lines_covered": coverage_data.get("totals", {}).get(
                                "covered_lines", 0
                            ),
                            "lines_total": coverage_data.get("totals", {}).get(
                                "num_statements", 0
                            ),
                        }

                        # Clean up coverage file
                        os.remove(coverage_path)

                    except (OSError, json.JSONDecodeError):
                        result["details"].append("Could not parse coverage report")

            if process_result.stderr:
                result["details"].append(f"Stderr: {process_result.stderr}")

        except FileNotFoundError:
            result["details"].append(
                "pytest not found - install pytest to run Python tests"
            )
        except Exception as e:
            result["details"].append(f"Error running Python tests: {e}")

        return result

    def _run_node_tests(
        self, plugin_dir: str, plugin_config: Dict[str, Any], coverage: bool
    ) -> Dict[str, Any]:
        """Run Node.js tests using npm/yarn test."""
        result = {
            "success": False,
            "test_count": 0,
            "details": [],
            "output": "",
            "coverage": {},
        }

        try:
            package_json_path = os.path.join(plugin_dir, "package.json")
            if not os.path.exists(package_json_path):
                result["details"].append("No package.json found")
                return result

            # Determine package manager
            yarn_lock_path = os.path.join(plugin_dir, "yarn.lock")
            if os.path.exists(yarn_lock_path):
                package_manager = "yarn"
                cmd = ["yarn", "test"]
            else:
                package_manager = "npm"
                cmd = ["npm", "test"]

            if self.verbose:
                print(f"Running Node.js tests with {package_manager}")

            # Run tests
            process_result = subprocess.run(
                cmd, cwd=plugin_dir, capture_output=True, text=True
            )

            result["output"] = process_result.stdout
            result["success"] = process_result.returncode == 0

            # Try to parse test output for counts (basic parsing)
            if "test" in result["output"].lower():
                result["test_count"] = result["output"].lower().count("test")

            result["details"].append(f"Tests run with {package_manager}")

            if process_result.stderr:
                result["details"].append(f"Stderr: {process_result.stderr}")

            # Check for coverage reports (if available)
            if coverage:
                coverage_paths = [
                    os.path.join(plugin_dir, "coverage", "coverage-summary.json"),
                    os.path.join(plugin_dir, "coverage.json"),
                ]

                for coverage_path in coverage_paths:
                    if os.path.exists(coverage_path):
                        try:
                            with open(coverage_path) as f:
                                coverage_data = json.load(f)

                            # Extract coverage info (format varies by tool)
                            if "total" in coverage_data:
                                total_coverage = coverage_data["total"]
                                result["coverage"] = {
                                    "lines": total_coverage.get("lines", {}).get(
                                        "pct", 0
                                    ),
                                    "statements": total_coverage.get(
                                        "statements", {}
                                    ).get("pct", 0),
                                    "functions": total_coverage.get(
                                        "functions", {}
                                    ).get("pct", 0),
                                    "branches": total_coverage.get("branches", {}).get(
                                        "pct", 0
                                    ),
                                }

                            break

                        except (OSError, json.JSONDecodeError):
                            continue

        except FileNotFoundError:
            result["details"].append("Package manager not found")
        except Exception as e:
            result["details"].append(f"Error running Node.js tests: {e}")

        return result

    def _run_integration_tests(
        self, plugin_dir: str, plugin_config: Dict[str, Any], coverage: bool
    ) -> Dict[str, Any]:
        """Run integration tests."""
        result = {
            "success": False,
            "test_count": 0,
            "details": [],
            "output": "",
            "coverage": {},
        }

        try:
            # Look for integration test directories
            integration_dirs = []
            for test_dir in ["integration", "tests/integration", "e2e"]:
                full_path = os.path.join(plugin_dir, test_dir)
                if os.path.exists(full_path):
                    integration_dirs.append(full_path)

            if not integration_dirs:
                result["details"].append("No integration test directories found")
                return result

            # Check for custom integration test script
            test_script = plugin_config.get("testing", {}).get("integration_script")

            if test_script:
                # Run custom script
                cmd = test_script.split()

                process_result = subprocess.run(
                    cmd, cwd=plugin_dir, capture_output=True, text=True
                )

                result["output"] = process_result.stdout
                result["success"] = process_result.returncode == 0
                result["details"].append(
                    f"Ran custom integration script: {test_script}"
                )

            else:
                # Default integration test approach
                # This could be enhanced to run docker-compose based tests
                result["details"].append(
                    "Integration tests detected but no runner configured"
                )
                result["success"] = True  # Default to success if no specific runner

        except Exception as e:
            result["details"].append(f"Error running integration tests: {e}")

        return result

    def _run_lint_tests(
        self, plugin_dir: str, plugin_config: Dict[str, Any], coverage: bool
    ) -> Dict[str, Any]:
        """Run linting tests."""
        result = {
            "success": True,
            "test_count": 0,
            "details": [],
            "output": "",
            "issues": [],
        }

        try:
            src_path = os.path.join(plugin_dir, "src")
            if not os.path.exists(src_path):
                result["details"].append("No src directory found for linting")
                return result

            # Python linting with flake8
            python_files = []
            for root, _dirs, files in os.walk(src_path):
                for file in files:
                    if file.endswith(".py"):
                        python_files.append(os.path.join(root, file))

            if python_files:
                try:
                    cmd = ["flake8", "--max-line-length=100", src_path]
                    process_result = subprocess.run(
                        cmd, cwd=plugin_dir, capture_output=True, text=True
                    )

                    if process_result.returncode == 0:
                        result["details"].append("Python linting passed")
                    else:
                        result["success"] = False
                        result["details"].append("Python linting failed")
                        result["issues"].extend(process_result.stdout.split("\n"))

                    result["test_count"] += len(python_files)

                except FileNotFoundError:
                    result["details"].append(
                        "flake8 not found - skipping Python linting"
                    )

            # JavaScript/TypeScript linting with eslint
            js_files = []
            for root, _dirs, files in os.walk(src_path):
                for file in files:
                    if file.endswith((".js", ".jsx", ".ts", ".tsx")):
                        js_files.append(os.path.join(root, file))

            if js_files:
                try:
                    cmd = ["npx", "eslint", src_path]
                    process_result = subprocess.run(
                        cmd, cwd=plugin_dir, capture_output=True, text=True
                    )

                    if process_result.returncode == 0:
                        result["details"].append("JavaScript linting passed")
                    else:
                        result["success"] = False
                        result["details"].append("JavaScript linting failed")
                        result["issues"].extend(process_result.stdout.split("\n"))

                    result["test_count"] += len(js_files)

                except FileNotFoundError:
                    result["details"].append(
                        "eslint not found - skipping JavaScript linting"
                    )

            if not python_files and not js_files:
                result["details"].append("No files found for linting")

        except Exception as e:
            result["details"].append(f"Error running lint tests: {e}")
            result["success"] = False

        return result

    def _run_security_tests(
        self, plugin_dir: str, plugin_config: Dict[str, Any], coverage: bool
    ) -> Dict[str, Any]:
        """Run security tests."""
        result = {
            "success": True,
            "test_count": 0,
            "details": [],
            "output": "",
            "vulnerabilities": [],
        }

        try:
            # Python security scanning with bandit
            src_path = os.path.join(plugin_dir, "src")
            if os.path.exists(src_path):
                python_files = [f for f in os.listdir(src_path) if f.endswith(".py")]

                if python_files:
                    try:
                        cmd = ["bandit", "-r", src_path, "-f", "json"]
                        process_result = subprocess.run(
                            cmd, cwd=plugin_dir, capture_output=True, text=True
                        )

                        # Parse bandit JSON output
                        if process_result.stdout:
                            try:
                                bandit_results = json.loads(process_result.stdout)
                                vulnerabilities = bandit_results.get("results", [])

                                result["test_count"] = len(python_files)
                                result["vulnerabilities"] = vulnerabilities

                                if vulnerabilities:
                                    high_severity = [
                                        v
                                        for v in vulnerabilities
                                        if v.get("issue_severity") == "HIGH"
                                    ]
                                    if high_severity:
                                        result["success"] = False
                                        result["details"].append(
                                            f"Found {len(high_severity)} high-severity security issues"
                                        )
                                    else:
                                        result["details"].append(
                                            f"Found {len(vulnerabilities)} low/medium security issues"
                                        )
                                else:
                                    result["details"].append("No security issues found")

                            except json.JSONDecodeError:
                                result["details"].append(
                                    "Could not parse bandit output"
                                )
                        else:
                            result["details"].append("Python security scan completed")

                    except FileNotFoundError:
                        result["details"].append(
                            "bandit not found - skipping Python security scanning"
                        )

            # Node.js security scanning
            package_json_path = os.path.join(plugin_dir, "package.json")
            if os.path.exists(package_json_path):
                try:
                    cmd = ["npm", "audit", "--json"]
                    process_result = subprocess.run(
                        cmd, cwd=plugin_dir, capture_output=True, text=True
                    )

                    if process_result.stdout:
                        try:
                            audit_results = json.loads(process_result.stdout)
                            vulnerabilities = audit_results.get("vulnerabilities", {})

                            if vulnerabilities:
                                high_vuln = sum(
                                    1
                                    for v in vulnerabilities.values()
                                    if v.get("severity") in ["high", "critical"]
                                )
                                if high_vuln > 0:
                                    result["success"] = False
                                    result["details"].append(
                                        f"Found {high_vuln} high/critical npm vulnerabilities"
                                    )
                                else:
                                    result["details"].append(
                                        f"Found {len(vulnerabilities)} low/medium npm vulnerabilities"
                                    )
                            else:
                                result["details"].append("No npm vulnerabilities found")

                        except json.JSONDecodeError:
                            result["details"].append("Could not parse npm audit output")

                except FileNotFoundError:
                    result["details"].append(
                        "npm not found - skipping Node.js security scanning"
                    )

        except Exception as e:
            result["details"].append(f"Error running security tests: {e}")
            result["success"] = False

        return result

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

    def _print_test_summary(self, results: Dict[str, Any]) -> None:
        """Print a formatted test summary."""
        print(f"\n=== Test Summary for {results['plugin_name']} ===")
        print(f"Overall Success: {'✓' if results['overall_success'] else '✗'}")
        print(f"Execution Time: {results['execution_time']:.2f}s")
        print(f"Total Tests: {results['summary']['total_tests']}")
        print(f"Passed: {results['summary']['passed']}")
        print(f"Failed: {results['summary']['failed']}")
        print(f"Errors: {results['summary']['errors']}")

        print("\n=== Test Type Results ===")
        for test_type, result in results["results"].items():
            status = "✓" if result.get("success", False) else "✗"
            count = result.get("test_count", 0)
            print(f"{status} {test_type}: {count} tests")

            if not result.get("success", False) and "details" in result:
                for detail in result["details"][:3]:  # Show first 3 details
                    print(f"    - {detail}")

        # Show coverage summary if available
        if results.get("coverage"):
            print("\n=== Coverage Summary ===")
            for test_type, coverage in results["coverage"].items():
                if isinstance(coverage, dict) and "percent_covered" in coverage:
                    print(f"{test_type}: {coverage['percent_covered']:.1f}%")

    def generate_test_report(
        self, results: Dict[str, Any], format: str = "text"
    ) -> str:
        """
        Generate a formatted test report.

        Args:
            results: Test results from run_plugin_tests
            format: Report format (text, json, html)

        Returns:
            str: Formatted test report
        """
        if format == "json":
            return json.dumps(results, indent=2)

        elif format == "html":
            # Basic HTML report
            html_lines = [
                "<html><head><title>Plugin Test Report</title></head><body>",
                f"<h1>Test Report for {results['plugin_name']}</h1>",
                f"<p><strong>Overall Success:</strong> {'✓' if results['overall_success'] else '✗'}</p>",
                f"<p><strong>Execution Time:</strong> {results['execution_time']:.2f}s</p>",
                "<h2>Summary</h2>",
                "<ul>",
                f"<li>Total Tests: {results['summary']['total_tests']}</li>",
                f"<li>Passed: {results['summary']['passed']}</li>",
                f"<li>Failed: {results['summary']['failed']}</li>",
                f"<li>Errors: {results['summary']['errors']}</li>",
                "</ul>",
                "<h2>Test Results</h2>",
            ]

            for test_type, result in results["results"].items():
                status = "✓" if result.get("success", False) else "✗"
                html_lines.extend(
                    [
                        f"<h3>{status} {test_type}</h3>",
                        f"<p>Tests: {result.get('test_count', 0)}</p>",
                        "<ul>",
                    ]
                )

                for detail in result.get("details", []):
                    html_lines.append(f"<li>{detail}</li>")

                html_lines.append("</ul>")

            html_lines.append("</body></html>")
            return "\n".join(html_lines)

        else:  # text format
            lines = [
                f"Plugin Test Report: {results['plugin_name']}",
                "=" * 50,
                f"Overall Success: {'✓' if results['overall_success'] else '✗'}",
                f"Execution Time: {results['execution_time']:.2f}s",
                "",
                "Summary:",
                f"  Total Tests: {results['summary']['total_tests']}",
                f"  Passed: {results['summary']['passed']}",
                f"  Failed: {results['summary']['failed']}",
                f"  Errors: {results['summary']['errors']}",
                "",
                "Test Results:",
            ]

            for test_type, result in results["results"].items():
                status = "✓" if result.get("success", False) else "✗"
                lines.append(
                    f"  {status} {test_type}: {result.get('test_count', 0)} tests"
                )

                for detail in result.get("details", []):
                    lines.append(f"    - {detail}")

                lines.append("")

            # Add coverage information
            if results.get("coverage"):
                lines.extend(["Coverage:", ""])

                for test_type, coverage in results["coverage"].items():
                    if isinstance(coverage, dict):
                        lines.append(f"  {test_type}:")
                        for metric, value in coverage.items():
                            lines.append(f"    {metric}: {value}")
                        lines.append("")

            return "\n".join(lines)
