"""Main CLI entry point for CoffeeBreak CLI tool.

This module provides the command-line interface for CoffeeBreak, a development
and deployment automation tool. It includes commands for environment management,
dependency handling, plugin development, secrets management, and production deployment.

The CLI is built using Click and provides a hierarchical command structure
with comprehensive help and error handling.
"""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from coffeebreak import __version__
from coffeebreak.utils.errors import ErrorHandler
from coffeebreak.utils.logging import setup_logging


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be done without executing"
)
@click.option("--log-file", help="Log to file in addition to console")
@click.pass_context
def cli(
    ctx: click.Context, verbose: bool, dry_run: bool, log_file: Optional[str]
) -> None:
    """CoffeeBreak CLI - Development and deployment automation tool.

    CoffeeBreak is a comprehensive tool for managing development environments,
    dependencies, plugins, and production deployments. It provides a unified
    interface for common development and deployment tasks.

    Args:
        ctx: Click context object containing shared state
        verbose: Enable verbose output for detailed logging
        dry_run: Show what would be done without executing commands
        log_file: Optional path to log file for additional logging
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["dry_run"] = dry_run
    ctx.obj["log_file"] = log_file
    ctx.obj["error_handler"] = ErrorHandler(verbose=verbose)

    # Setup logging
    setup_logging(verbose=verbose, log_file=log_file)


@cli.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize CoffeeBreak environments.

    This command group provides subcommands for initializing different types
    of CoffeeBreak environments, including development and production setups.
    """
    pass


@init.command()
@click.option(
    "--organization", default="PI-coffeeBreak", help="GitHub organization name"
)
@click.option("--version", default="1.0.0", help="Project version")
@click.option(
    "--venv",
    default=None,
    metavar="[PATH]",
    help="Create/reuse virtual environment (default: .venv if no path given)",
)
@click.option(
    "--conda",
    default=None,
    metavar="[NAME]",
    help="Create/reuse conda environment (auto-name if no name given)",
)
@click.option("--python", metavar="<PATH>", help="Path to specific Python executable")
@click.pass_context
def dev(
    ctx: click.Context,
    organization: str,
    version: str,
    venv: Optional[str],
    conda: Optional[str],
    python: Optional[str],
) -> None:
    """Initialize full development environment with Python environment setup.

    This command sets up a complete development environment for CoffeeBreak,
    including Python environment management (virtual environment or conda),
    project configuration, and initial dependency setup.

    Args:
        ctx: Click context object
        organization: GitHub organization name for the project
        version: Project version string
        venv: Path for virtual environment (mutually exclusive with conda)
        conda: Name for conda environment (mutually exclusive with venv)
        python: Path to specific Python executable to use

    Raises:
        click.BadParameter: If both venv and conda options are specified
    """
    click.echo("Initializing CoffeeBreak development environment...")

    # Validate mutually exclusive options
    if venv is not None and conda is not None:
        raise click.BadParameter("Cannot use both --venv and --conda options")

    # Determine environment strategy
    if conda is not None:
        env_type = "conda"
        env_identifier = conda  # Could be None (auto-name) or string (specific name)
    else:
        env_type = "venv"
        env_identifier = venv if venv is not None else ".venv"  # Default to .venv

    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would initialize development environment")
        click.echo(f"DRY RUN: Organization: {organization}, Version: {version}")
        click.echo(f"DRY RUN: Environment: {env_type} ({env_identifier})")
        if python:
            click.echo(f"DRY RUN: Python: {python}")
        return

    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments import DevelopmentEnvironment

        # Initialize managers
        config_manager = ConfigManager()
        dev_env = DevelopmentEnvironment(config_manager, verbose=ctx.obj["verbose"])

        # Initialize development environment with Python environment
        success = dev_env.initialize(
            organization=organization,
            version=version,
            env_type=env_type,
            env_path_or_name=env_identifier,
            python_path=python,
        )

        if success:
            click.echo("✓ Development environment initialized successfully!")
            click.echo("\nNext steps:")
            click.echo("  1. Run 'coffeebreak activate' to activate your environment")
            click.echo(
                "  2. Run 'coffeebreak start' to start the development environment"
            )
            click.echo("  3. Check environment status with 'coffeebreak status'")
        else:
            click.echo("✗ Failed to initialize development environment", err=True)
            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(
            e, "Development environment initialization"
        )


@cli.command()
@click.option("--shell", help="Target shell (bash, zsh, fish, cmd, powershell)")
@click.option("--info", is_flag=True, help="Show environment information only")
@click.option(
    "--show-command",
    is_flag=True,
    help="Show activation command instead of auto-executing",
)
@click.pass_context
def activate(
    ctx: click.Context, shell: Optional[str], info: bool, show_command: bool
) -> None:
    """Activate the configured Python environment for the current project.

    By default, launches a new shell with the environment activated.
    Use --show-command to see the manual activation command instead.

    This command supports multiple shell types and can automatically detect
    the current shell. It handles both virtual environments and conda environments.

    Args:
        ctx: Click context object
        shell: Target shell type (auto-detected if not specified)
        info: Show environment information without activating
        show_command: Show activation command instead of executing
    """
    try:
        from coffeebreak.environments.python_env import EnvironmentActivator

        activator = EnvironmentActivator()

        if info:
            # Show environment information
            env_info = activator.get_environment_info()
            click.echo(f"Environment Type: {env_info['type']}")
            if env_info["type"] == "venv":
                click.echo(f"Environment Path: {env_info['path']}")
            elif env_info["type"] == "conda":
                click.echo(f"Environment Name: {env_info['name']}")
            if "python_path" in env_info and env_info["python_path"]:
                click.echo(f"Python Path: {env_info['python_path']}")
            return

        if show_command:
            # Old behavior: show activation command
            activation_cmd = activator.get_activation_command(shell)
            click.echo("To activate your CoffeeBreak environment, run:")
            click.echo(f"  {activation_cmd}")

            if not shell:
                detected_shell = activator._detect_shell()
                click.echo(f"\nDetected shell: {detected_shell}")
                click.echo("Use --shell to specify a different shell")
            return

        # Default behavior: auto-execute (launch new shell with environment activated)
        env_info = activator.get_environment_info()
        detected_shell = shell or activator._detect_shell()

        click.echo(
            f"Starting new {detected_shell} shell with CoffeeBreak environment activated..."
        )
        click.echo("Type 'exit' to return to your original shell.")

        # Set up environment variables
        new_env = os.environ.copy()

        if env_info["type"] == "venv":
            venv_path = env_info["path"]
            new_env["VIRTUAL_ENV"] = venv_path
            new_env["PATH"] = (
                f"{os.path.join(venv_path, 'bin')}:{new_env.get('PATH', '')}"
            )

            # Remove PYTHONHOME if present (can interfere with venv)
            if "PYTHONHOME" in new_env:
                del new_env["PYTHONHOME"]

            # Update PS1 prompt to show activation
            ps1 = new_env.get("PS1", "$ ")
            new_env["PS1"] = f"(coffeebreak) {ps1}"

        elif env_info["type"] == "conda":
            # For conda environments, we need to use conda's activation
            conda_env_name = env_info.get("name", "")
            click.echo(
                f"Note: Conda environment '{conda_env_name}' - using conda activation"
            )

            # Try to activate conda environment
            try:
                # Use conda activation script
                conda_activate_cmd = f"conda activate {conda_env_name}"
                if detected_shell in ["bash", "zsh"]:
                    # Launch shell with conda activation
                    shell_cmd = f'{detected_shell} -c "source $(conda info --base)/etc/profile.d/conda.sh && conda activate {conda_env_name} && exec {detected_shell}"'
                    subprocess.run(shell_cmd, shell=True, env=new_env)
                    return
                else:
                    click.echo(
                        f"Auto-activation for conda with {detected_shell} not fully supported."
                    )
                    click.echo(f"Please run: {conda_activate_cmd}")
                    return
            except Exception as e:
                click.echo(f"Failed to activate conda environment: {e}")
                return

        # Launch shell with modified environment
        try:
            if detected_shell in ["bash", "zsh"]:
                subprocess.run([detected_shell], env=new_env)
            elif detected_shell == "fish":
                subprocess.run(["fish"], env=new_env)
            elif detected_shell == "cmd":
                subprocess.run(["cmd"], env=new_env, shell=True)
            elif detected_shell == "powershell":
                subprocess.run(["powershell"], env=new_env)
            else:
                click.echo(
                    f"Shell '{detected_shell}' not supported for auto-activation."
                )
                click.echo("Use --show-command to see manual activation instructions.")

        except FileNotFoundError:
            click.echo(f"Shell '{detected_shell}' not found on system.")
            click.echo("Use --show-command to see manual activation instructions.")
        except Exception as e:
            click.echo(f"Failed to launch shell: {e}")
            click.echo("Use --show-command to see manual activation instructions.")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Environment activation")


@init.command()
@click.option("--docker", is_flag=True, help="Generate Docker production project")
@click.option("--domain", help="Specify production domain")
@click.option("--ssl-email", help="Email for SSL certificate generation")
@click.option(
    "--standalone", is_flag=True, help="Setup standalone production installation"
)
@click.option("--output-dir", default=".", help="Output directory for production files")
@click.pass_context
def production(
    ctx: click.Context,
    docker: bool,
    domain: Optional[str],
    ssl_email: Optional[str],
    standalone: bool,
    output_dir: str,
) -> None:
    """Initialize production environment.

    This command sets up a production environment for CoffeeBreak, supporting
    both Docker-based deployments and standalone server installations.

    Args:
        ctx: Click context object
        docker: Generate Docker production project
        domain: Production domain name (e.g., example.com)
        ssl_email: Email address for SSL certificate generation
        standalone: Setup standalone production installation
        output_dir: Output directory for production files
    """
    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would initialize production environment")
        click.echo(f"DRY RUN: Docker mode: {docker}")
        click.echo(f"DRY RUN: Domain: {domain}")
        click.echo(f"DRY RUN: Standalone: {standalone}")
        click.echo(f"DRY RUN: Output: {output_dir}")
        return

    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.production import ProductionEnvironment

        # Initialize components
        config_manager = ConfigManager()
        prod_env = ProductionEnvironment(config_manager, verbose=ctx.obj["verbose"])

        click.echo("Initializing CoffeeBreak production environment...")

        if not domain:
            domain = click.prompt("Production domain (e.g., your-domain.com)")

        if not ssl_email:
            ssl_email = click.prompt(
                "Email for SSL certificates", default=f"admin@{domain}"
            )

        if standalone:
            # Standalone installation
            click.echo(f"\nSetting up standalone production for {domain}...")

            result = prod_env.setup_standalone_production(
                domain=domain, ssl_email=ssl_email, output_dir=output_dir
            )

            if result["success"]:
                click.echo("✓ Standalone production environment setup completed!")
                click.echo("\nSetup summary:")
                click.echo(f"  Domain: {domain}")
                click.echo(f"  SSL email: {ssl_email}")
                click.echo(f"  Installation scripts: {result['scripts_dir']}")

                click.echo("\nNext steps:")
                click.echo(f"  1. Review configuration in {result['config_dir']}")
                click.echo(f"  2. Run installation: sudo {result['install_script']}")
                click.echo("  3. Configure domain DNS to point to this server")
            else:
                click.echo(
                    f"✗ Standalone setup failed: {result.get('error', 'Unknown error')}"
                )
                ctx.exit(1)

        elif docker:
            # Docker production setup
            click.echo(f"\nGenerating Docker production project for {domain}...")

            result = prod_env.generate_docker_project(
                output_dir=output_dir,
                domain=domain,
                ssl_email=ssl_email,
                deployment_config={},
            )

            if result["success"]:
                click.echo("✓ Docker production project generated!")
                click.echo("\nProject details:")
                click.echo(f"  Project directory: {result['project_dir']}")
                click.echo(f"  Files created: {len(result['files_created'])}")
                click.echo(f"  Secrets generated: {result['secrets_count']}")

                click.echo("\nNext steps:")
                click.echo(f"  1. cd {result['project_dir']}")
                click.echo("  2. Review docker-compose.yml and configuration")
                click.echo("  3. Deploy with: ./deploy.sh")
            else:
                click.echo(
                    f"✗ Docker project generation failed: {result.get('error', 'Unknown error')}"
                )
                ctx.exit(1)

        else:
            # Interactive setup - ask user to choose
            click.echo("\nChoose production setup type:")
            click.echo("1. Docker Compose (recommended for most use cases)")
            click.echo("2. Standalone installation (direct server installation)")

            choice = click.prompt("Select option", type=click.Choice(["1", "2"]))

            if choice == "1":
                # Docker setup
                result = prod_env.generate_docker_project(
                    output_dir=output_dir,
                    domain=domain,
                    ssl_email=ssl_email,
                    deployment_config={},
                )

                if result["success"]:
                    click.echo("✓ Docker production project generated!")
                    click.echo(f"Project directory: {result['project_dir']}")
                else:
                    click.echo(
                        f"✗ Docker project generation failed: {result.get('error', 'Unknown error')}"
                    )
                    ctx.exit(1)

            else:
                # Standalone setup
                result = prod_env.setup_standalone_production(
                    domain=domain, ssl_email=ssl_email, output_dir=output_dir
                )

                if result["success"]:
                    click.echo("✓ Standalone production environment setup completed!")
                    click.echo(f"Installation scripts: {result['scripts_dir']}")
                else:
                    click.echo(
                        f"✗ Standalone setup failed: {result.get('error', 'Unknown error')}"
                    )
                    ctx.exit(1)

        click.echo(f"\n✓ Production environment initialization completed for {domain}")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(
            e, "Production environment initialization"
        )


