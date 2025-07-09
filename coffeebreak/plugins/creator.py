"""Plugin creation and scaffolding for CoffeeBreak CLI."""

import os
import shutil
import tempfile
from typing import Dict, Any, List, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from ..utils.files import FileManager
from ..utils.errors import PluginError, CoffeeBreakError
from ..config.manager import ConfigManager


class PluginCreator:
    """Creates new plugins from templates."""
    
    def __init__(self, verbose: bool = False):
        """Initialize plugin creator."""
        self.verbose = verbose
        self.file_manager = FileManager(verbose=verbose)
        self.config_manager = ConfigManager()
        
        # Setup Jinja2 environment
        templates_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def create_plugin(self, 
                     name: str, 
                     template: str = "basic",
                     target_dir: Optional[str] = None,
                     **kwargs) -> str:
        """
        Create a new plugin from template.
        
        Args:
            name: Plugin name
            template: Template to use (default: basic)
            target_dir: Target directory (default: current directory)
            **kwargs: Additional template variables
            
        Returns:
            str: Path to created plugin directory
            
        Raises:
            PluginError: If plugin creation fails
        """
        try:
            if self.verbose:
                print(f"Creating plugin '{name}' using template '{template}'")
            
            # Validate plugin name
            self._validate_plugin_name(name)
            
            # Determine target directory
            if target_dir is None:
                target_dir = os.getcwd()
            
            plugin_dir = os.path.join(target_dir, name)
            
            # Check if plugin directory already exists
            if os.path.exists(plugin_dir):
                raise PluginError(f"Plugin directory '{plugin_dir}' already exists")
            
            # Create plugin directory structure
            self._create_plugin_structure(name, template, plugin_dir, **kwargs)
            
            # Generate plugin manifest
            self._generate_plugin_manifest(name, plugin_dir, **kwargs)
            
            # Create build scripts
            self._create_build_scripts(plugin_dir)
            
            # Create initial plugin files
            self._create_plugin_files(name, plugin_dir, **kwargs)
            
            if self.verbose:
                print(f"Plugin '{name}' created successfully at {plugin_dir}")
            
            return plugin_dir
            
        except Exception as e:
            if isinstance(e, CoffeeBreakError):
                raise
            else:
                raise PluginError(f"Failed to create plugin '{name}': {e}")
    
    def _validate_plugin_name(self, name: str) -> None:
        """Validate plugin name format."""
        if not name:
            raise PluginError("Plugin name cannot be empty")
        
        if not name.replace("-", "_").replace("_", "").isalnum():
            raise PluginError("Plugin name must contain only letters, numbers, hyphens, and underscores")
        
        if name.startswith("-") or name.endswith("-"):
            raise PluginError("Plugin name cannot start or end with hyphens")
        
        if len(name) > 50:
            raise PluginError("Plugin name must be 50 characters or less")
    
    def _create_plugin_structure(self, 
                                name: str, 
                                template: str, 
                                plugin_dir: str,
                                **kwargs) -> None:
        """Create the basic plugin directory structure."""
        try:
            # Create main plugin directory
            os.makedirs(plugin_dir, exist_ok=True)
            
            # Create standard plugin directories
            directories = [
                "src",
                "scripts", 
                "assets",
                "tests",
                "docs"
            ]
            
            for directory in directories:
                dir_path = os.path.join(plugin_dir, directory)
                os.makedirs(dir_path, exist_ok=True)
                
                if self.verbose:
                    print(f"Created directory: {directory}")
            
            # Copy template files if template exists
            template_dir = Path(__file__).parent / "templates" / template
            if template_dir.exists():
                self._copy_template_files(template_dir, plugin_dir, name, **kwargs)
            
        except Exception as e:
            raise PluginError(f"Failed to create plugin structure: {e}")
    
    def _copy_template_files(self, 
                           template_dir: Path, 
                           plugin_dir: str, 
                           name: str,
                           **kwargs) -> None:
        """Copy and process template files."""
        template_vars = {
            "plugin_name": name,
            "plugin_package_name": name.replace("-", "_"),
            "plugin_class_name": name.replace("-", "_").title(),
            **kwargs
        }
        
        for root, dirs, files in os.walk(template_dir):
            # Calculate relative path from template root
            rel_path = os.path.relpath(root, template_dir)
            
            # Skip template root itself
            if rel_path == ".":
                continue
            
            # Create corresponding directory in plugin
            target_dir = os.path.join(plugin_dir, rel_path)
            os.makedirs(target_dir, exist_ok=True)
            
            # Copy and process files
            for file in files:
                src_file = os.path.join(root, file)
                dst_file = os.path.join(target_dir, file)
                
                # Process template files
                if file.endswith(('.j2', '.jinja2')):
                    # Remove template extension
                    dst_file = dst_file.replace('.j2', '').replace('.jinja2', '')
                    self._process_template_file(src_file, dst_file, template_vars)
                else:
                    # Copy file as-is
                    shutil.copy2(src_file, dst_file)
                
                if self.verbose:
                    print(f"Created file: {os.path.relpath(dst_file, plugin_dir)}")
    
    def _process_template_file(self, src_file: str, dst_file: str, variables: Dict[str, Any]) -> None:
        """Process a Jinja2 template file."""
        try:
            with open(src_file, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            template = self.jinja_env.from_string(template_content)
            rendered_content = template.render(**variables)
            
            with open(dst_file, 'w', encoding='utf-8') as f:
                f.write(rendered_content)
                
        except Exception as e:
            raise PluginError(f"Failed to process template file {src_file}: {e}")
    
    def _generate_plugin_manifest(self, name: str, plugin_dir: str, **kwargs) -> None:
        """Generate coffeebreak-plugin.yml manifest file."""
        try:
            manifest_template = self.jinja_env.get_template("../coffeebreak-plugin.yml.j2")
            
            template_vars = {
                "plugin_name": name,
                "plugin_package_name": name.replace("-", "_"),
                "plugin_description": kwargs.get("description", f"CoffeeBreak plugin: {name}"),
                "plugin_version": kwargs.get("version", "1.0.0"),
                "plugin_author": kwargs.get("author", "Unknown"),
                "plugin_email": kwargs.get("email", ""),
                **kwargs
            }
            
            manifest_content = manifest_template.render(**template_vars)
            manifest_path = os.path.join(plugin_dir, "coffeebreak-plugin.yml")
            
            with open(manifest_path, 'w', encoding='utf-8') as f:
                f.write(manifest_content)
            
            if self.verbose:
                print("Created plugin manifest: coffeebreak-plugin.yml")
                
        except Exception as e:
            raise PluginError(f"Failed to generate plugin manifest: {e}")
    
    def _create_build_scripts(self, plugin_dir: str) -> None:
        """Create build scripts for the plugin."""
        scripts_dir = os.path.join(plugin_dir, "scripts")
        
        # Build script
        build_script = os.path.join(scripts_dir, "build.sh")
        build_content = """#!/bin/bash
# Plugin build script
set -e

echo "Building plugin..."

# Install dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt --target ./build/
fi

# Run any custom build steps here

echo "Build completed successfully!"
"""
        self._write_executable_script(build_script, build_content)
        
        # Package script  
        package_script = os.path.join(scripts_dir, "package.sh")
        package_content = """#!/bin/bash
# Plugin packaging script
set -e

echo "Packaging plugin..."

# Create package using coffeebreak CLI
coffeebreak plugin build

echo "Packaging completed successfully!"
"""
        self._write_executable_script(package_script, package_content)
        
        # Test script
        test_script = os.path.join(scripts_dir, "test.sh")
        test_content = """#!/bin/bash
# Plugin test script
set -e

echo "Running plugin tests..."

# Run Python tests if they exist
if [ -d "tests" ]; then
    python -m pytest tests/ -v
fi

echo "Tests completed successfully!"
"""
        self._write_executable_script(test_script, test_content)
        
        # Validation script
        validate_script = os.path.join(scripts_dir, "validate.sh")
        validate_content = """#!/bin/bash
# Plugin validation script
set -e

echo "Validating plugin..."

# Validate plugin manifest
coffeebreak plugin validate

# Run linting if available
if command -v flake8 >/dev/null 2>&1; then
    echo "Running Python linting..."
    flake8 src/ --max-line-length=100
fi

echo "Validation completed successfully!"
"""
        self._write_executable_script(validate_script, validate_content)
        
        if self.verbose:
            print("Created build scripts: build.sh, package.sh, test.sh, validate.sh")
    
    def _write_executable_script(self, script_path: str, content: str) -> None:
        """Write an executable script file."""
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Make script executable
        os.chmod(script_path, 0o755)
    
    def _create_plugin_files(self, name: str, plugin_dir: str, **kwargs) -> None:
        """Create initial plugin source files."""
        src_dir = os.path.join(plugin_dir, "src")
        package_name = name.replace("-", "_")
        
        # Create __init__.py
        init_file = os.path.join(src_dir, "__init__.py")
        init_content = f'''"""
{name} - CoffeeBreak Plugin

{kwargs.get("description", f"A CoffeeBreak plugin for {name}")}
"""

__version__ = "{kwargs.get("version", "1.0.0")}"
__author__ = "{kwargs.get("author", "Unknown")}"

# Plugin entry point
def main():
    """Main plugin entry point."""
    print(f"Hello from {name} plugin!")

if __name__ == "__main__":
    main()
'''
        with open(init_file, 'w', encoding='utf-8') as f:
            f.write(init_content)
        
        # Create main plugin module
        main_file = os.path.join(src_dir, f"{package_name}.py")
        main_content = f'''"""
Main module for {name} plugin.
"""

class {name.replace("-", "_").title()}Plugin:
    """Main plugin class."""
    
    def __init__(self):
        self.name = "{name}"
        self.version = "{kwargs.get("version", "1.0.0")}"
    
    def initialize(self):
        """Initialize the plugin."""
        print(f"Initializing {{self.name}} plugin v{{self.version}}")
    
    def execute(self):
        """Execute plugin functionality."""
        print(f"Executing {{self.name}} plugin")
    
    def cleanup(self):
        """Cleanup plugin resources."""
        print(f"Cleaning up {{self.name}} plugin")

# Plugin instance
plugin = {name.replace("-", "_").title()}Plugin()
'''
        with open(main_file, 'w', encoding='utf-8') as f:
            f.write(main_content)
        
        # Create requirements.txt
        requirements_file = os.path.join(plugin_dir, "requirements.txt")
        requirements_content = """# Plugin dependencies
# Add your Python package dependencies here
# Example:
# requests>=2.25.0
# pyyaml>=5.4.0
"""
        with open(requirements_file, 'w', encoding='utf-8') as f:
            f.write(requirements_content)
        
        # Create README.md
        readme_file = os.path.join(plugin_dir, "README.md")
        readme_content = f"""# {name}

{kwargs.get("description", f"A CoffeeBreak plugin for {name}")}

## Installation

```bash
# Build the plugin
coffeebreak plugin build

# Install in CoffeeBreak
# (Installation method will be available in future releases)
```

## Development

```bash
# Initialize development environment
coffeebreak plugin init

# Run tests
./scripts/test.sh

# Build plugin
./scripts/build.sh
```

## Configuration

This plugin can be configured through the `coffeebreak-plugin.yml` file.

## License

{kwargs.get("license", "MIT License")}
"""
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        if self.verbose:
            print(f"Created plugin source files: __init__.py, {package_name}.py, requirements.txt, README.md")
    
    def list_available_templates(self) -> List[str]:
        """Get list of available plugin templates."""
        templates_dir = Path(__file__).parent / "templates"
        
        if not templates_dir.exists():
            return []
        
        templates = []
        for item in templates_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                templates.append(item.name)
        
        return sorted(templates)
    
    def get_template_info(self, template: str) -> Dict[str, Any]:
        """Get information about a template."""
        template_dir = Path(__file__).parent / "templates" / template
        
        if not template_dir.exists():
            raise PluginError(f"Template '{template}' not found")
        
        info = {
            "name": template,
            "path": str(template_dir),
            "description": f"Template for {template} plugins"
        }
        
        # Try to read template info file if it exists
        info_file = template_dir / "template.yml"
        if info_file.exists():
            try:
                import yaml
                with open(info_file, 'r', encoding='utf-8') as f:
                    template_info = yaml.safe_load(f)
                    info.update(template_info)
            except Exception:
                pass
        
        return info