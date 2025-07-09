"""Metrics collection system for production monitoring."""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any
import yaml

from ..utils.errors import ConfigurationError


class MetricsCollector:
    """Collects and manages production metrics."""
    
    def __init__(self, verbose: bool = False):
        """Initialize metrics collector."""
        self.verbose = verbose
    
    def setup_metrics_collection(self, domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup Prometheus metrics collection."""
        setup_result = {
            'success': True,
            'errors': [],
            'prometheus_endpoint': None
        }
        
        try:
            if config.get('enable_prometheus', True):
                prometheus_setup = self._setup_prometheus(domain, config)
                if prometheus_setup['success']:
                    setup_result['prometheus_endpoint'] = f"https://{domain}/prometheus"
                else:
                    setup_result['errors'].extend(prometheus_setup['errors'])
            
            # Setup node exporter for system metrics
            node_exporter_setup = self._setup_node_exporter(config)
            if not node_exporter_setup['success']:
                setup_result['errors'].extend(node_exporter_setup['errors'])
            
            setup_result['success'] = len(setup_result['errors']) == 0
            
        except Exception as e:
            setup_result['success'] = False
            setup_result['errors'].append(f"Metrics collection setup failed: {e}")
        
        return setup_result
    
    def _setup_prometheus(self, domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup Prometheus monitoring."""
        setup_result = {
            'success': True,
            'errors': []
        }
        
        try:
            # Create Prometheus configuration
            prometheus_config = {
                'global': {
                    'scrape_interval': '15s',
                    'evaluation_interval': '15s'
                },
                'scrape_configs': [
                    {
                        'job_name': 'prometheus',
                        'static_configs': [{'targets': ['localhost:9090']}]
                    },
                    {
                        'job_name': 'node-exporter',
                        'static_configs': [{'targets': ['localhost:9100']}]
                    },
                    {
                        'job_name': 'coffeebreak-api',
                        'static_configs': [{'targets': ['localhost:3000']}],
                        'metrics_path': '/metrics'
                    },
                    {
                        'job_name': 'nginx',
                        'static_configs': [{'targets': ['localhost:9113']}]
                    }
                ]
            }
            
            # Write Prometheus configuration
            prometheus_dir = Path('./prometheus')
            prometheus_dir.mkdir(exist_ok=True)
            
            with open(prometheus_dir / 'prometheus.yml', 'w') as f:
                yaml.dump(prometheus_config, f)
            
            if self.verbose:
                print("Prometheus configuration created")
            
        except Exception as e:
            setup_result['success'] = False
            setup_result['errors'].append(f"Prometheus setup failed: {e}")
        
        return setup_result
    
    def _setup_node_exporter(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup Node Exporter for system metrics."""
        setup_result = {
            'success': True,
            'errors': []
        }
        
        try:
            # For Docker deployment, node exporter is included in compose
            # For standalone, install as system service
            if config.get('deployment_type') == 'standalone':
                self._install_node_exporter_standalone()
            
        except Exception as e:
            setup_result['success'] = False
            setup_result['errors'].append(f"Node Exporter setup failed: {e}")
        
        return setup_result
    
    def _install_node_exporter_standalone(self) -> None:
        """Install Node Exporter for standalone deployment."""
        try:
            # Download and install node exporter
            node_exporter_version = "1.3.1"
            download_url = f"https://github.com/prometheus/node_exporter/releases/download/v{node_exporter_version}/node_exporter-{node_exporter_version}.linux-amd64.tar.gz"
            
            # Create node_exporter user
            subprocess.run(['useradd', '--no-create-home', '--shell', '/bin/false', 'node_exporter'], 
                         capture_output=True)
            
            # Download and extract
            subprocess.run(['wget', download_url, '-O', '/tmp/node_exporter.tar.gz'], check=True)
            subprocess.run(['tar', '-xzf', '/tmp/node_exporter.tar.gz', '-C', '/tmp'], check=True)
            subprocess.run(['cp', f'/tmp/node_exporter-{node_exporter_version}.linux-amd64/node_exporter', 
                          '/usr/local/bin/'], check=True)
            subprocess.run(['chown', 'node_exporter:node_exporter', '/usr/local/bin/node_exporter'], check=True)
            
            # Create systemd service
            service_content = """[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
"""
            
            with open('/etc/systemd/system/node_exporter.service', 'w') as f:
                f.write(service_content)
            
            # Enable and start service
            subprocess.run(['systemctl', 'daemon-reload'], check=True)
            subprocess.run(['systemctl', 'enable', 'node_exporter'], check=True)
            subprocess.run(['systemctl', 'start', 'node_exporter'], check=True)
            
        except Exception as e:
            raise ConfigurationError(f"Failed to install Node Exporter: {e}")