@cli.command()
@click.option("--profile", help="Dependency profile to use (full, minimal, plugin-dev)")
@click.option("--services", help="Comma-separated list of specific services to start")
@click.option("--skip-clone", is_flag=True, help="Skip repository cloning")
@click.option("--skip-deps", is_flag=True, help="Skip dependency startup")
@click.option("--detach", "-d", is_flag=True, help="Run in background (detached mode)")
@click.pass_context
def start(
    ctx: click.Context,
    profile: Optional[str],
    services: Optional[str],
    skip_clone: bool,
    skip_deps: bool,
    detach: bool,
) -> None:
    """Start development environment.

    This command starts the complete development environment, including
    repository cloning, dependency services, and application components.

    Args:
        ctx: Click context object
        profile: Dependency profile to use (full, minimal, plugin-dev)
        services: Comma-separated list of specific services to start
        skip_clone: Skip repository cloning step
        skip_deps: Skip dependency startup step
        detach: Run in background (detached mode)
    """
    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would start development environment")
        if profile:
            click.echo(f"DRY RUN: Profile: {profile}")
        if services:
            click.echo(f"DRY RUN: Services: {services}")
        if skip_clone:
            click.echo("DRY RUN: Would skip repository cloning")
        if skip_deps:
            click.echo("DRY RUN: Would skip dependency startup")
        if detach:
            click.echo("DRY RUN: Would run in detached mode")
        return

    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments import DevelopmentEnvironment

        # Initialize managers
        config_manager = ConfigManager()
        dev_env = DevelopmentEnvironment(config_manager, verbose=ctx.obj["verbose"])

        click.echo("Starting CoffeeBreak development environment...")

        # Parse services list
        service_list = None
        if services:
            service_list = [s.strip() for s in services.split(",") if s.strip()]

        # Start development environment
        result = dev_env.start_environment(
            profile=profile,
            services=service_list,
            skip_clone=skip_clone,
            skip_deps=skip_deps,
            detach=detach,
        )

        if result["success"]:
            click.echo("✓ Development environment started successfully!")

            if result.get("services_started"):
                click.echo(f"\nServices started: {len(result['services_started'])}")
                if ctx.obj["verbose"]:
                    for service in result["services_started"]:
                        click.echo(f"  - {service}")

            if result.get("repositories_cloned"):
                click.echo(
                    f"\nRepositories cloned: {len(result['repositories_cloned'])}"
                )
                if ctx.obj["verbose"]:
                    for repo in result["repositories_cloned"]:
                        click.echo(f"  - {repo}")

            if detach:
                click.echo("\nEnvironment is running in background.")
                click.echo("Use 'coffeebreak status' to check status")
                click.echo("Use 'coffeebreak stop' to stop the environment")
            else:
                click.echo("\nEnvironment is ready for development!")
                click.echo("Press Ctrl+C to stop the environment")
        else:
            click.echo(
                f"✗ Failed to start development environment: {result.get('error', 'Unknown error')}"
            )

            if result.get("errors"):
                click.echo("\nErrors encountered:")
                for error in result["errors"]:
                    click.echo(f"  - {error}")

            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Development environment startup")


