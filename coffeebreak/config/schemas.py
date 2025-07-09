"""Configuration file schemas for CoffeeBreak CLI."""

MAIN_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "coffeebreak": {
            "type": "object",
            "properties": {
                "version": {
                    "type": "string",
                    "pattern": r"^\d+\.\d+\.\d+$"
                },
                "organization": {
                    "type": "string",
                    "description": "GitHub organization name"
                },
                "environment": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["venv", "conda"]
                        },
                        "path": {
                            "type": "string",
                            "description": "Path to virtual environment (for venv type)"
                        },
                        "name": {
                            "type": "string",
                            "description": "Environment name (for conda type)"
                        },
                        "python_path": {
                            "type": "string",
                            "description": "Path to Python executable"
                        }
                    },
                    "required": ["type"],
                    "additionalProperties": False
                },
                "repositories": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "enum": ["core", "frontend", "event-app"]
                            },
                            "url": {
                                "type": "string",
                                "pattern": r"^(https://github\.com/|git@github\.com:).+\.git$"
                            },
                            "path": {
                                "type": "string"
                            },
                            "branch": {
                                "type": "string",
                                "default": "main"
                            },
                            "startup_command": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["name", "url", "path"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["version", "repositories"],
            "additionalProperties": False
        },
        "environments": {
            "type": "object",
            "properties": {
                "dev": {
                    "type": "object",
                    "properties": {
                        "docker_network": {
                            "type": "string",
                            "default": "coffeebreak-dev"
                        },
                        "auto_start_deps": {
                            "type": "boolean",
                            "default": True
                        },
                        "hot_reload": {
                            "type": "boolean",
                            "default": True
                        }
                    },
                    "additionalProperties": False
                },
                "production": {
                    "type": "object",
                    "properties": {
                        "domain_required": {
                            "type": "boolean",
                            "default": True
                        },
                        "ssl_required": {
                            "type": "boolean",
                            "default": True
                        },
                        "backup_enabled": {
                            "type": "boolean",
                            "default": True
                        }
                    },
                    "additionalProperties": False
                }
            },
            "additionalProperties": False
        },
        "dependencies": {
            "type": "object",
            "properties": {
                "profiles": {
                    "type": "object",
                    "properties": {
                        "minimal": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "full": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "plugin-dev": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "additionalProperties": False
                },
                "services": {
                    "type": "object",
                    "patternProperties": {
                        "^[a-zA-Z0-9_-]+$": {
                            "type": "object",
                            "properties": {
                                "image": {"type": "string"},
                                "build": {
                                    "type": "object",
                                    "properties": {
                                        "context": {"type": "string"},
                                        "dockerfile": {"type": "string"}
                                    },
                                    "required": ["context"],
                                    "additionalProperties": False
                                },
                                "container_name": {"type": "string"},
                                "command": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "ports": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "environment": {
                                    "type": "object",
                                    "additionalProperties": {"type": "string"}
                                },
                                "volumes": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "depends_on": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "healthcheck": {
                                    "type": "object",
                                    "properties": {
                                        "test": {
                                            "type": "array",
                                            "items": {"type": "string"}
                                        },
                                        "interval": {"type": "string"},
                                        "retries": {"type": "integer"}
                                    }
                                }
                            },
                            "required": ["image"],
                            "additionalProperties": False
                        }
                    }
                }
            },
            "additionalProperties": False
        }
    },
    "required": ["coffeebreak"],
    "additionalProperties": False
}

PLUGIN_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "plugin": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "pattern": r"^[a-zA-Z0-9_-]+$"
                },
                "version": {
                    "type": "string",
                    "pattern": r"^\d+\.\d+\.\d+$"
                },
                "description": {"type": "string"},
                "author": {"type": "string"},
                "homepage": {"type": "string"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["name", "version"],
            "additionalProperties": False
        },
        "compatibility": {
            "type": "object",
            "properties": {
                "coffeebreak_core": {"type": "string"},
                "coffeebreak_api": {"type": "string"},
                "node_version": {"type": "string"},
                "python_version": {"type": "string"}
            },
            "additionalProperties": False
        },
        "dependencies": {
            "type": "object",
            "properties": {
                "services": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["database", "mongodb", "rabbitmq", "keycloak", "keycloak-db"]
                    }
                },
                "npm_packages": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "python_packages": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "system_requirements": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "additionalProperties": False
        },
        "development": {
            "type": "object",
            "properties": {
                "mount_paths": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "environment": {
                    "type": "object",
                    "additionalProperties": {"type": ["string", "boolean"]}
                },
                "ports": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "hot_reload": {
                    "type": "boolean",
                    "default": True
                },
                "watch_extensions": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "additionalProperties": False
        },
        "api_endpoints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "methods": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
                        }
                    },
                    "authentication": {
                        "type": "string",
                        "enum": ["required", "optional", "none"]
                    },
                    "permissions": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["path", "methods"],
                "additionalProperties": False
            }
        },
        "frontend_routes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "component": {"type": "string"},
                    "title": {"type": "string"},
                    "permissions": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["path", "component"],
                "additionalProperties": False
            }
        },
        "configuration": {
            "type": "object",
            "properties": {
                "settings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {
                                "type": "string",
                                "enum": ["string", "integer", "boolean", "array"]
                            },
                            "default": {},
                            "description": {"type": "string"},
                            "options": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "min": {"type": "number"},
                            "max": {"type": "number"}
                        },
                        "required": ["name", "type"],
                        "additionalProperties": False
                    }
                }
            },
            "additionalProperties": False
        },
        "build": {
            "type": "object",
            "properties": {
                "hooks": {
                    "type": "object",
                    "properties": {
                        "pre_build": {"type": "string"},
                        "build": {"type": "string"},
                        "post_build": {"type": "string"},
                        "test": {"type": "string"}
                    },
                    "additionalProperties": False
                },
                "output_directory": {"type": "string"},
                "assets_directory": {"type": "string"},
                "include_files": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "exclude_patterns": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "additionalProperties": False
        }
    },
    "required": ["plugin"],
    "additionalProperties": False
}