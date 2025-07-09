"""Alert management system for production monitoring."""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any
import yaml

from ..utils.errors import ConfigurationError


class AlertManager:
    """Manages alerts and notifications for production monitoring."""
    
    def __init__(self, verbose: bool = False):
        """Initialize alert manager."""
        self.verbose = verbose
    
    def setup_alerting(self, domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup alerting system."""
        setup_result = {
            'success': True,
            'errors': []
        }
        
        try:
            # Setup Prometheus Alertmanager
            alertmanager_setup = self._setup_alertmanager(domain, config)
            if not alertmanager_setup['success']:
                setup_result['errors'].extend(alertmanager_setup['errors'])
            
            # Setup alert rules
            rules_setup = self._setup_alert_rules(config)
            if not rules_setup['success']:
                setup_result['errors'].extend(rules_setup['errors'])
            
            # Setup notification channels
            notifications_setup = self._setup_notifications(config)
            if not notifications_setup['success']:
                setup_result['errors'].extend(notifications_setup['errors'])
            
            setup_result['success'] = len(setup_result['errors']) == 0
            
        except Exception as e:
            setup_result['success'] = False
            setup_result['errors'].append(f"Alerting setup failed: {e}")
        
        return setup_result
    
    def _setup_alertmanager(self, domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup Prometheus Alertmanager."""
        setup_result = {
            'success': True,
            'errors': []
        }
        
        try:
            # Create Alertmanager configuration
            alertmanager_config = {
                'global': {
                    'smtp_smarthost': config.get('smtp_host', 'localhost:587'),
                    'smtp_from': config.get('alert_email', f'alerts@{domain}'),
                    'smtp_auth_username': config.get('smtp_user', ''),
                    'smtp_auth_password': config.get('smtp_password', '')
                },
                'route': {
                    'group_by': ['alertname'],
                    'group_wait': '10s',
                    'group_interval': '10s',
                    'repeat_interval': '1h',
                    'receiver': 'web.hook'
                },
                'receivers': [
                    {
                        'name': 'web.hook',
                        'email_configs': [
                            {
                                'to': config.get('alert_email', f'admin@{domain}'),
                                'subject': 'CoffeeBreak Alert: {{ .GroupLabels.alertname }}',
                                'body': '''
Alert: {{ .GroupLabels.alertname }}
Summary: {{ range .Alerts }}{{ .Annotations.summary }}{{ end }}
Description: {{ range .Alerts }}{{ .Annotations.description }}{{ end }}

Details:
{{ range .Alerts }}
- Alert: {{ .Labels.alertname }}
  Instance: {{ .Labels.instance }}
  Severity: {{ .Labels.severity }}
  Value: {{ .Annotations.value }}
{{ end }}

Dashboard: https://''' + domain + '''/grafana
'''
                            }
                        ]
                    }
                ]
            }
            
            # Write Alertmanager configuration
            alertmanager_dir = Path('./alertmanager')
            alertmanager_dir.mkdir(exist_ok=True)
            
            with open(alertmanager_dir / 'alertmanager.yml', 'w') as f:
                yaml.dump(alertmanager_config, f)
            
            if self.verbose:
                print("Alertmanager configuration created")
            
        except Exception as e:
            setup_result['success'] = False
            setup_result['errors'].append(f"Alertmanager setup failed: {e}")
        
        return setup_result
    
    def _setup_alert_rules(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup Prometheus alert rules."""
        setup_result = {
            'success': True,
            'errors': []
        }
        
        try:
            # Define alert rules
            alert_rules = {
                'groups': [
                    {
                        'name': 'coffeebreak.rules',
                        'rules': [
                            {
                                'alert': 'InstanceDown',
                                'expr': 'up == 0',
                                'for': '5m',
                                'labels': {
                                    'severity': 'critical'
                                },
                                'annotations': {
                                    'summary': 'Instance {{ $labels.instance }} down',
                                    'description': 'Instance {{ $labels.instance }} has been down for more than 5 minutes.'
                                }
                            },
                            {
                                'alert': 'HighCPUUsage',
                                'expr': '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80',
                                'for': '5m',
                                'labels': {
                                    'severity': 'warning'
                                },
                                'annotations': {
                                    'summary': 'High CPU usage on {{ $labels.instance }}',
                                    'description': 'CPU usage is above 80% for more than 5 minutes.',
                                    'value': '{{ $value }}%'
                                }
                            },
                            {
                                'alert': 'HighMemoryUsage',
                                'expr': '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 90',
                                'for': '5m',
                                'labels': {
                                    'severity': 'warning'
                                },
                                'annotations': {
                                    'summary': 'High memory usage on {{ $labels.instance }}',
                                    'description': 'Memory usage is above 90% for more than 5 minutes.',
                                    'value': '{{ $value }}%'
                                }
                            },
                            {
                                'alert': 'DiskSpaceLow',
                                'expr': '(1 - (node_filesystem_avail_bytes{fstype!="tmpfs"} / node_filesystem_size_bytes{fstype!="tmpfs"})) * 100 > 85',
                                'for': '5m',
                                'labels': {
                                    'severity': 'warning'
                                },
                                'annotations': {
                                    'summary': 'Disk space low on {{ $labels.instance }}',
                                    'description': 'Disk usage is above 85% on {{ $labels.mountpoint }}.',
                                    'value': '{{ $value }}%'
                                }
                            },
                            {
                                'alert': 'HTTPRequestErrors',
                                'expr': 'rate(http_requests_total{status=~"5.."}[5m]) > 0.1',
                                'for': '5m',
                                'labels': {
                                    'severity': 'critical'
                                },
                                'annotations': {
                                    'summary': 'High HTTP error rate',
                                    'description': 'HTTP error rate is above 0.1 requests per second.',
                                    'value': '{{ $value }} req/s'
                                }
                            },
                            {
                                'alert': 'SlowHTTPRequests',
                                'expr': 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2',
                                'for': '5m',
                                'labels': {
                                    'severity': 'warning'
                                },
                                'annotations': {
                                    'summary': 'Slow HTTP requests',
                                    'description': '95th percentile response time is above 2 seconds.',
                                    'value': '{{ $value }}s'
                                }
                            },
                            {
                                'alert': 'SSLCertificateExpiring',
                                'expr': '(ssl_certificate_expiry_seconds - time()) / 86400 < 30',
                                'for': '1h',
                                'labels': {
                                    'severity': 'warning'
                                },
                                'annotations': {
                                    'summary': 'SSL certificate expiring soon',
                                    'description': 'SSL certificate for {{ $labels.instance }} expires in {{ $value }} days.',
                                    'value': '{{ $value }}'
                                }
                            },
                            {
                                'alert': 'DatabaseConnectionError',
                                'expr': 'postgresql_up == 0 or mongodb_up == 0',
                                'for': '2m',
                                'labels': {
                                    'severity': 'critical'
                                },
                                'annotations': {
                                    'summary': 'Database connection error',
                                    'description': 'Cannot connect to {{ $labels.database }} database.'
                                }
                            }
                        ]
                    }
                ]
            }
            
            # Write alert rules
            prometheus_dir = Path('./prometheus')
            prometheus_dir.mkdir(exist_ok=True)
            
            with open(prometheus_dir / 'alert.rules.yml', 'w') as f:
                yaml.dump(alert_rules, f)
            
            if self.verbose:
                print("Alert rules created")
            
        except Exception as e:
            setup_result['success'] = False
            setup_result['errors'].append(f"Alert rules setup failed: {e}")
        
        return setup_result
    
    def _setup_notifications(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup notification channels."""
        setup_result = {
            'success': True,
            'errors': []
        }
        
        try:
            # Create notification script for immediate alerts
            notification_script = f"""#!/bin/bash
# CoffeeBreak notification script

ALERT_EMAIL="{config.get('alert_email', 'admin@localhost')}"
WEBHOOK_URL="{config.get('webhook_url', '')}"

# Function to send email notification
send_email() {{
    local subject="$1"
    local message="$2"
    
    if command -v mail &> /dev/null && [ -n "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "CoffeeBreak Alert: $subject" "$ALERT_EMAIL"
        echo "Email alert sent to $ALERT_EMAIL"
    fi
}}

# Function to send webhook notification
send_webhook() {{
    local subject="$1"
    local message="$2"
    
    if [ -n "$WEBHOOK_URL" ] && command -v curl &> /dev/null; then
        local payload='{{"text": "CoffeeBreak Alert: '"$subject"'
'"$message"'"}}'
        curl -X POST -H "Content-Type: application/json" -d "$payload" "$WEBHOOK_URL"
        echo "Webhook notification sent"
    fi
}}

# Function to log notification
log_notification() {{
    local subject="$1"
    local message="$2"
    
    logger -t coffeebreak-alert "ALERT: $subject - $message"
}}

# Main notification function
notify() {{
    local subject="$1"
    local message="$2"
    
    echo "Sending notification: $subject"
    echo "Message: $message"
    
    send_email "$subject" "$message"
    send_webhook "$subject" "$message"
    log_notification "$subject" "$message"
}}

# Handle command line arguments
if [ $# -ge 2 ]; then
    notify "$1" "$2"
else
    echo "Usage: $0 <subject> <message>"
    exit 1
fi
"""
            
            # Write notification script
            if config.get('deployment_type') == 'standalone':
                script_path = "/opt/coffeebreak/bin/notify.sh"
            else:
                script_path = "./notify.sh"
            
            os.makedirs(os.path.dirname(script_path), exist_ok=True)
            
            with open(script_path, 'w') as f:
                f.write(notification_script)
            os.chmod(script_path, 0o755)
            
            if self.verbose:
                print("Notification system configured")
            
        except Exception as e:
            setup_result['success'] = False
            setup_result['errors'].append(f"Notifications setup failed: {e}")
        
        return setup_result