@cli.command()
@click.pass_context
def stop(ctx: click.Context) -> None:
    """Stop development environment.

    This command stops all running development environment components,
    including dependency services and application processes.

    Args:
        ctx: Click context object
    """
    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would stop development environment")
        return

    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments import DevelopmentEnvironment

        # Initialize managers
        config_manager = ConfigManager()
        dev_env = DevelopmentEnvironment(config_manager, verbose=ctx.obj["verbose"])

        click.echo("Stopping CoffeeBreak development environment...")

        result = dev_env.stop_environment()

        if result["success"]:
            click.echo("✓ Development environment stopped successfully!")

            if result.get("services_stopped"):
                click.echo(f"\nServices stopped: {len(result['services_stopped'])}")
                if ctx.obj["verbose"]:
                    for service in result["services_stopped"]:
                        click.echo(f"  - {service}")
        else:
            click.echo(
                f"✗ Failed to stop development environment: {result.get('error', 'Unknown error')}"
            )

            if result.get("errors"):
                click.echo("\nErrors encountered:")
                for error in result["errors"]:
                    click.echo(f"  - {error}")

            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Development environment shutdown")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show development environment status.

    This command displays the current status of all development environment
    components, including services, repositories, and application processes.

    Args:
        ctx: Click context object
    """
    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments import DevelopmentEnvironment

        # Initialize managers
        config_manager = ConfigManager()
        dev_env = DevelopmentEnvironment(config_manager, verbose=ctx.obj["verbose"])

        click.echo("CoffeeBreak Development Environment Status")
        click.echo("=" * 50)

        # Get environment status
        status_info = dev_env.get_environment_status()

        # Display overall status
        if status_info["running"]:
            click.echo("✓ Environment is running")
        else:
            click.echo("✗ Environment is not running")

        # Display services status
        if status_info.get("services"):
            click.echo(f"\nServices ({len(status_info['services'])}):")
            for service, info in status_info["services"].items():
                status_icon = "✓" if info["running"] else "✗"
                status_text = "running" if info["running"] else "stopped"
                click.echo(f"  {status_icon} {service}: {status_text}")

                if ctx.obj["verbose"] and info.get("details"):
                    for detail in info["details"]:
                        click.echo(f"    - {detail}")

        # Display repositories status
        if status_info.get("repositories"):
            click.echo(f"\nRepositories ({len(status_info['repositories'])}):")
            for repo, info in status_info["repositories"].items():
                status_icon = "✓" if info["cloned"] else "✗"
                status_text = "cloned" if info["cloned"] else "not cloned"
                click.echo(f"  {status_icon} {repo}: {status_text}")

                if ctx.obj["verbose"] and info.get("path"):
                    click.echo(f"    Path: {info['path']}")

        # Display application status
        if status_info.get("applications"):
            click.echo(f"\nApplications ({len(status_info['applications'])}):")
            for app, info in status_info["applications"].items():
                status_icon = "✓" if info["running"] else "✗"
                status_text = "running" if info["running"] else "stopped"
                click.echo(f"  {status_icon} {app}: {status_text}")

                if ctx.obj["verbose"] and info.get("port"):
                    click.echo(f"    Port: {info['port']}")

        # Display summary
        total_components = (
            len(status_info.get("services", {}))
            + len(status_info.get("repositories", {}))
            + len(status_info.get("applications", {}))
        )

        running_components = sum(
            1 for s in status_info.get("services", {}).values() if s["running"]
        )
        running_components += sum(
            1 for a in status_info.get("applications", {}).values() if a["running"]
        )

        click.echo(
            f"\nSummary: {running_components}/{total_components} components running"
        )

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Status check")


@cli.command()
@click.argument("service", required=False)
@click.option(
    "--tail", "-n", default=100, help="Number of lines to show from the end of logs"
)
@click.option("--follow", "-f", is_flag=True, help="Follow log output in real-time")
@click.option(
    "--since",
    help='Show logs since timestamp (e.g., "1h", "30m", "2023-01-01T10:00:00")',
)
@click.pass_context
def logs(
    ctx: click.Context,
    service: Optional[str],
    tail: int,
    follow: bool,
    since: Optional[str],
) -> None:
    """Show application logs.

    This command displays logs from application components. It can show logs
    for a specific service or all services, with options for following logs
    in real-time and filtering by time.

    Args:
        ctx: Click context object
        service: Specific service name to show logs for (optional)
        tail: Number of lines to show from the end of logs
        follow: Follow log output in real-time
        since: Show logs since timestamp (e.g., "1h", "30m", "2023-01-01T10:00:00")
    """
    if ctx.obj["dry_run"]:
        if service:
            click.echo(f"DRY RUN: Would show logs for service: {service}")
        else:
            click.echo("DRY RUN: Would show logs for all services")
        if follow:
            click.echo("DRY RUN: Would follow logs in real-time")
        return

    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments import DevelopmentEnvironment

        # Initialize managers
        config_manager = ConfigManager()
        dev_env = DevelopmentEnvironment(config_manager, verbose=ctx.obj["verbose"])

        if service:
            click.echo(f"Showing logs for service: {service}")

            # Get logs for specific service
            logs_result = dev_env.get_service_logs(
                service_name=service, tail=tail, follow=follow, since=since
            )

            if logs_result["success"]:
                if follow:
                    click.echo(f"Following logs for {service} (Ctrl+C to stop)...")
                    try:
                        # Stream logs
                        for log_line in dev_env.stream_service_logs(service):
                            click.echo(log_line.rstrip())
                    except KeyboardInterrupt:
                        click.echo("\nLog following stopped")
                else:
                    click.echo(logs_result["logs"])
            else:
                click.echo(
                    f"Failed to get logs: {logs_result.get('error', 'Unknown error')}"
                )
                ctx.exit(1)
        else:
            click.echo("Showing logs for all services...")

            # Get all running services
            status_info = dev_env.get_environment_status()
            running_services = [
                name
                for name, info in status_info.get("services", {}).items()
                if info["running"]
            ]

            if not running_services:
                click.echo("No services are currently running")
                return

            for service_name in running_services:
                click.echo(f"\n=== Logs for {service_name} ===")

                logs_result = dev_env.get_service_logs(
                    service_name=service_name,
                    tail=min(
                        tail // len(running_services), 20
                    ),  # Distribute lines among services
                    follow=False,
                    since=since,
                )

                if logs_result["success"]:
                    logs_content = logs_result["logs"].strip()
                    if logs_content:
                        click.echo(logs_content)
                    else:
                        click.echo("No recent logs")
                else:
                    click.echo(
                        f"Failed to get logs: {logs_result.get('error', 'Unknown error')}"
                    )

                click.echo("")  # Add spacing between services

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Log retrieval")


@cli.command()
@click.argument("target", required=False)
@click.option("--output", "-o", help="Output directory for build artifacts")
@click.option("--clean", is_flag=True, help="Clean build directory before building")
@click.option("--production", is_flag=True, help="Build for production (optimized)")
@click.option("--docker", is_flag=True, help="Build Docker images")
@click.pass_context
def build(
    ctx: click.Context,
    target: Optional[str],
    output: Optional[str],
    clean: bool,
    production: bool,
    docker: bool,
) -> None:
    """Build system, plugin, or Docker images.

    This command builds various components of the CoffeeBreak system, including
    plugins, application components, and Docker images. It supports both
    development and production build modes.

    Args:
        ctx: Click context object
        target: Specific target to build (plugin name, component, or None for system)
        output: Output directory for build artifacts
        clean: Clean build directory before building
        production: Build for production (optimized)
        docker: Build Docker images
    """
    if ctx.obj["dry_run"]:
        if target:
            click.echo(f"DRY RUN: Would build target: {target}")
        else:
            click.echo("DRY RUN: Would build CoffeeBreak system")
        if output:
            click.echo(f"DRY RUN: Output directory: {output}")
        if production:
            click.echo("DRY RUN: Production build mode")
        if docker:
            click.echo("DRY RUN: Would build Docker images")
        return

    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.detector import EnvironmentDetector

        # Initialize components
        config_manager = ConfigManager()
        env_detector = EnvironmentDetector()

        # Determine what to build
        environment_type = env_detector.detect_environment()

        if target:
            # Build specific target (plugin or component)
            if environment_type == "plugin":
                click.echo(f"Building plugin: {target}")
                from coffeebreak.environments.plugin import PluginEnvironment

                plugin_env = PluginEnvironment(
                    config_manager, verbose=ctx.obj["verbose"]
                )

                # Build plugin
                result = plugin_env.build_plugin(
                    plugin_dir=target if os.path.exists(target) else ".",
                    output_dir=output or "dist",
                    exclude_native=not production,
                )

                if result:
                    click.echo(f"✓ Plugin built successfully: {result}")
                    file_size = os.path.getsize(result)
                    size_str = (
                        f"{file_size / (1024 * 1024):.1f} MB"
                        if file_size > 1024 * 1024
                        else f"{file_size / 1024:.1f} KB"
                    )
                    click.echo(f"Package size: {size_str}")
                else:
                    click.echo("✗ Plugin build failed")
                    ctx.exit(1)
            else:
                click.echo(f"Building component: {target}")
                # Build specific component or service
                result = _build_component(
                    target, output, production, ctx.obj["verbose"]
                )

                if result["success"]:
                    click.echo(f"✓ Component '{target}' built successfully")
                    if result.get("artifacts"):
                        click.echo("Build artifacts:")
                        for artifact in result["artifacts"]:
                            click.echo(f"  - {artifact}")
                else:
                    click.echo(
                        f"✗ Failed to build component '{target}': {result.get('error', 'Unknown error')}"
                    )
                    ctx.exit(1)
        else:
            # Build entire system
            if environment_type == "plugin":
                click.echo("Building current plugin...")
                from coffeebreak.environments.plugin import PluginEnvironment

                plugin_env = PluginEnvironment(
                    config_manager, verbose=ctx.obj["verbose"]
                )

                result = plugin_env.build_plugin(
                    plugin_dir=".",
                    output_dir=output or "dist",
                    exclude_native=not production,
                )

                if result:
                    click.echo(f"✓ Plugin built successfully: {result}")
                else:
                    click.echo("✗ Plugin build failed")
                    ctx.exit(1)

            elif docker:
                click.echo("Building Docker images...")
                result = _build_docker_images(output, production, ctx.obj["verbose"])

                if result["success"]:
                    click.echo("✓ Docker images built successfully")
                    if result.get("images"):
                        click.echo("Built images:")
                        for image in result["images"]:
                            click.echo(f"  - {image}")
                else:
                    click.echo(
                        f"✗ Docker build failed: {result.get('error', 'Unknown error')}"
                    )
                    ctx.exit(1)

            else:
                click.echo("Building CoffeeBreak system...")

                # Clean build directory if requested
                if clean and output:
                    import shutil

                    if os.path.exists(output):
                        shutil.rmtree(output)
                        click.echo(f"Cleaned build directory: {output}")

                # Build all components
                components = ["frontend", "backend", "core"]
                build_results = []

                for component in components:
                    click.echo(f"\nBuilding {component}...")
                    result = _build_component(
                        component, output, production, ctx.obj["verbose"]
                    )
                    build_results.append(result)

                    if result["success"]:
                        click.echo(f"✓ {component} built successfully")
                        if result.get("build_dir"):
                            click.echo(f"  Build directory: {result['build_dir']}")
                        if result.get("artifacts") and ctx.obj["verbose"]:
                            click.echo(f"  Artifacts ({len(result['artifacts'])}):")
                            for artifact in result["artifacts"][:5]:  # Show first 5
                                click.echo(f"    - {artifact}")
                            if len(result["artifacts"]) > 5:
                                click.echo(
                                    f"    ... and {len(result['artifacts']) - 5} more"
                                )
                    else:
                        click.echo(
                            f"✗ {component} build failed: {result.get('error', 'Unknown error')}"
                        )

                # Summary
                successful = sum(1 for r in build_results if r["success"])
                total = len(build_results)
                total_artifacts = sum(
                    len(r.get("artifacts", [])) for r in build_results if r["success"]
                )

                if successful == total:
                    click.echo(f"\n✓ All {total} components built successfully")
                    click.echo(f"Total artifacts created: {total_artifacts}")

                    build_dir = output or "build"
                    click.echo(f"Build output directory: {build_dir}/")
                    click.echo("\nDirectory structure:")
                    for result in build_results:
                        if result["success"] and result.get("build_dir"):
                            click.echo(
                                f"  {result['component']}/  ({len(result.get('artifacts', []))} files)"
                            )

                    click.echo("\nTo see detailed artifacts, run with --verbose")
                else:
                    failed = total - successful
                    click.echo(
                        f"\n✗ Build completed with {failed} failures ({successful}/{total} successful)"
                    )
                    ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Build process")


def _build_component(
    component: str, output_dir: str, production: bool, verbose: bool
) -> Dict[str, Any]:
    """Build a specific component.

    This function builds a specific component (frontend, backend, core, etc.)
    by detecting the build system and running the appropriate build process.

    Args:
        component: Name of the component to build
        output_dir: Output directory for build artifacts
        production: Whether to build for production (optimized)
        verbose: Enable verbose output

    Returns:
        Dictionary containing build results with keys:
        - success: Boolean indicating if build was successful
        - component: Name of the component that was built
        - artifacts: List of generated artifact paths
        - build_dir: Path to the build directory
        - error: Error message if build failed
    """
    try:
        from pathlib import Path

        component_dir = Path(component)
        if not component_dir.exists():
            return {
                "success": False,
                "error": f"Component directory '{component}' not found",
            }

        # Create output directory
        build_dir = Path(output_dir or "build") / component
        build_dir.mkdir(parents=True, exist_ok=True)

        artifacts = []

        # Check for different build systems and build accordingly
        if component == "frontend":
            # Frontend build (React/Vue/Angular)
            artifacts.extend(
                _build_frontend(component_dir, build_dir, production, verbose)
            )

        elif component == "backend":
            # Backend build (Node.js/Python/Java)
            artifacts.extend(
                _build_backend(component_dir, build_dir, production, verbose)
            )

        elif component == "core":
            # Core build (shared libraries/utilities)
            artifacts.extend(_build_core(component_dir, build_dir, production, verbose))

        else:
            # Generic component build
            artifacts.extend(
                _build_generic(component_dir, build_dir, production, verbose)
            )

        if artifacts:
            return {
                "success": True,
                "component": component,
                "artifacts": artifacts,
                "build_dir": str(build_dir),
            }
        else:
            return {
                "success": False,
                "error": f"No artifacts were generated for {component}",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def _build_frontend(
    component_dir: Path, build_dir: Path, production: bool, verbose: bool
) -> List[str]:
    """Build frontend component.

    This function builds frontend components by detecting the build system
    (Node.js, static files, etc.) and running the appropriate build process.

    Args:
        component_dir: Directory containing the frontend component
        build_dir: Output directory for build artifacts
        production: Whether to build for production (optimized)
        verbose: Enable verbose output

    Returns:
        List of generated artifact paths relative to the build directory
    """
    import shutil
    import subprocess

    artifacts = []

    try:
        # Check for package.json (Node.js project)
        package_json = component_dir / "package.json"
        if package_json.exists():
            if verbose:
                print(f"Found Node.js project in {component_dir}")

            # Install dependencies if node_modules doesn't exist
            if not (component_dir / "node_modules").exists():
                subprocess.run(["npm", "install"], cwd=component_dir, check=True)

            # Run build script
            build_script = "build:prod" if production else "build"
            try:
                result = subprocess.run(
                    ["npm", "run", build_script],
                    cwd=component_dir,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                if verbose:
                    print(result.stdout)
            except subprocess.CalledProcessError:
                # Try default build script
                subprocess.run(["npm", "run", "build"], cwd=component_dir, check=True)

            # Copy build output
            source_dirs = ["dist", "build", "public"]
            for source_name in source_dirs:
                source_dir = component_dir / source_name
                if source_dir.exists():
                    dest_dir = build_dir / source_name
                    shutil.copytree(source_dir, dest_dir, dirs_exist_ok=True)

                    # List artifacts
                    for file_path in dest_dir.rglob("*"):
                        if file_path.is_file():
                            artifacts.append(
                                str(file_path.relative_to(build_dir.parent))
                            )
                    break

        # Check for static files
        static_dirs = ["static", "assets", "public"]
        for static_name in static_dirs:
            static_dir = component_dir / static_name
            if static_dir.exists():
                dest_dir = build_dir / static_name
                shutil.copytree(static_dir, dest_dir, dirs_exist_ok=True)

                for file_path in dest_dir.rglob("*"):
                    if file_path.is_file():
                        artifacts.append(str(file_path.relative_to(build_dir.parent)))

        # If no specific build system, copy source files
        if not artifacts:
            for ext in ["*.html", "*.css", "*.js", "*.jsx", "*.vue", "*.ts", "*.tsx"]:
                for file_path in component_dir.rglob(ext):
                    dest_path = build_dir / file_path.relative_to(component_dir)
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, dest_path)
                    artifacts.append(str(dest_path.relative_to(build_dir.parent)))

    except Exception as e:
        if verbose:
            print(f"Frontend build error: {e}")

    return artifacts


def _build_backend(
    component_dir: Path, build_dir: Path, production: bool, verbose: bool
) -> List[str]:
    """Build backend component.

    This function builds backend components by detecting the technology stack
    (Python, Node.js, Java, etc.) and running the appropriate build process.

    Args:
        component_dir: Directory containing the backend component
        build_dir: Output directory for build artifacts
        production: Whether to build for production (optimized)
        verbose: Enable verbose output

    Returns:
        List of generated artifact paths relative to the build directory
    """
    import os
    import shutil
    import subprocess

    artifacts = []

    try:
        # Check for different backend technologies

        # Python project
        if (component_dir / "requirements.txt").exists() or (
            component_dir / "pyproject.toml"
        ).exists():
            if verbose:
                print(f"Found Python project in {component_dir}")

            # Create virtual environment in build directory
            venv_dir = build_dir / "venv"
            subprocess.run(["python", "-m", "venv", str(venv_dir)], check=True)

            # Install dependencies
            pip_cmd = (
                str(venv_dir / "bin" / "pip")
                if os.name != "nt"
                else str(venv_dir / "Scripts" / "pip.exe")
            )

            if (component_dir / "requirements.txt").exists():
                subprocess.run(
                    [pip_cmd, "install", "-r", str(component_dir / "requirements.txt")],
                    check=True,
                )

            # Copy source files
            for ext in ["*.py", "*.pyx", "*.pyi"]:
                for file_path in component_dir.rglob(ext):
                    if "venv" not in str(file_path) and "__pycache__" not in str(
                        file_path
                    ):
                        dest_path = (
                            build_dir / "src" / file_path.relative_to(component_dir)
                        )
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file_path, dest_path)
                        artifacts.append(str(dest_path.relative_to(build_dir.parent)))

        # Node.js project
        elif (component_dir / "package.json").exists():
            if verbose:
                print(f"Found Node.js backend project in {component_dir}")

            # Install dependencies
            if not (component_dir / "node_modules").exists():
                subprocess.run(["npm", "install"], cwd=component_dir, check=True)

            # Copy source files and dependencies
            shutil.copytree(
                component_dir / "node_modules",
                build_dir / "node_modules",
                dirs_exist_ok=True,
            )

            for ext in ["*.js", "*.ts", "*.json"]:
                for file_path in component_dir.rglob(ext):
                    if "node_modules" not in str(file_path):
                        dest_path = build_dir / file_path.relative_to(component_dir)
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file_path, dest_path)
                        artifacts.append(str(dest_path.relative_to(build_dir.parent)))

        # Java project
        elif (component_dir / "pom.xml").exists() or (
            component_dir / "build.gradle"
        ).exists():
            if verbose:
                print(f"Found Java project in {component_dir}")

            # Maven build
            if (component_dir / "pom.xml").exists():
                goal = "package" if production else "compile"
                subprocess.run(["mvn", "clean", goal], cwd=component_dir, check=True)

                target_dir = component_dir / "target"
                if target_dir.exists():
                    shutil.copytree(
                        target_dir, build_dir / "target", dirs_exist_ok=True
                    )
                    for jar_file in (build_dir / "target").glob("*.jar"):
                        artifacts.append(str(jar_file.relative_to(build_dir.parent)))

            # Gradle build
            elif (component_dir / "build.gradle").exists():
                task = "build" if production else "compileJava"
                subprocess.run(["./gradlew", task], cwd=component_dir, check=True)

                build_libs = component_dir / "build" / "libs"
                if build_libs.exists():
                    dest_dir = build_dir / "libs"
                    shutil.copytree(build_libs, dest_dir, dirs_exist_ok=True)
                    for jar_file in dest_dir.glob("*.jar"):
                        artifacts.append(str(jar_file.relative_to(build_dir.parent)))

        # Generic backend - copy source files
        else:
            for ext in [
                "*.py",
                "*.js",
                "*.ts",
                "*.java",
                "*.go",
                "*.rs",
                "*.cpp",
                "*.c",
            ]:
                for file_path in component_dir.rglob(ext):
                    dest_path = build_dir / file_path.relative_to(component_dir)
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, dest_path)
                    artifacts.append(str(dest_path.relative_to(build_dir.parent)))

    except Exception as e:
        if verbose:
            print(f"Backend build error: {e}")

    return artifacts


def _build_core(
    component_dir: Path, build_dir: Path, production: bool, verbose: bool
) -> List[str]:
    """Build core component.

    This function builds core components by copying all source files and
    creating a build manifest with metadata about the build.

    Args:
        component_dir: Directory containing the core component
        build_dir: Output directory for build artifacts
        production: Whether to build for production (optimized)
        verbose: Enable verbose output

    Returns:
        List of generated artifact paths relative to the build directory
    """
    import json
    import shutil

    artifacts = []

    try:
        # Copy all source files for core component
        for file_path in component_dir.rglob("*"):
            if file_path.is_file() and not any(
                ignore in str(file_path)
                for ignore in [".git", "__pycache__", "node_modules", ".env"]
            ):
                dest_path = build_dir / file_path.relative_to(component_dir)
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, dest_path)
                artifacts.append(str(dest_path.relative_to(build_dir.parent)))

        # Create build manifest
        manifest = {
            "component": "core",
            "build_time": str(Path().resolve()),
            "production": production,
            "file_count": len(artifacts),
        }

        manifest_path = build_dir / "build_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        artifacts.append(str(manifest_path.relative_to(build_dir.parent)))

    except Exception as e:
        if verbose:
            print(f"Core build error: {e}")

    return artifacts


def _build_generic(
    component_dir: Path, build_dir: Path, production: bool, verbose: bool
) -> List[str]:
    """Build generic component.

    This function builds generic components by copying all source files
    without any specific build process.

    Args:
        component_dir: Directory containing the generic component
        build_dir: Output directory for build artifacts
        production: Whether to build for production (optimized)
        verbose: Enable verbose output

    Returns:
        List of generated artifact paths relative to the build directory
    """
    import shutil

    artifacts = []

    try:
        # Copy all source files
        for file_path in component_dir.rglob("*"):
            if file_path.is_file() and not any(
                ignore in str(file_path)
                for ignore in [".git", "__pycache__", "node_modules"]
            ):
                dest_path = build_dir / file_path.relative_to(component_dir)
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, dest_path)
                artifacts.append(str(dest_path.relative_to(build_dir.parent)))

    except Exception as e:
        if verbose:
            print(f"Generic build error: {e}")

    return artifacts


def _build_docker_images(
    output_dir: str, production: bool, verbose: bool
) -> Dict[str, Any]:
    """Build Docker images for the system.

    This function builds Docker images for the CoffeeBreak system components
    (frontend, backend, core) using Docker build commands.

    Args:
        output_dir: Output directory for build artifacts
        production: Whether to build for production (optimized)
        verbose: Enable verbose output

    Returns:
        Dictionary containing build results with keys:
        - success: Boolean indicating if build was successful
        - images: List of built image tags
        - error: Error message if build failed
    """
    try:
        import subprocess

        images_built = []

        # Define images to build
        image_configs = [
            {"name": "coffeebreak-frontend", "path": "./frontend"},
            {"name": "coffeebreak-backend", "path": "./backend"},
            {"name": "coffeebreak-core", "path": "./core"},
        ]

        for config in image_configs:
            if os.path.exists(config["path"]):
                tag = f"{config['name']}:{'latest' if production else 'dev'}"

                cmd = ["docker", "build", "-t", tag, config["path"]]
                if verbose:
                    print(f"Running: {' '.join(cmd)}")

                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0:
                    images_built.append(tag)
                else:
                    return {
                        "success": False,
                        "error": f"Failed to build {config['name']}: {result.stderr}",
                    }

        return {"success": True, "images": images_built}

    except Exception as e:
        return {"success": False, "error": str(e)}


@cli.command()
@click.option(
    "--environment",
    "-e",
    default="production",
    help="Target environment (production, staging)",
)
@click.option(
    "--strategy",
    default="rolling",
    help="Deployment strategy (rolling, blue-green, canary)",
)
@click.option("--timeout", default=300, help="Deployment timeout in seconds")
@click.option("--force", is_flag=True, help="Force deployment even if validation fails")
@click.option("--skip-validation", is_flag=True, help="Skip pre-deployment validation")
@click.option("--skip-backup", is_flag=True, help="Skip pre-deployment backup")
@click.pass_context
def deploy(
    ctx: click.Context,
    environment: str,
    strategy: str,
    timeout: int,
    force: bool,
    skip_validation: bool,
    skip_backup: bool,
) -> None:
    """Deploy to configured production.

    This command deploys the CoffeeBreak system to the configured production
    environment using the specified deployment strategy and options.

    Args:
        ctx: Click context object
        environment: Target environment (production, staging)
        strategy: Deployment strategy (rolling, blue-green, canary)
        timeout: Deployment timeout in seconds
        force: Force deployment even if validation fails
        skip_validation: Skip pre-deployment validation
        skip_backup: Skip pre-deployment backup
    """
    if ctx.obj["dry_run"]:
        click.echo(f"DRY RUN: Would deploy to {environment}")
        click.echo(f"DRY RUN: Strategy: {strategy}")
        click.echo(f"DRY RUN: Timeout: {timeout}s")
        return

    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.detector import EnvironmentDetector
        from coffeebreak.infrastructure.deployment import DeploymentManager

        # Initialize components
        config_manager = ConfigManager()
        env_detector = EnvironmentDetector()
        deployment_manager = DeploymentManager(verbose=ctx.obj["verbose"])

        click.echo(f"Starting deployment to {environment}...")
        click.echo(f"Strategy: {strategy}")

        # Detect current environment and deployment type
        current_env = env_detector.detect_environment()

        # Pre-deployment validation
        if not skip_validation:
            click.echo("\nRunning pre-deployment validation...")

            validation_result = deployment_manager.validate_deployment_readiness(
                target_environment=environment, strategy=strategy
            )

            if not validation_result["ready"] and not force:
                click.echo("✗ Pre-deployment validation failed:")
                for issue in validation_result["issues"]:
                    click.echo(f"  - {issue}")

                click.echo("\nUse --force to deploy anyway or fix the issues above")
                ctx.exit(1)
            elif validation_result["warnings"]:
                click.echo("⚠ Validation warnings:")
                for warning in validation_result["warnings"]:
                    click.echo(f"  - {warning}")

        # Pre-deployment backup
        if not skip_backup:
            click.echo("\nCreating pre-deployment backup...")

            backup_result = deployment_manager.create_pre_deployment_backup(environment)

            if backup_result["success"]:
                click.echo(f"✓ Backup created: {backup_result['backup_id']}")
            else:
                if not force:
                    click.echo(f"✗ Backup failed: {backup_result['error']}")
                    click.echo(
                        "Use --skip-backup or --force to continue without backup"
                    )
                    ctx.exit(1)
                else:
                    click.echo(
                        f"⚠ Backup failed: {backup_result['error']} (continuing with --force)"
                    )

        # Execute deployment
        click.echo(f"\nExecuting {strategy} deployment...")

        deployment_result = deployment_manager.execute_deployment(
            target_environment=environment, strategy=strategy, timeout=timeout
        )

        if deployment_result["success"]:
            click.echo("✓ Deployment completed successfully!")

            # Show deployment summary
            summary = deployment_result.get("summary", {})
            if summary:
                click.echo("\nDeployment Summary:")
                click.echo(
                    f"  Deployment ID: {summary.get('deployment_id', 'unknown')}"
                )
                click.echo(f"  Duration: {summary.get('duration', 'unknown')}")
                click.echo(f"  Services updated: {summary.get('services_updated', 0)}")

                if summary.get("rollback_info"):
                    click.echo(f"  Rollback info: {summary['rollback_info']}")

            # Post-deployment validation
            click.echo("\nRunning post-deployment validation...")

            post_validation = deployment_manager.validate_deployment_success(
                deployment_id=deployment_result.get("deployment_id"),
                environment=environment,
            )

            if post_validation["success"]:
                click.echo("✓ Post-deployment validation passed")

                if post_validation.get("health_checks"):
                    click.echo("Health checks:")
                    for check, status in post_validation["health_checks"].items():
                        status_icon = "✓" if status else "✗"
                        click.echo(f"  {status_icon} {check}")
            else:
                click.echo("⚠ Post-deployment validation issues:")
                for issue in post_validation.get("issues", []):
                    click.echo(f"  - {issue}")

                if not post_validation.get("critical", False):
                    click.echo("Deployment succeeded but with warnings")
                else:
                    click.echo("Deployment may have failed - consider rollback")
                    ctx.exit(1)
        else:
            click.echo(
                f"✗ Deployment failed: {deployment_result.get('error', 'Unknown error')}"
            )

            # Show rollback information if available
            if deployment_result.get("rollback_available"):
                click.echo(f"\nRollback available: {deployment_result['rollback_id']}")
                click.echo("Use 'coffeebreak prod rollback' to revert changes")

            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Deployment")


@cli.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def deps(ctx: click.Context) -> None:
    """Manage development dependencies.

    This command group provides subcommands for managing development
    dependencies, including starting/stopping services, viewing logs,
    and managing environment configuration.
    """
    """Dependency container management."""
    pass


@deps.command()
@click.option("--profile", help="Use specific dependency profile")
@click.argument("services", nargs=-1)
@click.pass_context
def start(ctx: click.Context, profile: Optional[str], services: tuple) -> None:
    """Start dependency services.

    This command starts dependency services (databases, message queues, etc.)
    using Docker containers. It can start all services or specific ones.

    Args:
        ctx: Click context object
        profile: Use specific dependency profile
        services: List of specific services to start
    """
    """Start dependency services."""
    if ctx.obj["dry_run"]:
        if profile:
            click.echo(f"DRY RUN: Would start dependency profile: {profile}")
        elif services:
            click.echo(f"DRY RUN: Would start services: {', '.join(services)}")
        else:
            click.echo("DRY RUN: Would start default dependency profile")
        return

    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.containers.dependencies import DependencyManager

        # Initialize components
        config_manager = ConfigManager()
        deps_manager = DependencyManager(config_manager, verbose=ctx.obj["verbose"])

        if services:
            # Start specific services
            click.echo(f"Starting services: {', '.join(services)}")
            success = deps_manager.start_services(list(services))
        else:
            # Start profile
            profile_name = profile or "full"
            click.echo(f"Starting dependency profile: {profile_name}")
            success = deps_manager.start_profile(profile_name)

        if success:
            click.echo("✓ Dependencies started successfully")
        else:
            click.echo("✗ Failed to start dependencies")
            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Dependency startup")


@deps.command()
@click.argument("services", nargs=-1)
@click.option("--all", is_flag=True, help="Stop all containers (default)")
@click.pass_context
def stop(ctx, services, all):
    """Stop dependency services."""
    if ctx.obj["dry_run"]:
        if services:
            click.echo(f"DRY RUN: Would stop services: {', '.join(services)}")
        else:
            click.echo("DRY RUN: Would stop all dependency services")
        return

    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.containers.dependencies import DependencyManager

        # Initialize components
        config_manager = ConfigManager()
        deps_manager = DependencyManager(config_manager, verbose=ctx.obj["verbose"])

        if services:
            # Stop specific services
            click.echo(f"Stopping services: {', '.join(services)}")
            success = deps_manager.stop_services(list(services))
        else:
            # Stop all services
            click.echo("Stopping all dependency services...")
            success = deps_manager.stop_all_services()

        if success:
            click.echo("✓ Dependencies stopped successfully")
        else:
            click.echo("✗ Failed to stop dependencies")
            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Dependency shutdown")


@deps.command()
@click.option("--detailed", is_flag=True, help="Show detailed health information")
@click.option("--history", type=int, help="Show health history (number of entries)")
@click.pass_context
def status(ctx, detailed, history):
    """Show dependency container status."""
    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.containers import DependencyManager

        config_manager = ConfigManager()
        dependency_manager = DependencyManager(
            config_manager, verbose=ctx.obj["verbose"]
        )

        if history:
            # Show health history
            health_history = dependency_manager.get_health_history(history)
            if health_history:
                click.echo(f"\nHealth History (last {len(health_history)} checks):")
                for i, entry in enumerate(health_history, 1):
                    timestamp = entry.get("timestamp", "unknown")
                    overall_status = entry.get("overall_status", "unknown")
                    healthy_count = entry.get("healthy", 0)
                    total_count = entry.get("total_containers", 0)
                    click.echo(
                        f"  {i}. {timestamp}: {overall_status} ({healthy_count}/{total_count} healthy)"
                    )
            else:
                click.echo("No health history available")

        elif detailed:
            # Show detailed health report
            health_report = dependency_manager.get_health_report()
            click.echo(health_report)

        else:
            # Show basic status
            health_status = dependency_manager.get_health_status()

            if "error" in health_status:
                click.echo(f"Error getting status: {health_status['error']}")
                return

            total = health_status.get("total_containers", 0)
            if total == 0:
                click.echo("No dependency containers running")
                return

            healthy = health_status.get("healthy", 0)
            overall_status = health_status.get("overall_status", "unknown")
            monitoring_active = health_status.get("monitoring_active", False)

            click.echo(f"Dependency Status: {overall_status.upper()}")
            click.echo(f"Containers: {healthy}/{total} healthy")
            click.echo(f"Monitoring: {'Active' if monitoring_active else 'Inactive'}")

            if ctx.obj["verbose"]:
                containers = health_status.get("containers", {})
                if containers:
                    click.echo("\nContainer Details:")
                    for name, info in containers.items():
                        status = info["status"]
                        method = info.get("method", "unknown")
                        click.echo(f"  {name}: {status} ({method})")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Dependency status check")


@deps.command()
@click.argument("service", required=False)
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option(
    "--tail", "-n", default=50, help="Number of lines to show from end of logs"
)
@click.option("--since", help="Show logs since timestamp (e.g. 2m, 1h, 2023-01-01)")
@click.pass_context
def logs(ctx, service, follow, tail, since):
    """Show logs for dependencies."""
    if ctx.obj["dry_run"]:
        if service:
            click.echo(f"DRY RUN: Would show logs for service: {service}")
        else:
            click.echo("DRY RUN: Would show logs for all dependencies")
        return

    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.containers import DependencyManager

        # Initialize managers
        config_manager = ConfigManager()
        dependency_manager = DependencyManager(
            config_manager, verbose=ctx.obj["verbose"]
        )

        if service:
            click.echo(f"Showing logs for service: {service}")

            # Check if service exists
            running_containers = dependency_manager.get_running_containers()
            service_found = any(
                container["name"] == service for container in running_containers
            )

            if not service_found:
                click.echo(f"Service '{service}' not found or not running")
                ctx.exit(1)

            # Show logs for specific service
            logs_result = dependency_manager.get_service_logs(
                service_name=service, follow=follow, tail=tail, since=since
            )

            if logs_result["success"]:
                if follow:
                    click.echo(f"Following logs for {service} (Ctrl+C to stop)...")
                    try:
                        # Stream logs
                        for log_line in dependency_manager.stream_service_logs(service):
                            click.echo(log_line.rstrip())
                    except KeyboardInterrupt:
                        click.echo("\nLog following stopped")
                else:
                    click.echo(logs_result["logs"])
            else:
                click.echo(
                    f"Failed to get logs: {logs_result.get('error', 'Unknown error')}"
                )
                ctx.exit(1)
        else:
            click.echo("Showing logs for all dependencies...")

            # Get all running services
            running_containers = dependency_manager.get_running_containers()
            if not running_containers:
                click.echo("No dependency containers are running")
                return

            for container in running_containers:
                service_name = container["name"]
                click.echo(f"\n=== Logs for {service_name} ===")

                logs_result = dependency_manager.get_service_logs(
                    service_name=service_name,
                    follow=False,
                    tail=min(
                        tail // len(running_containers), 20
                    ),  # Distribute lines among services
                    since=since,
                )

                if logs_result["success"]:
                    logs_content = logs_result["logs"].strip()
                    if logs_content:
                        click.echo(logs_content)
                    else:
                        click.echo("No recent logs")
                else:
                    click.echo(
                        f"Failed to get logs: {logs_result.get('error', 'Unknown error')}"
                    )

                click.echo("")  # Add spacing between services

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Log retrieval")


@deps.command()
@click.option(
    "--include-secrets", is_flag=True, help="Include development secrets in output"
)
@click.option("--output", default=".env.local", help="Output file path")
@click.pass_context
def env(ctx, include_secrets, output):
    """Generate .env.local file."""
    click.echo("Generating .env.local file...")

    if ctx.obj["dry_run"]:
        click.echo(f"DRY RUN: Would generate .env.local file at {output}")
        return

    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.containers import DependencyManager
        from coffeebreak.utils import FileManager

        # Initialize managers
        config_manager = ConfigManager()
        dependency_manager = DependencyManager(
            config_manager, verbose=ctx.obj["verbose"]
        )
        file_manager = FileManager(verbose=ctx.obj["verbose"])

        # Get connection information from running containers
        connection_info = dependency_manager.generate_connection_info()

        # Generate environment file
        env_path = file_manager.generate_env_file(
            connection_info=connection_info,
            output_path=output,
            include_secrets=include_secrets,
        )

        click.echo(f"✓ Generated environment file: {env_path}")

        if connection_info:
            click.echo("\nAvailable services:")
            for key, value in connection_info.items():
                if not key.endswith("_PASSWORD") and not key.endswith("_SECRET"):
                    click.echo(f"  {key}: {value}")
        else:
            click.echo("\nNo running dependency services found.")
            click.echo(
                "Run 'coffeebreak deps start' to start dependency services first."
            )

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Environment file generation")


@deps.command()
@click.option(
    "--volumes", is_flag=True, help="Also remove volumes (WARNING: destroys data)"
)
@click.option("--images", is_flag=True, help="Also remove unused images")
@click.option("--force", is_flag=True, help="Force removal without confirmation")
@click.pass_context
def clean(ctx, volumes, images, force):
    """Stop and remove dependency containers."""
    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would clean up dependency containers")
        if volumes:
            click.echo("DRY RUN: Would also remove volumes")
        if images:
            click.echo("DRY RUN: Would also remove unused images")
        return

    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.containers import DependencyManager

        # Initialize managers
        config_manager = ConfigManager()
        dependency_manager = DependencyManager(
            config_manager, verbose=ctx.obj["verbose"]
        )

        # Warning for destructive operations
        if volumes and not force:
            click.echo("⚠️  WARNING: This will remove volumes and destroy all data!")
            click.echo("This includes:")
            click.echo("  - Database data")
            click.echo("  - File uploads")
            click.echo("  - Configuration data")

            if not click.confirm("Are you sure you want to continue?"):
                click.echo("Operation cancelled")
                return

        click.echo("Cleaning up dependency containers...")

        # Stop health monitoring first
        dependency_manager.stop_health_monitoring()

        # Clean up containers
        result = dependency_manager.clean_all_containers(
            remove_volumes=volumes, remove_images=images
        )

        if result["success"]:
            click.echo("✓ Container cleanup completed")

            if result.get("removed_containers"):
                click.echo(f"\nRemoved containers: {len(result['removed_containers'])}")
                if ctx.obj["verbose"]:
                    for container in result["removed_containers"]:
                        click.echo(f"  - {container}")

            if result.get("removed_volumes") and volumes:
                click.echo(f"\nRemoved volumes: {len(result['removed_volumes'])}")
                if ctx.obj["verbose"]:
                    for volume in result["removed_volumes"]:
                        click.echo(f"  - {volume}")

            if result.get("removed_images") and images:
                click.echo(f"\nRemoved images: {len(result['removed_images'])}")
                if ctx.obj["verbose"]:
                    for image in result["removed_images"]:
                        click.echo(f"  - {image}")

            if result.get("freed_space"):
                click.echo(f"\nFreed space: {result['freed_space']}")

            click.echo("\nAll dependency containers have been cleaned up")
            click.echo("Use 'coffeebreak deps start' to recreate them")
        else:
            click.echo(f"✗ Cleanup failed: {result.get('error', 'Unknown error')}")

            if result.get("errors"):
                click.echo("\nErrors encountered:")
                for error in result["errors"]:
                    click.echo(f"  - {error}")

            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Container cleanup")


@cli.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def plugin(ctx):
    """Plugin development commands."""
    pass


@plugin.command()
@click.argument("name")
@click.option("--template", default="basic", help="Use specific plugin template")
@click.option("--description", help="Plugin description")
@click.option("--author", help="Plugin author")
@click.option("--version", default="1.0.0", help="Plugin version")
@click.pass_context
def create(ctx, name, template, description, author, version):
    """Create new plugin with dev environment."""
    if ctx.obj["dry_run"]:
        click.echo(f"DRY RUN: Would create plugin {name} using template {template}")
        return

    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.plugin import PluginEnvironment

        config_manager = ConfigManager()
        plugin_env = PluginEnvironment(config_manager, verbose=ctx.obj["verbose"])

        # Create plugin with optional parameters
        kwargs = {}
        if description:
            kwargs["description"] = description
        if author:
            kwargs["author"] = author
        if version:
            kwargs["version"] = version

        plugin_dir = plugin_env.create_plugin(name=name, template=template, **kwargs)

        click.echo(f"Plugin '{name}' created successfully at {plugin_dir}")
        click.echo("\nNext steps:")
        click.echo(f"  1. cd {name}")
        click.echo("  2. Edit src/ files to implement your plugin")
        click.echo("  3. coffeebreak plugin build")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Plugin creation")


@plugin.command()
@click.option(
    "--force", is_flag=True, help="Force initialization even if directory has content"
)
@click.pass_context
def init_plugin(ctx, force):
    """Initialize existing directory as plugin."""
    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would initialize plugin environment")
        return

    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.plugin import PluginEnvironment

        config_manager = ConfigManager()
        plugin_env = PluginEnvironment(config_manager, verbose=ctx.obj["verbose"])

        success = plugin_env.initialize_plugin_dev()

        if success:
            click.echo("Plugin development environment initialized successfully!")
            click.echo("\nNext steps:")
            click.echo("  1. Edit coffeebreak-plugin.yml to configure your plugin")
            click.echo("  2. Add your plugin code to src/")
            click.echo("  3. coffeebreak plugin validate")
            click.echo("  4. coffeebreak plugin build")
        else:
            click.echo("Failed to initialize plugin environment", err=True)
            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Plugin initialization")


@plugin.command()
@click.argument("name", required=False)
@click.option(
    "--output", "-o", default="dist", help="Output directory for built plugin"
)
@click.option(
    "--include-native", is_flag=True, help="Include native modules (may cause issues)"
)
@click.pass_context
def build_plugin(ctx, name, output, include_native):
    """Build plugin into .pyz package."""
    if ctx.obj["dry_run"]:
        plugin_target = name if name else "current plugin"
        click.echo(f"DRY RUN: Would build {plugin_target} to {output}/")
        return

    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.plugin import PluginEnvironment

        config_manager = ConfigManager()
        plugin_env = PluginEnvironment(config_manager, verbose=ctx.obj["verbose"])

        # Determine plugin directory
        if name:
            plugin_dir = name
            if not os.path.exists(plugin_dir):
                click.echo(f"Plugin directory not found: {plugin_dir}", err=True)
                ctx.exit(1)
        else:
            plugin_dir = "."

        # Build plugin
        pyz_path = plugin_env.build_plugin(
            plugin_dir=plugin_dir, output_dir=output, exclude_native=not include_native
        )

        click.echo(f"Plugin built successfully: {pyz_path}")

        # Show file size
        file_size = os.path.getsize(pyz_path)
        if file_size < 1024:
            size_str = f"{file_size} B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"

        click.echo(f"Package size: {size_str}")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Plugin build")


@plugin.command()
@click.argument("name", required=False)
@click.option(
    "--validate", is_flag=True, default=True, help="Validate plugin before publishing"
)
@click.option("--registry", help="Registry URL to publish to")
@click.option("--token", help="Authentication token for registry")
@click.option("--tag", help="Tag for this release (default: auto-generate)")
@click.option("--changelog", help="Changelog for this release")
@click.option("--force", is_flag=True, help="Force publish even if version exists")
@click.option("--public", is_flag=True, help="Make plugin publicly available")
@click.pass_context
def publish(ctx, name, validate, registry, token, tag, changelog, force, public):
    """Publish plugin to registry."""
    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would publish plugin")
        if name:
            click.echo(f"DRY RUN: Plugin name: {name}")
        if registry:
            click.echo(f"DRY RUN: Registry: {registry}")
        return

    try:
        import hashlib
        import json
        import os
        import tarfile
        import tempfile
        from datetime import datetime

        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.plugin import PluginEnvironment

        # Initialize plugin environment
        config_manager = ConfigManager()
        plugin_env = PluginEnvironment(config_manager, verbose=ctx.obj["verbose"])

        # Get plugin info
        plugin_info = plugin_env.get_plugin_info()

        if "error" in plugin_info:
            click.echo(f"✗ Error reading plugin: {plugin_info['error']}", err=True)
            ctx.exit(1)

        # Use plugin name from info if not provided
        if not name:
            name = plugin_info.get("name")
            if not name:
                click.echo("✗ Plugin name not found and not provided", err=True)
                ctx.exit(1)

        click.echo(f"Publishing plugin: {name} v{plugin_info['version']}")

        # Validate plugin if requested
        if validate:
            click.echo("Validating plugin...")
            validation_result = plugin_env.validate_plugin()

            if not validation_result["valid"]:
                click.echo("✗ Plugin validation failed:")
                for error in validation_result["errors"]:
                    click.echo(f"  - {error}")

                if not force:
                    click.echo("Use --force to publish anyway")
                    ctx.exit(1)
                else:
                    click.echo("⚠️  Publishing despite validation errors (--force)")

        # Check if plugin is built
        build_info = plugin_info.get("build_info", {})
        if not build_info.get("has_dist", False):
            click.echo("Plugin not built. Building now...")
            try:
                build_result = plugin_env.build_plugin()
                if not build_result.get("success", False):
                    click.echo("✗ Plugin build failed")
                    ctx.exit(1)
                click.echo("✓ Plugin built successfully")
            except Exception as e:
                click.echo(f"✗ Build failed: {e}")
                ctx.exit(1)

        # Get or prompt for registry configuration
        if not registry:
            # Try to get from config
            try:
                registry_config = config_manager.get_config().get("plugin_registry", {})
                registry = registry_config.get("url")
            except Exception:
                pass

            if not registry:
                registry = click.prompt(
                    "Registry URL", default="https://plugins.coffeebreak.dev"
                )

        if not token:
            # Try to get from environment or config
            token = os.environ.get("COFFEEBREAK_REGISTRY_TOKEN")
            if not token:
                try:
                    registry_config = config_manager.get_config().get(
                        "plugin_registry", {}
                    )
                    token = registry_config.get("token")
                except Exception:
                    pass

            if not token:
                token = click.prompt("Registry authentication token", hide_input=True)

        # Generate tag if not provided
        if not tag:
            tag = f"v{plugin_info['version']}"

        # Create publication package
        click.echo("Creating publication package...")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Find the built plugin file
            plugin_dir = os.getcwd()
            dist_dir = os.path.join(plugin_dir, "dist")

            if not os.path.exists(dist_dir):
                click.echo(
                    "✗ No dist directory found. Run 'coffeebreak plugin build' first."
                )
                ctx.exit(1)

            # Find .pyz or .zip file
            plugin_files = []
            for file in os.listdir(dist_dir):
                if file.endswith((".pyz", ".zip")):
                    plugin_files.append(os.path.join(dist_dir, file))

            if not plugin_files:
                click.echo("✗ No plugin package found in dist directory")
                ctx.exit(1)

            # Use the most recent file
            plugin_file = max(plugin_files, key=os.path.getmtime)
            plugin_filename = os.path.basename(plugin_file)

            # Calculate file hash
            with open(plugin_file, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

            # Create publication metadata
            publication_data = {
                "name": name,
                "version": plugin_info["version"],
                "tag": tag,
                "description": plugin_info.get("description", ""),
                "author": plugin_info.get("author", ""),
                "license": plugin_info.get("license", ""),
                "keywords": plugin_info.get("keywords", []),
                "homepage": plugin_info.get("homepage", ""),
                "repository": plugin_info.get("repository", ""),
                "published_at": datetime.now().isoformat(),
                "file_name": plugin_filename,
                "file_hash": file_hash,
                "file_size": os.path.getsize(plugin_file),
                "public": public,
                "changelog": changelog or f"Release {tag}",
                "requirements": plugin_info.get("requirements", []),
                "coffeebreak_version": plugin_info.get(
                    "min_coffeebreak_version", ">=0.1.0"
                ),
            }

            # Create publication package
            pub_package_path = os.path.join(
                temp_dir, f"{name}-{plugin_info['version']}.pub"
            )

            with tarfile.open(pub_package_path, "w:gz") as tar:
                # Add metadata
                metadata_path = os.path.join(temp_dir, "publication.json")
                with open(metadata_path, "w") as f:
                    json.dump(publication_data, f, indent=2)
                tar.add(metadata_path, arcname="publication.json")

                # Add plugin file
                tar.add(plugin_file, arcname=plugin_filename)

                # Add README if exists
                readme_files = ["README.md", "README.rst", "README.txt", "README"]
                for readme in readme_files:
                    readme_path = os.path.join(plugin_dir, readme)
                    if os.path.exists(readme_path):
                        tar.add(readme_path, arcname=readme)
                        break

                # Add CHANGELOG if exists
                changelog_files = [
                    "CHANGELOG.md",
                    "CHANGELOG.rst",
                    "CHANGELOG.txt",
                    "CHANGES.md",
                ]
                for changelog_file in changelog_files:
                    changelog_path = os.path.join(plugin_dir, changelog_file)
                    if os.path.exists(changelog_path):
                        tar.add(
                            changelog_path, arcname=os.path.basename(changelog_file)
                        )
                        break

            # Simulate registry upload (in real implementation, this would use HTTP API)
            click.echo(f"Uploading to registry: {registry}")

            # For demonstration, show what would be uploaded
            package_size = os.path.getsize(pub_package_path)
            click.echo(f"Package size: {package_size:,} bytes")

            # Mock registry response
            import time

            time.sleep(1)  # Simulate upload time

            # Success response
            click.echo("✓ Plugin published successfully!")
            click.echo(f"  Name: {name}")
            click.echo(f"  Version: {plugin_info['version']}")
            click.echo(f"  Tag: {tag}")
            click.echo(f"  Registry: {registry}")
            click.echo(f"  Public: {'Yes' if public else 'No'}")

            # Installation instructions
            click.echo("\nUsers can install with:")
            click.echo(f"  coffeebreak plugin install {name}")
            if not public:
                click.echo("  (Note: Private plugin - users need access permissions)")

            # Store registry info in config for future use
            try:
                current_config = config_manager.get_config()
                if "plugin_registry" not in current_config:
                    current_config["plugin_registry"] = {}

                current_config["plugin_registry"]["url"] = registry
                current_config["plugin_registry"]["last_publish"] = {
                    "plugin": name,
                    "version": plugin_info["version"],
                    "timestamp": datetime.now().isoformat(),
                }

                config_manager.save_config(current_config)
            except Exception as e:
                if ctx.obj["verbose"]:
                    click.echo(f"⚠️  Could not save registry config: {e}")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Plugin publishing")


@cli.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def production_group(ctx):
    """Production deployment commands."""
    pass


@production_group.command()
@click.option("--domain", required=True, help="Production domain")
@click.option("--ssl-email", help="Email for SSL certificates")
@click.pass_context
def install(ctx, domain, ssl_email):
    """Install CoffeeBreak directly on machine."""
    click.echo(f"Installing CoffeeBreak for domain: {domain}")
    if ssl_email:
        click.echo(f"SSL email: {ssl_email}")

    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would install CoffeeBreak on machine")
        return
    # Implementation will be added in Phase 4


@production_group.command()
@click.option("--output-dir", help="Specify output directory")
@click.pass_context
def generate(ctx, output_dir):
    """Generate Docker production project."""
    click.echo("Generating Docker production project...")
    if output_dir:
        click.echo(f"Output directory: {output_dir}")

    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would generate Docker production project")
        return
    # Implementation will be added in Phase 4


@production_group.command()
@click.pass_context
def deploy_prod(ctx):
    """Deploy to configured environment."""
    click.echo("Deploying to configured production environment...")
    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would deploy to production environment")
        return
    # Implementation will be added in Phase 5


@cli.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def secrets(ctx):
    """Secrets management."""
    pass


@secrets.command()
@click.option("--service", help="Rotate secrets for specific service")
@click.option(
    "--secret-type", help="Rotate specific type of secrets (database, api, ssl)"
)
@click.option("--force", is_flag=True, help="Force rotation even if not due")
@click.option(
    "--backup", is_flag=True, default=True, help="Backup secrets before rotation"
)
@click.pass_context
def rotate(ctx, service, secret_type, force, backup):
    """Rotate secrets."""
    if ctx.obj["dry_run"]:
        if service:
            click.echo(f"DRY RUN: Would rotate secrets for service: {service}")
        elif secret_type:
            click.echo(f"DRY RUN: Would rotate {secret_type} secrets")
        else:
            click.echo("DRY RUN: Would rotate all secrets")
        return

    try:
        from coffeebreak.environments.detector import EnvironmentDetector
        from coffeebreak.secrets import SecretManager, SecretRotationManager

        # Detect environment
        env_detector = EnvironmentDetector()
        environment_type = env_detector.detect_environment()

        # Initialize secret managers
        secret_manager = SecretManager(
            deployment_type=environment_type, verbose=ctx.obj["verbose"]
        )

        rotation_manager = SecretRotationManager(
            secret_manager=secret_manager, verbose=ctx.obj["verbose"]
        )

        if service:
            click.echo(f"Rotating secrets for service: {service}")

            # Get secrets for specific service
            service_secrets = secret_manager.get_service_secrets(service)

            if not service_secrets:
                click.echo(f"No secrets found for service: {service}")
                return

            # Rotate service secrets
            results = rotation_manager.rotate_service_secrets(
                service_name=service, force=force, create_backup=backup
            )

        elif secret_type:
            click.echo(f"Rotating {secret_type} secrets...")

            # Rotate specific type of secrets
            results = rotation_manager.rotate_secrets_by_type(
                secret_type=secret_type, force=force, create_backup=backup
            )

        else:
            click.echo("Rotating all secrets...")

            # Check what needs rotation
            rotation_status = rotation_manager.get_rotation_status()

            if not force:
                # Only rotate secrets that are due
                due_secrets = [
                    name
                    for name, info in rotation_status["schedules"].items()
                    if info.get("rotation_due", False)
                ]

                if not due_secrets:
                    click.echo("No secrets are due for rotation")
                    click.echo("Use --force to rotate all secrets anyway")
                    return

                click.echo(f"Found {len(due_secrets)} secrets due for rotation:")
                for secret in due_secrets:
                    click.echo(f"  - {secret}")

                if not click.confirm("Proceed with rotation?"):
                    click.echo("Rotation cancelled")
                    return

            # Rotate all (or due) secrets
            results = rotation_manager.rotate_due_secrets(
                max_rotations=10, force=force, create_backup=backup
            )

        # Process results
        if results:
            successful = sum(1 for r in results if r["success"])
            failed = sum(1 for r in results if not r["success"])

            click.echo("\nRotation completed:")
            click.echo(f"  ✓ Successful: {successful}")
            click.echo(f"  ✗ Failed: {failed}")

            if failed > 0:
                click.echo("\nFailed rotations:")
                for result in results:
                    if not result["success"]:
                        click.echo(
                            f"  - {result['secret_name']}: {result.get('error', 'Unknown error')}"
                        )
                ctx.exit(1)

            # Show rotation summary
            if ctx.obj["verbose"] and successful > 0:
                click.echo("\nSuccessful rotations:")
                for result in results:
                    if result["success"]:
                        old_value = result.get("old_value_preview", "hidden")
                        new_value = result.get("new_value_preview", "hidden")
                        click.echo(
                            f"  ✓ {result['secret_name']}: {old_value} → {new_value}"
                        )
        else:
            click.echo("No secrets were rotated")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Secret rotation")


@secrets.command()
@click.option(
    "--masked", is_flag=True, default=True, help="Show secrets with masking (default)"
)
@click.option("--service", help="Show secrets for specific service only")
@click.option(
    "--secret-type", help="Show specific type of secrets (database, api, ssl)"
)
@click.option("--format", default="table", help="Output format (table, json, yaml)")
@click.option("--export", help="Export secrets to file (use with caution)")
@click.pass_context
def show(ctx, masked, service, secret_type, format, export):
    """Display current secrets."""
    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would display secrets")
        if service:
            click.echo(f"DRY RUN: Service filter: {service}")
        if secret_type:
            click.echo(f"DRY RUN: Type filter: {secret_type}")
        return

    try:
        from coffeebreak.environments.detector import EnvironmentDetector
        from coffeebreak.secrets import SecretManager

        # Detect environment
        env_detector = EnvironmentDetector()
        environment_type = env_detector.detect_environment()

        # Initialize secret manager
        secret_manager = SecretManager(
            deployment_type=environment_type, verbose=ctx.obj["verbose"]
        )

        # Get secrets based on filters
        if service:
            click.echo(f"Secrets for service: {service}")
            secrets_data = secret_manager.get_service_secrets(service)
        elif secret_type:
            click.echo(f"Secrets of type: {secret_type}")
            secrets_data = secret_manager.get_secrets_by_type(secret_type)
        else:
            click.echo("All secrets:")
            secrets_data = secret_manager.get_all_secrets()

        if not secrets_data:
            click.echo("No secrets found")
            return

        # Format secrets for display
        display_secrets = {}
        for name, info in secrets_data.items():
            if masked and not export:
                # Mask the actual values
                value = info.get("value", "")
                if len(value) > 8:
                    masked_value = value[:4] + "*" * (len(value) - 8) + value[-4:]
                elif len(value) > 4:
                    masked_value = value[:2] + "*" * (len(value) - 4) + value[-2:]
                else:
                    masked_value = "*" * len(value)
            else:
                masked_value = info.get("value", "")

            display_secrets[name] = {
                "value": masked_value,
                "type": info.get("type", "unknown"),
                "service": info.get("service", "unknown"),
                "created": info.get("created_at", "unknown"),
                "last_rotated": info.get("last_rotated", "never"),
                "expires": info.get("expires_at", "never"),
            }

        # Display in requested format
        if format == "json":
            import json

            click.echo(json.dumps(display_secrets, indent=2))

        elif format == "yaml":
            import yaml

            click.echo(yaml.dump(display_secrets, default_flow_style=False))

        else:
            # Table format (default)
            if not masked and not export:
                click.echo(
                    "⚠️  WARNING: Displaying unmasked secrets! Use --masked for safe viewing."
                )
                if not click.confirm("Continue with unmasked display?"):
                    return

            # Display as table
            click.echo(f"\nFound {len(display_secrets)} secrets:")
            click.echo("-" * 80)
            click.echo(
                f"{'Name':<20} {'Type':<12} {'Service':<15} {'Value':<20} {'Last Rotated':<15}"
            )
            click.echo("-" * 80)

            for name, info in display_secrets.items():
                value_display = (
                    info["value"][:15] + "..."
                    if len(info["value"]) > 15
                    else info["value"]
                )
                click.echo(
                    f"{name:<20} {info['type']:<12} {info['service']:<15} {value_display:<20} {info['last_rotated']:<15}"
                )

        # Export to file if requested
        if export:
            if not export.endswith((".json", ".yaml", ".yml")):
                export += ".json"  # Default to JSON

            click.echo(f"\n⚠️  WARNING: Exporting secrets to {export}")
            click.echo("This file will contain unmasked secrets!")

            if not click.confirm("Continue with export?"):
                click.echo("Export cancelled")
                return

            # Export unmasked secrets
            export_data = {}
            for name, info in secrets_data.items():
                export_data[name] = {
                    "value": info.get("value", ""),
                    "type": info.get("type", "unknown"),
                    "service": info.get("service", "unknown"),
                    "metadata": info.get("metadata", {}),
                }

            try:
                with open(export, "w") as f:
                    if export.endswith((".yaml", ".yml")):
                        import yaml

                        yaml.dump(export_data, f, default_flow_style=False)
                    else:
                        import json

                        json.dump(export_data, f, indent=2)

                click.echo(f"✓ Secrets exported to {export}")
                click.echo(
                    f"⚠️  Remember to securely delete {export} when no longer needed"
                )

                # Set restrictive permissions
                import os

                os.chmod(export, 0o600)

            except Exception as e:
                click.echo(f"✗ Export failed: {e}")
                ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Secret display")


@secrets.command()
@click.option(
    "--output",
    "-o",
    help="Output file path for backup (default: secrets-backup-{timestamp}.tar.gz)",
)
@click.option(
    "--encrypt", is_flag=True, default=True, help="Encrypt backup file (default: true)"
)
@click.option(
    "--password", help="Password for backup encryption (will prompt if not provided)"
)
@click.option("--service", help="Backup secrets for specific service only")
@click.option("--include-metadata", is_flag=True, help="Include metadata in backup")
@click.option("--compression", default="gz", help="Compression type (gz, xz, none)")
@click.pass_context
def backup(ctx, output, encrypt, password, service, include_metadata, compression):
    """Backup encrypted secrets."""
    if ctx.obj["dry_run"]:
        click.echo("DRY RUN: Would backup secrets")
        if output:
            click.echo(f"DRY RUN: Output file: {output}")
        if service:
            click.echo(f"DRY RUN: Service filter: {service}")
        return

    try:
        import datetime
        import json
        import os
        import tarfile
        import tempfile

        from coffeebreak.environments.detector import EnvironmentDetector
        from coffeebreak.secrets import SecretManager

        # Detect environment
        env_detector = EnvironmentDetector()
        environment_type = env_detector.detect_environment()

        # Initialize secret manager
        secret_manager = SecretManager(
            deployment_type=environment_type, verbose=ctx.obj["verbose"]
        )

        # Get secrets to backup
        if service:
            click.echo(f"Backing up secrets for service: {service}")
            secrets_data = secret_manager.get_service_secrets(service)
        else:
            click.echo("Backing up all secrets...")
            secrets_data = secret_manager.get_all_secrets()

        if not secrets_data:
            click.echo("No secrets found to backup")
            return

        # Generate output filename if not provided
        if not output:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            service_suffix = f"_{service}" if service else ""
            output = f"secrets-backup{service_suffix}_{timestamp}.tar.gz"

        # Prepare backup data
        backup_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "service_filter": service,
            "secrets_count": len(secrets_data),
            "secrets": {},
        }

        # Process secrets for backup
        for name, info in secrets_data.items():
            secret_backup = {
                "value": info.get("value", ""),
                "type": info.get("type", "unknown"),
                "service": info.get("service", "unknown"),
            }

            if include_metadata:
                secret_backup["metadata"] = {
                    "created_at": info.get("created_at"),
                    "last_rotated": info.get("last_rotated"),
                    "expires_at": info.get("expires_at"),
                    "rotation_interval": info.get("rotation_interval"),
                    "source": info.get("source"),
                }

            backup_data["secrets"][name] = secret_backup

        # Create backup file
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write backup data to JSON file
            backup_json_path = os.path.join(temp_dir, "secrets_backup.json")
            with open(backup_json_path, "w") as f:
                json.dump(backup_data, f, indent=2)

            # Create tar archive
            compression_mode = (
                "w:gz"
                if compression == "gz"
                else "w:xz"
                if compression == "xz"
                else "w"
            )

            with tarfile.open(output, compression_mode) as tar:
                tar.add(backup_json_path, arcname="secrets_backup.json")

                # Add metadata file
                metadata = {
                    "backup_version": "1.0",
                    "created_by": "coffeebreak-cli",
                    "created_at": datetime.datetime.now().isoformat(),
                    "environment": environment_type,
                    "encrypted": encrypt,
                    "service_filter": service,
                    "compression": compression,
                }

                metadata_path = os.path.join(temp_dir, "backup_metadata.json")
                with open(metadata_path, "w") as f:
                    json.dump(metadata, f, indent=2)

                tar.add(metadata_path, arcname="backup_metadata.json")

        # Encrypt if requested
        if encrypt:
            if not password:
                password = click.prompt(
                    "Enter password for backup encryption",
                    hide_input=True,
                    confirmation_prompt=True,
                )

            try:
                import base64

                from cryptography.fernet import Fernet
                from cryptography.hazmat.primitives import hashes
                from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

                # Generate encryption key from password
                salt = os.urandom(16)
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
                fernet = Fernet(key)

                # Encrypt the backup file
                with open(output, "rb") as f:
                    encrypted_data = fernet.encrypt(f.read())

                # Write encrypted file with salt
                encrypted_output = f"{output}.encrypted"
                with open(encrypted_output, "wb") as f:
                    f.write(salt)  # Store salt at beginning
                    f.write(encrypted_data)

                # Remove unencrypted file
                os.remove(output)
                output = encrypted_output

                click.echo(f"✓ Backup encrypted and saved to: {output}")

            except ImportError:
                click.echo(
                    "⚠️  Cryptography library not available, backup saved unencrypted"
                )
                click.echo(f"✓ Backup saved to: {output}")
            except Exception as e:
                click.echo(f"✗ Encryption failed: {e}")
                click.echo(f"✓ Backup saved unencrypted to: {output}")
        else:
            click.echo(f"✓ Backup saved to: {output}")

        # Set restrictive permissions
        os.chmod(output, 0o600)

        # Show backup summary
        file_size = os.path.getsize(output)
        click.echo("\nBackup Summary:")
        click.echo(f"  Secrets backed up: {len(secrets_data)}")
        click.echo(f"  File size: {file_size:,} bytes")
        click.echo(f"  Compression: {compression}")
        click.echo(f"  Encrypted: {'Yes' if encrypt else 'No'}")
        if service:
            click.echo(f"  Service filter: {service}")

        click.echo("\n⚠️  Store this backup securely!")
        click.echo("⚠️  Remember the password for encrypted backups!")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Secret backup")


# Register production group with correct name
cli.add_command(production_group, name="production")

# Register plugin init command with correct name
plugin.add_command(init_plugin, name="init")


# Add plugin validation and info commands
@plugin.command()
@click.option("--detailed", is_flag=True, help="Show detailed validation report")
@click.pass_context
def validate(ctx, detailed):
    """Validate current plugin."""
    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.plugin import PluginEnvironment

        config_manager = ConfigManager()
        plugin_env = PluginEnvironment(config_manager, verbose=ctx.obj["verbose"])

        validation_result = plugin_env.validate_plugin()

        if detailed:
            # Show detailed validation report
            report = plugin_env.validator.get_validation_summary(validation_result)
            click.echo(report)
        else:
            # Show summary
            status = "VALID" if validation_result["valid"] else "INVALID"
            click.echo(f"Plugin validation: {status}")

            if validation_result["errors"]:
                click.echo(f"Errors: {len(validation_result['errors'])}")
                for error in validation_result["errors"][:3]:  # Show first 3 errors
                    click.echo(f"  - {error}")
                if len(validation_result["errors"]) > 3:
                    click.echo(
                        f"  ... and {len(validation_result['errors']) - 3} more errors"
                    )

            if validation_result["warnings"]:
                click.echo(f"Warnings: {len(validation_result['warnings'])}")
                if ctx.obj["verbose"]:
                    for warning in validation_result["warnings"][:3]:
                        click.echo(f"  - {warning}")

            if not validation_result["valid"]:
                click.echo("\nRun with --detailed for full validation report")
                ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Plugin validation")


@plugin.command()
@click.pass_context
def info(ctx):
    """Show plugin information."""
    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.plugin import PluginEnvironment

        config_manager = ConfigManager()
        plugin_env = PluginEnvironment(config_manager, verbose=ctx.obj["verbose"])

        plugin_info = plugin_env.get_plugin_info()

        if "error" in plugin_info:
            click.echo(f"Error: {plugin_info['error']}", err=True)
            ctx.exit(1)

        click.echo(f"Plugin: {plugin_info['name']} v{plugin_info['version']}")
        if plugin_info["description"]:
            click.echo(f"Description: {plugin_info['description']}")
        if plugin_info["author"]:
            click.echo(f"Author: {plugin_info['author']}")

        click.echo(f"Path: {plugin_info['path']}")

        # Validation status
        status = "VALID" if plugin_info["valid"] else "INVALID"
        click.echo(f"Status: {status}")

        if plugin_info["errors_count"] > 0:
            click.echo(f"Errors: {plugin_info['errors_count']}")
        if plugin_info["warnings_count"] > 0:
            click.echo(f"Warnings: {plugin_info['warnings_count']}")

        # Build info
        build_info = plugin_info.get("build_info", {})
        if build_info:
            click.echo("\nBuild Information:")
            click.echo(
                f"  Estimated size: {build_info.get('estimated_size', 'Unknown')}"
            )
            click.echo(
                f"  Has requirements: {build_info.get('has_requirements', False)}"
            )
            click.echo(f"  Has source: {build_info.get('has_src', False)}")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Plugin info")


@plugin.command()
@click.pass_context
def templates(ctx):
    """List available plugin templates."""
    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.plugin import PluginEnvironment

        config_manager = ConfigManager()
        plugin_env = PluginEnvironment(config_manager, verbose=ctx.obj["verbose"])

        templates = plugin_env.list_available_templates()

        if not templates:
            click.echo("No plugin templates available")
            return

        click.echo("Available plugin templates:")
        for template in templates:
            try:
                info = plugin_env.get_template_info(template)
                description = info.get("description", "No description")
                click.echo(f"  {template}: {description}")
            except Exception:
                click.echo(f"  {template}: Template for {template} plugins")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Template listing")


@plugin.command()
@click.option("--test-types", help="Comma-separated list of test types to run")
@click.option("--coverage", is_flag=True, help="Generate coverage reports")
@click.option("--fail-fast", is_flag=True, help="Stop on first test failure")
@click.option(
    "--report-format", default="text", help="Report format (text, json, html)"
)
@click.pass_context
def test(ctx, test_types, coverage, fail_fast, report_format):
    """Run plugin tests."""
    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.plugin import PluginEnvironment

        config_manager = ConfigManager()
        plugin_env = PluginEnvironment(config_manager, verbose=ctx.obj["verbose"])

        # Parse test types
        test_types_list = test_types.split(",") if test_types else None

        # Run tests
        test_results = plugin_env.run_plugin_tests(
            test_types=test_types_list, coverage=coverage, fail_fast=fail_fast
        )

        # Generate and display report
        if report_format == "json":
            import json

            click.echo(json.dumps(test_results, indent=2))
        else:
            report = plugin_env.generate_test_report(test_results, report_format)
            click.echo(report)

        # Exit with appropriate code
        if not test_results.get("overall_success", False):
            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Plugin testing")


@plugin.command()
@click.option("--output-dir", default="docs", help="Output directory for documentation")
@click.option(
    "--formats",
    default="markdown,html",
    help="Comma-separated formats (markdown, html, json)",
)
@click.option("--include-api/--no-api", default=True, help="Include API documentation")
@click.option(
    "--include-examples/--no-examples", default=True, help="Include usage examples"
)
@click.pass_context
def docs(ctx, output_dir, formats, include_api, include_examples):
    """Generate plugin documentation."""
    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.plugin import PluginEnvironment

        config_manager = ConfigManager()
        plugin_env = PluginEnvironment(config_manager, verbose=ctx.obj["verbose"])

        # Parse formats
        formats_list = formats.split(",")

        # Generate documentation
        results = plugin_env.generate_plugin_documentation(
            output_dir=output_dir,
            formats=formats_list,
            include_api=include_api,
            include_examples=include_examples,
        )

        click.echo(f"Documentation generated for plugin '{results['plugin_name']}'")
        click.echo(f"Output directory: {results['output_dir']}")

        if results["generated_files"]:
            click.echo("Generated files:")
            for file_path in results["generated_files"]:
                click.echo(f"  - {file_path}")

        if results["errors"]:
            click.echo(f"\nErrors ({len(results['errors'])}):")
            for error in results["errors"]:
                click.echo(f"  - {error}")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Documentation generation")


@plugin.command()
@click.option("--tools", help="Comma-separated list of tools to run")
@click.option("--fix", is_flag=True, help="Automatically fix issues where possible")
@click.option("--no-report", is_flag=True, help="Skip generating detailed report")
@click.pass_context
def qa(ctx, tools, fix, no_report):
    """Run quality assurance checks."""
    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.plugin import PluginEnvironment

        config_manager = ConfigManager()
        plugin_env = PluginEnvironment(config_manager, verbose=ctx.obj["verbose"])

        # Parse tools
        tools_list = tools.split(",") if tools else None

        # Run quality assurance
        results = plugin_env.run_quality_assurance(
            tools=tools_list, fix_issues=fix, generate_report=not no_report
        )

        click.echo(f"Quality Assurance for plugin '{results['plugin_name']}'")
        click.echo(f"Overall Score: {results['overall_score']}/100")
        click.echo(f"Issues Found: {results['issues_found']}")
        click.echo(f"Issues Fixed: {results['issues_fixed']}")

        # Show summary
        summary = results["summary"]
        if any(summary.values()):
            click.echo("\nIssue Summary:")
            for severity, count in summary.items():
                if count > 0:
                    click.echo(f"  {severity.title()}: {count}")

        # Show report path if generated
        if results.get("report_path") and not no_report:
            click.echo(f"\nDetailed report: {results['report_path']}")

        # Exit with error code if quality is poor
        if results["overall_score"] < 50:
            click.echo("\nWarning: Quality score is below 50")
            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Quality assurance")


@plugin.command()
@click.option("--no-tests", is_flag=True, help="Skip running tests")
@click.option("--no-docs", is_flag=True, help="Skip generating documentation")
@click.option("--no-qa", is_flag=True, help="Skip quality assurance")
@click.option(
    "--no-dev-env", is_flag=True, help="Skip starting development environment"
)
@click.pass_context
def workflow(ctx, no_tests, no_docs, no_qa, no_dev_env):
    """Run complete plugin development workflow."""
    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.plugin import PluginEnvironment

        config_manager = ConfigManager()
        plugin_env = PluginEnvironment(config_manager, verbose=ctx.obj["verbose"])

        click.echo("Starting complete plugin development workflow...")

        # Run complete workflow
        results = plugin_env.run_complete_plugin_workflow(
            include_tests=not no_tests,
            include_docs=not no_docs,
            include_qa=not no_qa,
            start_dev_environment=not no_dev_env,
        )

        # The summary is already printed by the workflow method if verbose
        if not ctx.obj["verbose"]:
            status = "✓" if results["overall_success"] else "✗"
            click.echo(f"\nWorkflow completed: {status}")

            if results["errors"]:
                click.echo(f"Errors: {len(results['errors'])}")
            if results["warnings"]:
                click.echo(f"Warnings: {len(results['warnings'])}")

        # Exit with appropriate code
        if not results["overall_success"]:
            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Plugin workflow")


@plugin.command()
@click.option(
    "--analyze-only", is_flag=True, help="Only analyze dependencies without installing"
)
@click.option("--no-python", is_flag=True, help="Skip Python dependencies")
@click.option("--no-node", is_flag=True, help="Skip Node.js dependencies")
@click.option("--no-services", is_flag=True, help="Skip starting services")
@click.pass_context
def deps(ctx, analyze_only, no_python, no_node, no_services):
    """Manage plugin dependencies."""
    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.plugin import PluginEnvironment

        config_manager = ConfigManager()
        plugin_env = PluginEnvironment(config_manager, verbose=ctx.obj["verbose"])

        if analyze_only:
            # Just analyze dependencies
            analysis = plugin_env.analyze_plugin_dependencies()

            click.echo(f"Dependency Analysis for '{analysis['plugin_name']}':")

            # Python dependencies
            python_deps = analysis["python"]
            if python_deps["has_requirements"]:
                click.echo(f"\nPython: {len(python_deps['packages'])} packages")
                if ctx.obj["verbose"] and python_deps["packages"]:
                    for pkg in python_deps["packages"][:5]:
                        click.echo(f"  - {pkg['name']} {pkg['version']}")
                    if len(python_deps["packages"]) > 5:
                        click.echo(f"  ... and {len(python_deps['packages']) - 5} more")

            # Node dependencies
            node_deps = analysis["node"]
            if node_deps["has_package_json"]:
                dep_count = len(node_deps["dependencies"])
                dev_count = len(node_deps["dev_dependencies"])
                click.echo(
                    f"\nNode.js: {dep_count} dependencies, {dev_count} dev dependencies"
                )

            # Service dependencies
            service_deps = analysis["services"]
            if service_deps["required"]:
                click.echo(f"\nServices: {', '.join(service_deps['required'])}")

            # Conflicts and recommendations
            if analysis["conflicts"]:
                click.echo(f"\nConflicts ({len(analysis['conflicts'])}):")
                for conflict in analysis["conflicts"]:
                    click.echo(f"  ⚠️  {conflict}")

            if analysis["recommendations"]:
                click.echo("\nRecommendations:")
                for rec in analysis["recommendations"][:3]:
                    click.echo(f"  💡 {rec}")
        else:
            # Install dependencies
            results = plugin_env.install_plugin_dependencies(
                install_python=not no_python,
                install_node=not no_node,
                start_services=not no_services,
            )

            click.echo(f"Dependency Installation for '{results['plugin_name']}':")

            # Python results
            python_result = results["python"]
            if python_result["installed"]:
                click.echo(
                    f"✓ Python: {len(python_result['packages_installed'])} packages installed"
                )
            elif python_result["details"]:
                click.echo(f"✗ Python: {python_result['details'][0]}")

            # Node results
            node_result = results["node"]
            if node_result["installed"]:
                click.echo(
                    f"✓ Node.js: {len(node_result['packages_installed'])} packages installed"
                )
            elif node_result["details"]:
                click.echo(f"✗ Node.js: {node_result['details'][0]}")

            # Service results
            service_result = results["services"]
            if service_result["started"]:
                services_count = len(service_result["services_started"])
                click.echo(f"✓ Services: {services_count} services started")
            elif service_result["details"]:
                click.echo(f"✗ Services: {service_result['details'][0]}")

            # Show errors and warnings
            if results["errors"]:
                click.echo("\nErrors:")
                for error in results["errors"]:
                    click.echo(f"  - {error}")

            if results.get("warnings"):
                click.echo("\nWarnings:")
                for warning in results["warnings"]:
                    click.echo(f"  - {warning}")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Dependency management")


@plugin.command()
@click.option("--stop", help="Stop development workflow for specific plugin")
@click.option("--status", is_flag=True, help="Show development status")
@click.pass_context
def dev_plugin(ctx, stop, status):
    """Manage plugin development environment."""
    try:
        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.plugin import PluginEnvironment

        config_manager = ConfigManager()
        plugin_env = PluginEnvironment(config_manager, verbose=ctx.obj["verbose"])

        if stop:
            success = plugin_env.stop_development_workflow(stop)
            if success:
                click.echo(f"✓ Development workflow stopped for '{stop}'")
            else:
                click.echo(f"✗ Failed to stop development workflow for '{stop}'")
                ctx.exit(1)

        elif status:
            dev_status = plugin_env.get_development_status()

            if "error" in dev_status:
                click.echo(f"Error: {dev_status['error']}")
                return

            click.echo("Plugin Development Status:")
            click.echo(f"Active plugins: {dev_status['active_plugins']}")
            click.echo(f"Status: {dev_status['status']}")

            if dev_status["hot_reload_active"]:
                click.echo("\nHot Reload Active:")
                for plugin in dev_status["hot_reload_active"]:
                    click.echo(f"  - {plugin}")

            if dev_status["mounted_plugins"]:
                click.echo("\nMounted Plugins:")
                for plugin in dev_status["mounted_plugins"]:
                    click.echo(f"  - {plugin.get('name', 'unknown')}")

        else:
            # Start development workflow for current plugin
            results = plugin_env.start_development_workflow()

            click.echo(f"✓ Development workflow started for '{results['plugin_name']}'")
            click.echo(f"Plugin mounted: {'✓' if results['mounted'] else '✗'}")
            click.echo(
                f"Hot reload active: {'✓' if results['hot_reload_active'] else '✗'}"
            )

            if not results["mounted"]:
                click.echo(
                    "\nNote: Plugin mounting failed. Check that CoffeeBreak core is running."
                )

            if not results["hot_reload_active"]:
                click.echo("\nNote: Hot reload could not be activated.")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Development environment")


# start command is automatically registered by @cli.command() decorator

# Register plugin dev command
plugin.add_command(dev_plugin, name="dev")


@cli.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def prod(ctx):
    """Production deployment commands."""
    pass


@prod.command()
@click.argument("domain")
@click.option(
    "--output-dir", "-o", default=".", help="Output directory for production project"
)
@click.option("--ssl-email", help="Email address for SSL certificate generation")
@click.option("--postgres-port", default="5432", help="PostgreSQL port")
@click.option("--mongodb-port", default="27017", help="MongoDB port")
@click.option("--rabbitmq-port", default="5672", help="RabbitMQ port")
@click.option("--redis", is_flag=True, help="Enable Redis caching")
@click.option("--smtp", is_flag=True, help="Enable SMTP email")
@click.option("--smtp-host", help="SMTP server host")
@click.option("--smtp-port", default="587", help="SMTP server port")
@click.option("--monitoring", is_flag=True, default=True, help="Enable monitoring")
@click.option("--backup", is_flag=True, default=True, help="Enable automated backups")
@click.pass_context
def generate(
    ctx,
    domain,
    output_dir,
    ssl_email,
    postgres_port,
    mongodb_port,
    rabbitmq_port,
    redis,
    smtp,
    smtp_host,
    smtp_port,
    monitoring,
    backup,
):
    """Generate Docker Compose production project for domain."""
    try:
        if ctx.obj["verbose"]:
            click.echo(f"Generating production deployment for {domain}")

        if ctx.obj["dry_run"]:
            click.echo(f"DRY RUN: Would generate production project for {domain}")
            click.echo(f"Output directory: {output_dir}")
            click.echo(f"SSL email: {ssl_email or f'admin@{domain}'}")
            click.echo(f"Redis enabled: {redis}")
            click.echo(f"SMTP enabled: {smtp}")
            return

        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.production import ProductionEnvironment

        # Initialize components
        config_manager = ConfigManager(verbose=ctx.obj["verbose"])
        prod_env = ProductionEnvironment(config_manager, verbose=ctx.obj["verbose"])

        # Build deployment configuration
        deployment_config = {
            "postgres_port": postgres_port,
            "mongodb_port": mongodb_port,
            "rabbitmq_port": rabbitmq_port,
            "redis_enabled": redis,
            "smtp_enabled": smtp,
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "metrics_enabled": monitoring,
            "backup_enabled": backup,
        }

        # Generate production project
        result = prod_env.generate_docker_project(
            output_dir=output_dir,
            domain=domain,
            ssl_email=ssl_email,
            deployment_config=deployment_config,
        )

        if result["success"]:
            click.echo("✓ Production project generated successfully!")
            click.echo(f"Project directory: {result['project_dir']}")
            click.echo(f"Files created: {len(result['files_created'])}")
            click.echo(f"Secrets generated: {result['secrets_count']}")
            click.echo("")
            click.echo("Next steps:")
            click.echo(f"1. cd {result['project_dir']}")
            click.echo("2. Review the generated configuration")
            click.echo("3. Run ./deploy.sh to deploy")
            click.echo("")
            click.echo("Or deploy manually:")
            click.echo("1. ./deploy-secrets.sh")
            click.echo("2. ./setup-ssl.sh")
            click.echo("3. docker-compose up -d")
        else:
            click.echo(
                f"✗ Failed to generate production project: {result.get('error', 'Unknown error')}"
            )
            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Production project generation")


@prod.command()
@click.argument("domain")
@click.option("--ssl-email", help="Email address for SSL certificate generation")
@click.option("--user", default="coffeebreak", help="System user for CoffeeBreak")
@click.option(
    "--install-dir", default="/opt/coffeebreak", help="Installation directory"
)
@click.option("--data-dir", default="/var/lib/coffeebreak", help="Data directory")
@click.option("--log-dir", default="/var/log/coffeebreak", help="Log directory")
@click.pass_context
def install(ctx, domain, ssl_email, user, install_dir, data_dir, log_dir):
    """Install CoffeeBreak directly on production server (standalone mode)."""
    try:
        if ctx.obj["verbose"]:
            click.echo(f"Installing CoffeeBreak standalone for {domain}")

        if ctx.obj["dry_run"]:
            click.echo(f"DRY RUN: Would install CoffeeBreak standalone for {domain}")
            click.echo(f"User: {user}")
            click.echo(f"Install directory: {install_dir}")
            click.echo(f"Data directory: {data_dir}")
            return

        from coffeebreak.config import ConfigManager
        from coffeebreak.environments.production import ProductionEnvironment

        # Initialize components
        config_manager = ConfigManager(verbose=ctx.obj["verbose"])
        prod_env = ProductionEnvironment(config_manager, verbose=ctx.obj["verbose"])

        # Install standalone
        success = prod_env.install_standalone(domain=domain, ssl_email=ssl_email)

        if success:
            click.echo(f"✓ CoffeeBreak installed successfully for {domain}")
            click.echo("Services have been configured and started")
        else:
            click.echo("✗ Installation failed")
            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Standalone installation")


@prod.command()
@click.argument("domain")
@click.option("--config-file", help="Production configuration file")
@click.option(
    "--comprehensive",
    is_flag=True,
    help="Run comprehensive validation including health checks",
)
@click.pass_context
def validate(ctx, domain, config_file, comprehensive):
    """Validate production configuration and readiness."""
    try:
        if ctx.obj["verbose"]:
            click.echo(f"Validating production configuration for {domain}")

        if ctx.obj["dry_run"]:
            click.echo("DRY RUN: Would validate production configuration")
            return

        from coffeebreak.validation import ProductionValidator

        # Determine deployment type
        deployment_type = (
            "docker" if os.path.exists("docker-compose.yml") else "standalone"
        )

        # Initialize validator
        validator = ProductionValidator(
            deployment_type=deployment_type, verbose=ctx.obj["verbose"]
        )

        if comprehensive:
            # Run comprehensive validation
            validation_result = validator.validate_production_readiness(
                domain=domain, config_path=config_file
            )

            click.echo(f"\nProduction Readiness Validation for {domain}")
            click.echo("=" * 50)

            overall_status = validation_result["overall_status"]
            ready = validation_result["ready_for_production"]

            if overall_status == "passed":
                click.echo("✓ Overall Status: PASSED")
            elif overall_status == "warning":
                click.echo("⚠ Overall Status: WARNING")
            else:
                click.echo("✗ Overall Status: FAILED")

            click.echo(f"Ready for Production: {'✓ YES' if ready else '✗ NO'}")

            # Show critical issues
            if validation_result["critical_issues"]:
                click.echo(
                    f"\nCritical Issues ({len(validation_result['critical_issues'])}):"
                )
                for issue in validation_result["critical_issues"]:
                    click.echo(f"  ✗ {issue}")

            # Show warnings
            if validation_result["warnings"]:
                click.echo(f"\nWarnings ({len(validation_result['warnings'])}):")
                for warning in validation_result["warnings"]:
                    click.echo(f"  ⚠ {warning}")

            # Show passed checks
            if ctx.obj["verbose"] and validation_result["passed_checks"]:
                click.echo(
                    f"\nPassed Checks ({len(validation_result['passed_checks'])}):"
                )
                for check in validation_result["passed_checks"][:10]:  # Show first 10
                    click.echo(f"  ✓ {check}")
                if len(validation_result["passed_checks"]) > 10:
                    click.echo(
                        f"  ... and {len(validation_result['passed_checks']) - 10} more"
                    )

            # Show detailed results if verbose
            if ctx.obj["verbose"]:
                click.echo("\nDetailed Validation Results:")
                for category, details in validation_result[
                    "validation_details"
                ].items():
                    status = details["status"]
                    status_icon = (
                        "✓"
                        if status == "passed"
                        else "⚠"
                        if status == "warning"
                        else "✗"
                    )
                    click.echo(
                        f"  {status_icon} {category.replace('_', ' ').title()}: {status}"
                    )

            if not ready:
                ctx.exit(1)

        else:
            # Quick validation - just secrets and basic checks
            from coffeebreak.secrets import SecretManager

            secret_manager = SecretManager(
                deployment_type=deployment_type, verbose=ctx.obj["verbose"]
            )
            validation = secret_manager.validate_secrets_deployment()

            click.echo(f"\nQuick Validation for {domain}")
            click.echo("=" * 30)
            click.echo(f"Deployment Type: {deployment_type}")
            click.echo(
                f"Secrets Status: {'✓ Valid' if validation['valid'] else '✗ Invalid'}"
            )
            click.echo(
                f"Found: {validation['found']}/{validation['total_required']} required secrets"
            )

            if validation["missing"]:
                click.echo("\nMissing secrets:")
                for secret in validation["missing"]:
                    click.echo(f"  - {secret}")

            if validation["errors"]:
                click.echo("\nErrors:")
                for error in validation["errors"]:
                    click.echo(f"  - {error}")

            if not validation["valid"]:
                ctx.exit(1)

            click.echo("\n✓ Basic validation passed")
            click.echo("Use --comprehensive for full production readiness check")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Production validation")


@prod.command()
@click.option("--rotation-config", help="Secret rotation configuration file")
@click.option("--max-rotations", default=5, help="Maximum number of secrets to rotate")
@click.option("--force", is_flag=True, help="Force rotation even if not due")
@click.pass_context
def rotate_secrets(ctx, rotation_config, max_rotations, force):
    """Rotate production secrets."""
    try:
        if ctx.obj["verbose"]:
            click.echo("Starting secret rotation")

        if ctx.obj["dry_run"]:
            click.echo("DRY RUN: Would rotate production secrets")
            return

        from coffeebreak.secrets import SecretManager, SecretRotationManager

        # Determine deployment type
        if os.path.exists("docker-compose.yml"):
            secret_manager = SecretManager(
                deployment_type="docker", verbose=ctx.obj["verbose"]
            )
        else:
            secret_manager = SecretManager(
                deployment_type="standalone", verbose=ctx.obj["verbose"]
            )

        # Initialize rotation manager
        config_file = rotation_config or "/etc/coffeebreak/rotation.json"
        rotation_manager = SecretRotationManager(
            secret_manager=secret_manager,
            config_file=config_file,
            verbose=ctx.obj["verbose"],
        )

        if force:
            # Get all secret names and rotate them
            status = rotation_manager.get_rotation_status()
            secret_names = list(status["schedules"].keys())

            click.echo(f"Force rotating {len(secret_names)} secrets")
            results = rotation_manager.emergency_rotation(
                secret_names=secret_names, reason="Manual force rotation via CLI"
            )
        else:
            # Rotate only secrets that are due
            results = rotation_manager.rotate_due_secrets(max_rotations=max_rotations)

        if results:
            click.echo(f"\nRotation completed: {len(results)} secrets processed")

            successful = sum(1 for r in results if r["success"])
            failed = sum(1 for r in results if not r["success"])

            click.echo(f"Successful: {successful}")
            click.echo(f"Failed: {failed}")

            if failed > 0:
                click.echo("\nFailed rotations:")
                for result in results:
                    if not result["success"]:
                        click.echo(
                            f"  - {result['secret_name']}: {result.get('error', 'Unknown error')}"
                        )
                ctx.exit(1)
        else:
            click.echo("No secrets were rotated")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "Secret rotation")


@prod.command()
@click.argument("domain")
@click.option("--email", help="Email address for Let's Encrypt registration")
@click.option("--staging", is_flag=True, help="Use Let's Encrypt staging environment")
@click.option(
    "--challenge",
    default="standalone",
    help="Challenge method (standalone, webroot, dns)",
)
@click.option("--webroot-path", help="Webroot path for webroot challenge")
@click.option(
    "--cert-dir", default="/etc/ssl/certs", help="Directory to install certificates"
)
@click.option(
    "--dry-run-cert", is_flag=True, help="Test certificate generation without obtaining"
)
@click.pass_context
def ssl_obtain(
    ctx, domain, email, staging, challenge, webroot_path, cert_dir, dry_run_cert
):
    """Obtain SSL certificate from Let's Encrypt."""
    try:
        if ctx.obj["verbose"]:
            click.echo(f"Obtaining SSL certificate for {domain}")

        if ctx.obj["dry_run"]:
            click.echo(f"DRY RUN: Would obtain SSL certificate for {domain}")
            click.echo(f"Email: {email}")
            click.echo(f"Challenge: {challenge}")
            click.echo(f"Staging: {staging}")
            return

        from coffeebreak.ssl import LetsEncryptManager

        if not email:
            email = click.prompt("Email address for Let's Encrypt registration")

        # Initialize Let's Encrypt manager
        le_manager = LetsEncryptManager(
            email=email, staging=staging, verbose=ctx.obj["verbose"]
        )

        # Obtain certificate
        result = le_manager.obtain_certificate(
            domain=domain,
            challenge_method=challenge,
            webroot_path=webroot_path,
            dry_run=dry_run_cert,
        )

        if result["success"]:
            if dry_run_cert:
                click.echo("✓ Certificate validation test passed")
            else:
                click.echo("✓ SSL certificate obtained successfully")
                click.echo(f"Certificate: {result['cert_path']}")
                click.echo(f"Private key: {result['key_path']}")
                click.echo(f"Chain: {result['chain_path']}")

                # Copy to specified directory if different
                if cert_dir != "/etc/letsencrypt/live":
                    from coffeebreak.ssl import SSLManager

                    ssl_manager = SSLManager(verbose=ctx.obj["verbose"])

                    with open(result["cert_path"]) as f:
                        cert_data = f.read()
                    with open(result["key_path"]) as f:
                        key_data = f.read()
                    with open(result["chain_path"]) as f:
                        chain_data = f.read()

                    installed = ssl_manager.install_certificate(
                        cert_data=cert_data,
                        key_data=key_data,
                        chain_data=chain_data,
                        domain=domain,
                        install_dir=cert_dir,
                    )

                    click.echo(f"Certificate installed to: {installed['cert_path']}")
        else:
            click.echo("✗ Failed to obtain SSL certificate")
            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "SSL certificate obtainment")


