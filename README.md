# CoffeeBreak CLI

CoffeeBreak CLI is a development and deployment automation tool that streamlines the entire CoffeeBreak development workflow, from initial setup to production deployment.

## Features

- **Environment Management**: Initialize and manage development, plugin development, and production environments
- **Dependency Management**: Automated container orchestration for development dependencies
- **Plugin Development**: Complete workflow for creating, developing, and building CoffeeBreak plugins
- **Production Deployment**: Support for both containerized (Docker) and standalone production deployments
- **Secrets Management**: Secure generation, storage, and rotation of secrets across all environments

## Installation

```bash
pip install coffeebreak-cli
```

## Quick Start

### Initialize Development Environment
```bash
mkdir my-coffeebreak-project
cd my-coffeebreak-project
coffeebreak init dev
coffeebreak dev
```

### Create a Plugin
```bash
coffeebreak plugin create my-awesome-plugin
cd my-awesome-plugin
coffeebreak dev
```

### Deploy to Production
```bash
# Generate Docker production project
coffeebreak production generate --output-dir /opt/deployments

# Or install directly on machine
sudo coffeebreak production install --domain api.company.com --ssl-email admin@company.com
```

## Documentation

For complete documentation, see the man pages:
- `man coffeebreak` - Main command reference
- `man coffeebreak.yml` - Configuration file format
- `man coffeebreak-plugin.yml` - Plugin manifest format

## Development

```bash
git clone https://github.com/PI-coffeeBreak/coffeebreak-cli
cd coffeebreak-cli
pip install -e .[dev]
pytest
```

## Support

Report issues at: https://github.com/PI-coffeeBreak/coffeebreak-cli/issues