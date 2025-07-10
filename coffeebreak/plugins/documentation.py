"""Plugin documentation generation for CoffeeBreak CLI."""

import os
import re
import ast
import json
import tempfile
from typing import Dict, Any, List, Optional, Set
from pathlib import Path

from ..utils.errors import PluginError


class PluginDocumentationGenerator:
    """Generates comprehensive documentation for CoffeeBreak plugins."""

    def __init__(self, verbose: bool = False):
        """Initialize documentation generator."""
        self.verbose = verbose
        self.extractors = {
            "python": self._extract_python_docs,
            "javascript": self._extract_javascript_docs,
            "typescript": self._extract_typescript_docs,
            "markdown": self._extract_markdown_docs,
        }

    def generate_plugin_documentation(
        self,
        plugin_dir: str = ".",
        output_dir: str = "docs",
        formats: Optional[List[str]] = None,
        include_api: bool = True,
        include_examples: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive documentation for a plugin.

        Args:
            plugin_dir: Plugin directory to document
            output_dir: Output directory for documentation
            formats: Documentation formats to generate (markdown, html, json)
            include_api: Whether to include API documentation
            include_examples: Whether to include usage examples

        Returns:
            Dict[str, Any]: Documentation generation results
        """
        try:
            plugin_dir = os.path.abspath(plugin_dir)
            output_dir = os.path.join(plugin_dir, output_dir)

            if self.verbose:
                print(f"Generating documentation for plugin at {plugin_dir}")

            # Validate plugin directory
            if not self._is_valid_plugin_directory(plugin_dir):
                raise PluginError(f"Invalid plugin directory: {plugin_dir}")

            # Load plugin configuration
            plugin_config = self._load_plugin_config(plugin_dir)
            plugin_name = plugin_config["plugin"]["name"]

            # Set default formats
            if formats is None:
                formats = ["markdown", "html"]

            if self.verbose:
                print(f"Generating formats: {formats}")

            # Create output directory
            os.makedirs(output_dir, exist_ok=True)

            # Extract documentation from source files
            documentation_data = self._extract_documentation_data(
                plugin_dir, plugin_config
            )

            # Generate API documentation if requested
            if include_api:
                documentation_data["api"] = self._generate_api_documentation(
                    plugin_dir, plugin_config
                )

            # Generate usage examples if requested
            if include_examples:
                documentation_data["examples"] = self._generate_usage_examples(
                    plugin_dir, plugin_config
                )

            # Generate documentation in requested formats
            results = {
                "plugin_name": plugin_name,
                "plugin_dir": plugin_dir,
                "output_dir": output_dir,
                "formats": formats,
                "generated_files": [],
                "errors": [],
                "warnings": [],
            }

            for format_type in formats:
                try:
                    if format_type == "markdown":
                        file_path = self._generate_markdown_docs(
                            documentation_data, output_dir
                        )
                        results["generated_files"].append(file_path)

                    elif format_type == "html":
                        file_path = self._generate_html_docs(
                            documentation_data, output_dir
                        )
                        results["generated_files"].append(file_path)

                    elif format_type == "json":
                        file_path = self._generate_json_docs(
                            documentation_data, output_dir
                        )
                        results["generated_files"].append(file_path)

                    else:
                        results["warnings"].append(
                            f"Unknown documentation format: {format_type}"
                        )

                except Exception as e:
                    results["errors"].append(
                        f"Failed to generate {format_type} documentation: {e}"
                    )

            if self.verbose:
                print(
                    f"Documentation generation completed. Files: {len(results['generated_files'])}"
                )

            return results

        except Exception as e:
            raise PluginError(f"Failed to generate plugin documentation: {e}")

    def _extract_documentation_data(
        self, plugin_dir: str, plugin_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract all documentation data from plugin sources."""
        documentation_data = {
            "plugin": plugin_config["plugin"],
            "overview": self._extract_overview(plugin_dir, plugin_config),
            "installation": self._extract_installation_info(plugin_dir, plugin_config),
            "configuration": self._extract_configuration_info(
                plugin_dir, plugin_config
            ),
            "source_docs": {},
            "files": {},
            "dependencies": self._extract_dependency_info(plugin_dir, plugin_config),
        }

        # Extract documentation from source files
        src_path = os.path.join(plugin_dir, "src")
        if os.path.exists(src_path):
            for root, dirs, files in os.walk(src_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, plugin_dir)

                    # Determine file type and extract documentation
                    file_ext = os.path.splitext(file)[1].lower()

                    if file_ext == ".py":
                        docs = self._extract_python_docs(file_path)
                        documentation_data["source_docs"][relative_path] = docs

                    elif file_ext in [".js", ".jsx"]:
                        docs = self._extract_javascript_docs(file_path)
                        documentation_data["source_docs"][relative_path] = docs

                    elif file_ext in [".ts", ".tsx"]:
                        docs = self._extract_typescript_docs(file_path)
                        documentation_data["source_docs"][relative_path] = docs

                    elif file_ext == ".md":
                        docs = self._extract_markdown_docs(file_path)
                        documentation_data["source_docs"][relative_path] = docs

        # Extract documentation from additional files
        doc_files = ["README.md", "USAGE.md", "EXAMPLES.md", "CHANGELOG.md"]
        for doc_file in doc_files:
            file_path = os.path.join(plugin_dir, doc_file)
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    documentation_data["files"][doc_file] = f.read()

        return documentation_data

    def _extract_overview(
        self, plugin_dir: str, plugin_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract plugin overview information."""
        plugin_info = plugin_config["plugin"]

        overview = {
            "name": plugin_info["name"],
            "version": plugin_info["version"],
            "description": plugin_info.get("description", ""),
            "author": plugin_info.get("author", ""),
            "license": plugin_info.get("license", ""),
            "keywords": plugin_info.get("keywords", []),
            "homepage": plugin_info.get("homepage", ""),
            "repository": plugin_info.get("repository", ""),
        }

        # Try to extract description from README if not in config
        if not overview["description"]:
            readme_path = os.path.join(plugin_dir, "README.md")
            if os.path.exists(readme_path):
                with open(readme_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Extract first paragraph as description
                    lines = content.split("\n")
                    for line in lines:
                        line = line.strip()
                        if (
                            line
                            and not line.startswith("#")
                            and not line.startswith("!")
                        ):
                            overview["description"] = line
                            break

        return overview

    def _extract_installation_info(
        self, plugin_dir: str, plugin_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract installation and setup information."""
        installation = {
            "requirements": [],
            "installation_steps": [],
            "dependencies": {},
        }

        # Check for requirements.txt
        requirements_path = os.path.join(plugin_dir, "requirements.txt")
        if os.path.exists(requirements_path):
            with open(requirements_path, "r") as f:
                installation["requirements"] = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.startswith("#")
                ]

        # Check for package.json
        package_json_path = os.path.join(plugin_dir, "package.json")
        if os.path.exists(package_json_path):
            try:
                with open(package_json_path, "r") as f:
                    package_data = json.load(f)
                installation["dependencies"]["node"] = {
                    "dependencies": package_data.get("dependencies", {}),
                    "devDependencies": package_data.get("devDependencies", {}),
                }
            except (json.JSONDecodeError, IOError):
                pass

        # Extract installation steps from config
        setup_config = plugin_config.get("setup", {})
        installation["installation_steps"] = setup_config.get("steps", [])

        return installation

    def _extract_configuration_info(
        self, plugin_dir: str, plugin_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract configuration information."""
        configuration = {
            "config_schema": plugin_config.get("config", {}),
            "default_config": {},
            "environment_variables": plugin_config.get("environment", {}),
            "examples": [],
        }

        # Look for configuration examples
        config_examples_path = os.path.join(plugin_dir, "config")
        if os.path.exists(config_examples_path):
            for file in os.listdir(config_examples_path):
                if file.endswith((".yml", ".yaml", ".json")):
                    file_path = os.path.join(config_examples_path, file)
                    try:
                        with open(file_path, "r") as f:
                            if file.endswith(".json"):
                                content = json.load(f)
                            else:
                                from ..config.manager import ConfigManager

                                config_manager = ConfigManager()
                                content = config_manager.load_config_file(file_path)

                            configuration["examples"].append(
                                {
                                    "name": file,
                                    "description": f"Example configuration: {file}",
                                    "content": content,
                                }
                            )
                    except Exception:
                        pass

        return configuration

    def _extract_dependency_info(
        self, plugin_dir: str, plugin_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract dependency information."""
        dependencies = plugin_config.get("dependencies", {})

        dependency_info = {
            "python": dependencies.get("python", {}),
            "node": dependencies.get("node", {}),
            "services": dependencies.get("services", []),
            "system": dependencies.get("system", {}),
            "optional": dependencies.get("optional", []),
        }

        return dependency_info

    def _extract_python_docs(self, file_path: str) -> Dict[str, Any]:
        """Extract documentation from Python files."""
        docs = {
            "file_type": "python",
            "module_doc": "",
            "classes": [],
            "functions": [],
            "constants": [],
        }

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse AST
            tree = ast.parse(content)

            # Extract module docstring
            if isinstance(tree.body[0], ast.Expr) and isinstance(
                tree.body[0].value, ast.Str
            ):
                docs["module_doc"] = tree.body[0].value.s

            # Extract classes and functions
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_doc = {
                        "name": node.name,
                        "docstring": ast.get_docstring(node) or "",
                        "methods": [],
                        "line_number": node.lineno,
                    }

                    # Extract methods
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_doc = {
                                "name": item.name,
                                "docstring": ast.get_docstring(item) or "",
                                "args": [arg.arg for arg in item.args.args],
                                "line_number": item.lineno,
                            }
                            class_doc["methods"].append(method_doc)

                    docs["classes"].append(class_doc)

                elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
                    # Top-level functions only
                    func_doc = {
                        "name": node.name,
                        "docstring": ast.get_docstring(node) or "",
                        "args": [arg.arg for arg in node.args.args],
                        "line_number": node.lineno,
                    }
                    docs["functions"].append(func_doc)

                elif isinstance(node, ast.Assign):
                    # Extract constants (uppercase variables)
                    for target in node.targets:
                        if (
                            isinstance(target, ast.Name)
                            and target.id.isupper()
                            and node.col_offset == 0
                        ):
                            constant_doc = {
                                "name": target.id,
                                "line_number": node.lineno,
                            }
                            docs["constants"].append(constant_doc)

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not parse Python file {file_path}: {e}")

        return docs

    def _extract_javascript_docs(self, file_path: str) -> Dict[str, Any]:
        """Extract documentation from JavaScript files."""
        docs = {
            "file_type": "javascript",
            "module_doc": "",
            "functions": [],
            "classes": [],
            "exports": [],
        }

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Simple regex-based extraction (could be enhanced with proper JS parser)

            # Extract JSDoc comments
            jsdoc_pattern = r"/\*\*\s*(.*?)\s*\*/"
            jsdoc_matches = re.findall(jsdoc_pattern, content, re.DOTALL)

            # Extract function declarations
            func_pattern = r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:function|\(.*?\)\s*=>))"
            func_matches = re.findall(func_pattern, content)

            for match in func_matches:
                func_name = match[0] or match[1]
                func_doc = {"name": func_name, "docstring": "", "type": "function"}
                docs["functions"].append(func_doc)

            # Extract class declarations
            class_pattern = r"class\s+(\w+)"
            class_matches = re.findall(class_pattern, content)

            for class_name in class_matches:
                class_doc = {"name": class_name, "docstring": "", "type": "class"}
                docs["classes"].append(class_doc)

            # Extract exports
            export_pattern = r"export\s+(?:default\s+)?(?:function\s+(\w+)|class\s+(\w+)|(?:const|let|var)\s+(\w+))"
            export_matches = re.findall(export_pattern, content)

            for match in export_matches:
                export_name = match[0] or match[1] or match[2]
                docs["exports"].append(export_name)

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not parse JavaScript file {file_path}: {e}")

        return docs

    def _extract_typescript_docs(self, file_path: str) -> Dict[str, Any]:
        """Extract documentation from TypeScript files."""
        # Similar to JavaScript but could extract type information
        docs = self._extract_javascript_docs(file_path)
        docs["file_type"] = "typescript"

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract interface definitions
            interface_pattern = r"interface\s+(\w+)"
            interface_matches = re.findall(interface_pattern, content)

            docs["interfaces"] = []
            for interface_name in interface_matches:
                interface_doc = {"name": interface_name, "type": "interface"}
                docs["interfaces"].append(interface_doc)

            # Extract type definitions
            type_pattern = r"type\s+(\w+)"
            type_matches = re.findall(type_pattern, content)

            docs["types"] = []
            for type_name in type_matches:
                type_doc = {"name": type_name, "type": "type_alias"}
                docs["types"].append(type_doc)

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not parse TypeScript file {file_path}: {e}")

        return docs

    def _extract_markdown_docs(self, file_path: str) -> Dict[str, Any]:
        """Extract structure from Markdown files."""
        docs = {
            "file_type": "markdown",
            "content": "",
            "headings": [],
            "links": [],
            "code_blocks": [],
        }

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                docs["content"] = content

            # Extract headings
            heading_pattern = r"^(#{1,6})\s+(.+)$"
            for match in re.finditer(heading_pattern, content, re.MULTILINE):
                level = len(match.group(1))
                text = match.group(2)
                docs["headings"].append(
                    {
                        "level": level,
                        "text": text,
                        "line": content[: match.start()].count("\n") + 1,
                    }
                )

            # Extract links
            link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
            for match in re.finditer(link_pattern, content):
                docs["links"].append({"text": match.group(1), "url": match.group(2)})

            # Extract code blocks
            code_pattern = r"```(\w+)?\n(.*?)\n```"
            for match in re.finditer(code_pattern, content, re.DOTALL):
                docs["code_blocks"].append(
                    {"language": match.group(1) or "text", "code": match.group(2)}
                )

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not parse Markdown file {file_path}: {e}")

        return docs

    def _generate_api_documentation(
        self, plugin_dir: str, plugin_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate API documentation."""
        api_docs = {"endpoints": [], "events": [], "hooks": [], "configuration": {}}

        # Look for API specification files
        api_spec_paths = [
            os.path.join(plugin_dir, "api.yml"),
            os.path.join(plugin_dir, "api.yaml"),
            os.path.join(plugin_dir, "openapi.yml"),
            os.path.join(plugin_dir, "swagger.yml"),
        ]

        for spec_path in api_spec_paths:
            if os.path.exists(spec_path):
                try:
                    from ..config.manager import ConfigManager

                    config_manager = ConfigManager()
                    api_spec = config_manager.load_config_file(spec_path)

                    # Extract endpoints from OpenAPI/Swagger spec
                    if "paths" in api_spec:
                        for path, methods in api_spec["paths"].items():
                            for method, spec in methods.items():
                                endpoint = {
                                    "path": path,
                                    "method": method.upper(),
                                    "summary": spec.get("summary", ""),
                                    "description": spec.get("description", ""),
                                    "parameters": spec.get("parameters", []),
                                    "responses": spec.get("responses", {}),
                                }
                                api_docs["endpoints"].append(endpoint)

                    break
                except Exception:
                    continue

        # Extract API info from plugin configuration
        api_config = plugin_config.get("api", {})
        if api_config:
            api_docs["configuration"] = api_config

        return api_docs

    def _generate_usage_examples(
        self, plugin_dir: str, plugin_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate usage examples."""
        examples = {
            "basic_usage": [],
            "advanced_usage": [],
            "code_examples": [],
            "configuration_examples": [],
        }

        # Look for examples directory
        examples_dir = os.path.join(plugin_dir, "examples")
        if os.path.exists(examples_dir):
            for file in os.listdir(examples_dir):
                file_path = os.path.join(examples_dir, file)
                if os.path.isfile(file_path):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()

                        example = {
                            "name": file,
                            "description": f"Example from {file}",
                            "content": content,
                            "language": self._detect_language_from_extension(file),
                        }

                        if "basic" in file.lower():
                            examples["basic_usage"].append(example)
                        elif "advanced" in file.lower():
                            examples["advanced_usage"].append(example)
                        else:
                            examples["code_examples"].append(example)

                    except Exception:
                        continue

        # Extract examples from configuration
        config_examples = plugin_config.get("examples", [])
        for example in config_examples:
            if isinstance(example, dict):
                examples["configuration_examples"].append(example)

        return examples

    def _generate_markdown_docs(
        self, documentation_data: Dict[str, Any], output_dir: str
    ) -> str:
        """Generate Markdown documentation."""
        plugin_info = documentation_data["plugin"]
        overview = documentation_data["overview"]

        md_lines = [
            f"# {plugin_info['name']}",
            "",
            f"Version: {plugin_info['version']}",
            "",
            f"{overview.get('description', 'No description available')}",
            "",
        ]

        # Add author and license if available
        if overview.get("author"):
            md_lines.extend([f"**Author:** {overview['author']}", ""])

        if overview.get("license"):
            md_lines.extend([f"**License:** {overview['license']}", ""])

        # Table of Contents
        md_lines.extend(
            [
                "## Table of Contents",
                "",
                "- [Installation](#installation)",
                "- [Configuration](#configuration)",
                "- [API Reference](#api-reference)",
                "- [Examples](#examples)",
                "- [Dependencies](#dependencies)",
                "",
            ]
        )

        # Installation section
        installation = documentation_data["installation"]
        md_lines.extend(["## Installation", "", "### Requirements", ""])

        if installation["requirements"]:
            for req in installation["requirements"]:
                md_lines.append(f"- {req}")
            md_lines.append("")
        else:
            md_lines.extend(["No specific requirements.", ""])

        # Configuration section
        configuration = documentation_data["configuration"]
        md_lines.extend(["## Configuration", "", "### Configuration Schema", ""])

        if configuration["config_schema"]:
            md_lines.append("```yaml")
            import yaml

            md_lines.append(
                yaml.dump(configuration["config_schema"], default_flow_style=False)
            )
            md_lines.extend(["```", ""])
        else:
            md_lines.extend(["No configuration schema available.", ""])

        # API Reference section
        if "api" in documentation_data:
            api_docs = documentation_data["api"]
            md_lines.extend(["## API Reference", ""])

            if api_docs["endpoints"]:
                md_lines.extend(["### Endpoints", ""])
                for endpoint in api_docs["endpoints"]:
                    md_lines.extend(
                        [
                            f"#### {endpoint['method']} {endpoint['path']}",
                            "",
                            endpoint.get("description", "No description"),
                            "",
                        ]
                    )

        # Examples section
        if "examples" in documentation_data:
            examples = documentation_data["examples"]
            md_lines.extend(["## Examples", ""])

            # Basic usage examples
            if examples["basic_usage"]:
                md_lines.extend(["### Basic Usage", ""])
                for example in examples["basic_usage"]:
                    md_lines.extend(
                        [
                            f"#### {example['name']}",
                            "",
                            f"```{example.get('language', 'text')}",
                            example["content"],
                            "```",
                            "",
                        ]
                    )

        # Dependencies section
        dependencies = documentation_data["dependencies"]
        md_lines.extend(["## Dependencies", ""])

        if dependencies["services"]:
            md_lines.extend(["### Required Services", ""])
            for service in dependencies["services"]:
                md_lines.append(f"- {service}")
            md_lines.append("")

        # Source code documentation
        if documentation_data["source_docs"]:
            md_lines.extend(["## Source Code Documentation", ""])

            for file_path, docs in documentation_data["source_docs"].items():
                md_lines.extend([f"### {file_path}", ""])

                if docs.get("module_doc"):
                    md_lines.extend([docs["module_doc"], ""])

                # Classes
                if docs.get("classes"):
                    md_lines.extend(["#### Classes", ""])
                    for cls in docs["classes"]:
                        md_lines.extend(
                            [
                                f"##### {cls['name']}",
                                "",
                                cls.get("docstring", "No documentation"),
                                "",
                            ]
                        )

                # Functions
                if docs.get("functions"):
                    md_lines.extend(["#### Functions", ""])
                    for func in docs["functions"]:
                        args_str = ", ".join(func.get("args", []))
                        md_lines.extend(
                            [
                                f"##### {func['name']}({args_str})",
                                "",
                                func.get("docstring", "No documentation"),
                                "",
                            ]
                        )

        # Write to file
        output_file = os.path.join(output_dir, "README.md")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        return output_file

    def _generate_html_docs(
        self, documentation_data: Dict[str, Any], output_dir: str
    ) -> str:
        """Generate HTML documentation."""
        plugin_info = documentation_data["plugin"]
        overview = documentation_data["overview"]

        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{plugin_info["name"]} Documentation</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }}
        .section {{ margin-bottom: 30px; }}
        .code {{ background-color: #f4f4f4; padding: 10px; border-radius: 5px; font-family: monospace; }}
        .toc {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; }}
        .toc ul {{ list-style-type: none; padding-left: 20px; }}
        .api-endpoint {{ border: 1px solid #ddd; padding: 10px; margin: 10px 0; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{plugin_info["name"]}</h1>
        <p>Version: {plugin_info["version"]}</p>
        <p>{overview.get("description", "No description available")}</p>
    </div>
    
    <div class="toc">
        <h2>Table of Contents</h2>
        <ul>
            <li><a href="#installation">Installation</a></li>
            <li><a href="#configuration">Configuration</a></li>
            <li><a href="#api">API Reference</a></li>
            <li><a href="#examples">Examples</a></li>
            <li><a href="#dependencies">Dependencies</a></li>
        </ul>
    </div>
"""

        # Installation section
        installation = documentation_data["installation"]
        html_content += f"""
    <div class="section" id="installation">
        <h2>Installation</h2>
        <h3>Requirements</h3>
        <ul>
"""

        for req in installation.get("requirements", ["No specific requirements"]):
            html_content += f"            <li>{req}</li>\n"

        html_content += """
        </ul>
    </div>
"""

        # Configuration section
        configuration = documentation_data["configuration"]
        html_content += f"""
    <div class="section" id="configuration">
        <h2>Configuration</h2>
        <h3>Configuration Schema</h3>
"""

        if configuration["config_schema"]:
            import yaml

            config_yaml = yaml.dump(
                configuration["config_schema"], default_flow_style=False
            )
            html_content += (
                f'        <div class="code"><pre>{config_yaml}</pre></div>\n'
            )
        else:
            html_content += "        <p>No configuration schema available.</p>\n"

        html_content += "    </div>\n"

        # API section
        if "api" in documentation_data:
            api_docs = documentation_data["api"]
            html_content += """
    <div class="section" id="api">
        <h2>API Reference</h2>
"""

            for endpoint in api_docs.get("endpoints", []):
                html_content += f"""
        <div class="api-endpoint">
            <h3>{endpoint["method"]} {endpoint["path"]}</h3>
            <p>{endpoint.get("description", "No description")}</p>
        </div>
"""

            html_content += "    </div>\n"

        # Examples section
        if "examples" in documentation_data:
            examples = documentation_data["examples"]
            html_content += """
    <div class="section" id="examples">
        <h2>Examples</h2>
"""

            for example in examples.get("basic_usage", []):
                html_content += f"""
        <h3>{example["name"]}</h3>
        <div class="code"><pre>{example["content"]}</pre></div>
"""

            html_content += "    </div>\n"

        # Dependencies section
        dependencies = documentation_data["dependencies"]
        html_content += """
    <div class="section" id="dependencies">
        <h2>Dependencies</h2>
        <h3>Required Services</h3>
        <ul>
"""

        for service in dependencies.get("services", ["No service dependencies"]):
            html_content += f"            <li>{service}</li>\n"

        html_content += """
        </ul>
    </div>
</body>
</html>
"""

        # Write to file
        output_file = os.path.join(output_dir, "index.html")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_file

    def _generate_json_docs(
        self, documentation_data: Dict[str, Any], output_dir: str
    ) -> str:
        """Generate JSON documentation."""
        output_file = os.path.join(output_dir, "documentation.json")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(documentation_data, f, indent=2, ensure_ascii=False)

        return output_file

    def _is_valid_plugin_directory(self, plugin_dir: str) -> bool:
        """Check if directory is a valid plugin."""
        manifest_path = os.path.join(plugin_dir, "coffeebreak-plugin.yml")
        return os.path.exists(manifest_path)

    def _load_plugin_config(self, plugin_dir: str) -> Dict[str, Any]:
        """Load plugin configuration."""
        config_path = os.path.join(plugin_dir, "coffeebreak-plugin.yml")
        from ..config.manager import ConfigManager

        config_manager = ConfigManager()
        return config_manager.load_config_file(config_path)

    def _detect_language_from_extension(self, filename: str) -> str:
        """Detect programming language from file extension."""
        ext = os.path.splitext(filename)[1].lower()

        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".json": "json",
            ".md": "markdown",
            ".sh": "bash",
            ".dockerfile": "dockerfile",
        }

        return language_map.get(ext, "text")