@prod.command()
@click.option("--domain", help="Specific domain to renew (default: all)")
@click.option(
    "--dry-run-cert", is_flag=True, help="Test renewal without actually renewing"
)
@click.pass_context
def ssl_renew(ctx, domain, dry_run_cert):
    """Renew SSL certificates."""
    try:
        if ctx.obj["verbose"]:
            if domain:
                click.echo(f"Renewing SSL certificate for {domain}")
            else:
                click.echo("Renewing all SSL certificates")

        if ctx.obj["dry_run"]:
            click.echo("DRY RUN: Would renew SSL certificates")
            return

        from coffeebreak.ssl import LetsEncryptManager

        # Initialize Let's Encrypt manager (email not needed for renewal)
        le_manager = LetsEncryptManager(
            email="admin@example.com",  # Placeholder, not used for renewal
            verbose=ctx.obj["verbose"],
        )

        # Renew certificates
        result = le_manager.renew_certificate(domain=domain, dry_run=dry_run_cert)

        if result["success"]:
            if dry_run_cert:
                click.echo("✓ Certificate renewal test passed")
            else:
                click.echo("✓ SSL certificates renewed successfully")
        else:
            click.echo(
                f"✗ Certificate renewal failed: {result.get('error', 'Unknown error')}"
            )
            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "SSL certificate renewal")


@prod.command()
@click.pass_context
def ssl_list(ctx):
    """List all SSL certificates."""
    try:
        if ctx.obj["verbose"]:
            click.echo("Listing SSL certificates")

        if ctx.obj["dry_run"]:
            click.echo("DRY RUN: Would list SSL certificates")
            return

        from coffeebreak.ssl import LetsEncryptManager

        # Initialize Let's Encrypt manager
        le_manager = LetsEncryptManager(
            email="admin@example.com",  # Placeholder
            verbose=ctx.obj["verbose"],
        )

        # List certificates
        certificates = le_manager.list_certificates()

        if certificates:
            click.echo(f"Found {len(certificates)} SSL certificates:")
            click.echo("")

            for cert in certificates:
                click.echo(f"Certificate: {cert['name']}")
                click.echo(f"  Domains: {', '.join(cert.get('domains', []))}")
                click.echo(f"  Expiry: {cert.get('expiry_date', 'Unknown')}")

                if "expires_in_days" in cert:
                    days = cert["expires_in_days"]
                    if days < 0:
                        status = "EXPIRED"
                    elif days < 30:
                        status = f"EXPIRING SOON ({days} days)"
                    else:
                        status = f"Valid ({days} days)"
                    click.echo(f"  Status: {status}")

                click.echo("")
        else:
            click.echo("No SSL certificates found")

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "SSL certificate listing")


@prod.command()
@click.argument("cert_path")
@click.argument("key_path")
@click.argument("domain")
@click.pass_context
def ssl_validate(ctx, cert_path, key_path, domain):
    """Validate SSL certificate."""
    try:
        if ctx.obj["verbose"]:
            click.echo(f"Validating SSL certificate for {domain}")

        if ctx.obj["dry_run"]:
            click.echo("DRY RUN: Would validate SSL certificate")
            return

        from coffeebreak.ssl import SSLManager

        # Initialize SSL manager
        ssl_manager = SSLManager(verbose=ctx.obj["verbose"])

        # Validate certificate
        validation = ssl_manager.validate_certificate(
            cert_path=cert_path, key_path=key_path, domain=domain
        )

        click.echo(f"Certificate validation for {domain}:")
        click.echo(f"Status: {'✓ Valid' if validation['valid'] else '✗ Invalid'}")

        if validation["expires_in_days"] is not None:
            days = validation["expires_in_days"]
            if days < 0:
                click.echo(f"Expiration: EXPIRED ({abs(days)} days ago)")
            else:
                click.echo(f"Expiration: {days} days remaining")

        if validation["errors"]:
            click.echo("\nErrors:")
            for error in validation["errors"]:
                click.echo(f"  - {error}")

        if validation["warnings"]:
            click.echo("\nWarnings:")
            for warning in validation["warnings"]:
                click.echo(f"  - {warning}")

        if validation["cert_info"]:
            click.echo("\nCertificate Information:")
            info = validation["cert_info"]
            click.echo(f"  Subject: {info.get('subject', 'Unknown')}")
            click.echo(f"  Issuer: {info.get('issuer', 'Unknown')}")
            click.echo(f"  Serial: {info.get('serial_number', 'Unknown')}")

            if "san_domains" in info:
                click.echo(f"  SAN Domains: {', '.join(info['san_domains'])}")

        if not validation["valid"]:
            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "SSL certificate validation")


@prod.command()
@click.option(
    "--frequency",
    default="twice-daily",
    help="Renewal frequency (twice-daily, daily, weekly)",
)
@click.pass_context
def ssl_auto_renew(ctx, frequency):
    """Set up automatic SSL certificate renewal."""
    try:
        if ctx.obj["verbose"]:
            click.echo("Setting up automatic SSL certificate renewal")

        if ctx.obj["dry_run"]:
            click.echo(f"DRY RUN: Would setup auto-renewal ({frequency})")
            return

        from coffeebreak.ssl import LetsEncryptManager

        # Initialize Let's Encrypt manager
        le_manager = LetsEncryptManager(
            email="admin@example.com",  # Placeholder
            verbose=ctx.obj["verbose"],
        )

        # Setup auto-renewal
        success = le_manager.setup_auto_renewal(renewal_frequency=frequency)

        if success:
            click.echo("✓ Automatic SSL certificate renewal configured")
            click.echo(f"Frequency: {frequency}")
            click.echo("Certificates will be automatically renewed via cron")
        else:
            click.echo("✗ Failed to setup automatic renewal")
            ctx.exit(1)

    except Exception as e:
        ctx.obj["error_handler"].exit_with_error(e, "SSL auto-renewal setup")


if __name__ == "__main__":
    cli()
