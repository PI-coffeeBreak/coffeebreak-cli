"""Production monitoring manager."""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader

from ..utils.errors import ConfigurationError
from .metrics import MetricsCollector
from .logs import LogManager
from .alerts import AlertManager


class MonitoringManager:
    """Manages production monitoring setup and configuration."""
    
    def __init__(self, 
                 deployment_type: str = "docker",
                 verbose: bool = False):
        """
        Initialize monitoring manager.
        
        Args:
            deployment_type: Type of deployment (docker, standalone)
            verbose: Enable verbose output
        """
        self.deployment_type = deployment_type
        self.verbose = verbose
        
        # Initialize components
        self.metrics_collector = MetricsCollector(verbose=verbose)
        self.log_manager = LogManager(deployment_type=deployment_type, verbose=verbose)
        self.alert_manager = AlertManager(verbose=verbose)
        
        # Initialize template system
        templates_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(templates_dir))
    
    def setup_production_monitoring(self, 
                                  domain: str,
                                  monitoring_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Set up comprehensive production monitoring.
        
        Args:
            domain: Production domain
            monitoring_config: Optional monitoring configuration
            
        Returns:
            Dict[str, Any]: Setup results
        """
        try:
            if self.verbose:
                print(f"Setting up production monitoring for {domain}")
            
            setup_result = {
                'success': True,
                'domain': domain,
                'deployment_type': self.deployment_type,
                'components_setup': [],
                'errors': [],
                'monitoring_endpoints': []
            }
            
            # Default monitoring configuration
            config = {
                'domain': domain,
                'enable_prometheus': True,
                'enable_grafana': True,
                'enable_log_aggregation': True,
                'enable_alerting': True,
                'log_retention_days': 30,
                'metrics_retention_days': 15,
                'alert_email': f"admin@{domain}",
                'grafana_admin_password': self._generate_password(16)
            }
            
            if monitoring_config:
                config.update(monitoring_config)
            
            # 1. Setup log aggregation
            log_setup = self.log_manager.setup_log_aggregation(domain, config)
            if log_setup['success']:
                setup_result['components_setup'].append('log_aggregation')
            else:
                setup_result['errors'].extend(log_setup['errors'])
            
            # 2. Setup metrics collection
            metrics_setup = self.metrics_collector.setup_metrics_collection(domain, config)
            if metrics_setup['success']:
                setup_result['components_setup'].append('metrics_collection')
                if 'prometheus_endpoint' in metrics_setup:
                    setup_result['monitoring_endpoints'].append({
                        'name': 'Prometheus',
                        'url': metrics_setup['prometheus_endpoint'],
                        'type': 'metrics'
                    })
            else:
                setup_result['errors'].extend(metrics_setup['errors'])
            
            # 3. Setup Grafana dashboards
            if config['enable_grafana']:
                grafana_setup = self._setup_grafana_dashboards(domain, config)
                if grafana_setup['success']:
                    setup_result['components_setup'].append('grafana_dashboards')
                    setup_result['monitoring_endpoints'].append({
                        'name': 'Grafana',
                        'url': f"https://{domain}/grafana",
                        'type': 'dashboard',
                        'credentials': {
                            'username': 'admin',
                            'password': config['grafana_admin_password']
                        }
                    })
                else:
                    setup_result['errors'].extend(grafana_setup['errors'])
            
            # 4. Setup alerting
            if config['enable_alerting']:
                alert_setup = self.alert_manager.setup_alerting(domain, config)
                if alert_setup['success']:
                    setup_result['components_setup'].append('alerting')
                else:
                    setup_result['errors'].extend(alert_setup['errors'])
            
            # 5. Setup health monitoring
            health_setup = self._setup_health_monitoring(domain, config)
            if health_setup['success']:
                setup_result['components_setup'].append('health_monitoring')
            else:
                setup_result['errors'].extend(health_setup['errors'])
            
            # 6. Create monitoring scripts
            scripts_setup = self._create_monitoring_scripts(domain, config)
            if scripts_setup['success']:
                setup_result['components_setup'].append('monitoring_scripts')
            else:
                setup_result['errors'].extend(scripts_setup['errors'])
            
            setup_result['success'] = len(setup_result['errors']) == 0
            
            if self.verbose:
                if setup_result['success']:
                    print(f"Monitoring setup completed successfully for {domain}")
                    print(f"Components: {', '.join(setup_result['components_setup'])}")
                else:
                    print(f"Monitoring setup completed with {len(setup_result['errors'])} errors")
            
            return setup_result
            
        except Exception as e:
            raise ConfigurationError(f"Failed to setup monitoring: {e}")
    
    def _setup_grafana_dashboards(self, domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup Grafana dashboards."""
        setup_result = {
            'success': True,
            'errors': []
        }
        
        try:
            if self.deployment_type == 'docker':
                # Add Grafana to Docker Compose
                grafana_config = self._generate_grafana_docker_config(domain, config)
                
                # Create Grafana configuration directory
                grafana_dir = Path('./grafana')
                grafana_dir.mkdir(exist_ok=True)
                
                # Create datasources configuration
                datasources_config = {
                    'apiVersion': 1,
                    'datasources': [{
                        'name': 'Prometheus',
                        'type': 'prometheus',
                        'url': 'http://prometheus:9090',
                        'access': 'proxy',
                        'isDefault': True
                    }]
                }
                
                import yaml
                with open(grafana_dir / 'datasources.yml', 'w') as f:
                    yaml.dump(datasources_config, f)
                
                # Create dashboard configurations
                self._create_grafana_dashboards(grafana_dir)
                
            else:  # Standalone
                # Install Grafana
                self._install_grafana_standalone(config)
                
                # Configure Grafana
                self._configure_grafana_standalone(domain, config)
            
        except Exception as e:
            setup_result['success'] = False
            setup_result['errors'].append(f"Grafana setup failed: {e}")
        
        return setup_result
    
    def _setup_health_monitoring(self, domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup health monitoring."""
        setup_result = {
            'success': True,
            'errors': []
        }
        
        try:
            # Create health check script
            health_script_content = f"""#!/bin/bash
# CoffeeBreak Health Monitoring Script

DOMAIN="{domain}"
LOG_FILE="/var/log/coffeebreak/health-monitor.log"
ALERT_EMAIL="{config.get('alert_email', 'admin@localhost')}"

# Create log directory
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log with timestamp
log_message() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}}

# Function to send alert
send_alert() {{
    local subject="$1"
    local message="$2"
    
    log_message "ALERT: $subject"
    
    # Send email if mail is available
    if command -v mail &> /dev/null; then
        echo "$message" | mail -s "CoffeeBreak Alert: $subject" "$ALERT_EMAIL"
    fi
    
    # Log to syslog
    logger -t coffeebreak-health "ALERT: $subject - $message"
}}

# Check HTTPS connectivity
check_https() {{
    if ! curl -s --max-time 10 "https://$DOMAIN/health" > /dev/null; then
        send_alert "HTTPS Check Failed" "Cannot reach https://$DOMAIN/health"
        return 1
    fi
    return 0
}}

# Check SSL certificate expiry
check_ssl_expiry() {{
    local expiry_days
    expiry_days=$(echo | openssl s_client -servername "$DOMAIN" -connect "$DOMAIN:443" 2>/dev/null | \\
                 openssl x509 -noout -dates | grep notAfter | cut -d= -f2 | \\
                 xargs -I{{}} date -d{{}} +%s)
    
    if [ -n "$expiry_days" ]; then
        local current_time=$(date +%s)
        local days_left=$(( (expiry_days - current_time) / 86400 ))
        
        if [ "$days_left" -lt 30 ]; then
            send_alert "SSL Certificate Expiring" "SSL certificate expires in $days_left days"
        fi
    fi
}}

# Check service status
check_services() {{
    local services=("nginx" "postgresql" "mongod" "rabbitmq-server" "redis-server")
    
    for service in "${{services[@]}}"; do
        if ! systemctl is-active --quiet "$service" 2>/dev/null; then
            send_alert "Service Down" "Service $service is not running"
        fi
    done
}}

# Check disk space
check_disk_space() {{
    local usage
    usage=$(df / | awk 'NR==2 {{print $5}}' | sed 's/%//')
    
    if [ "$usage" -gt 85 ]; then
        send_alert "High Disk Usage" "Disk usage is at $usage%"
    fi
}}

# Check memory usage
check_memory() {{
    local mem_usage
    mem_usage=$(free | awk 'NR==2{{printf "%.0f", $3*100/$2 }}')
    
    if [ "$mem_usage" -gt 90 ]; then
        send_alert "High Memory Usage" "Memory usage is at $mem_usage%"
    fi
}}

# Main health check
main() {{
    log_message "Starting health check"
    
    local checks_passed=0
    local total_checks=5
    
    check_https && ((checks_passed++))
    check_ssl_expiry && ((checks_passed++))
    check_services && ((checks_passed++))
    check_disk_space && ((checks_passed++))
    check_memory && ((checks_passed++))
    
    log_message "Health check completed: $checks_passed/$total_checks checks passed"
    
    if [ "$checks_passed" -eq "$total_checks" ]; then
        exit 0
    else
        exit 1
    fi
}}

main "$@"
"""
            
            # Write health script
            if self.deployment_type == 'standalone':
                health_script_path = "/opt/coffeebreak/bin/health-monitor.sh"
            else:
                health_script_path = "./health-monitor.sh"
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(health_script_path), exist_ok=True)
            
            with open(health_script_path, 'w') as f:
                f.write(health_script_content)
            os.chmod(health_script_path, 0o755)
            
            # Setup cron job for health monitoring
            cron_entry = f"*/5 * * * * {health_script_path}"
            
            try:
                current_crontab = subprocess.run(['crontab', '-l'], 
                                               capture_output=True, text=True)
                crontab_content = current_crontab.stdout if current_crontab.returncode == 0 else ""
            except:
                crontab_content = ""
            
            if "health-monitor.sh" not in crontab_content:
                new_crontab = crontab_content.rstrip() + "\n" + cron_entry + "\n"
                process = subprocess.Popen(['crontab', '-'], 
                                         stdin=subprocess.PIPE, text=True)
                process.communicate(input=new_crontab)
            
        except Exception as e:
            setup_result['success'] = False
            setup_result['errors'].append(f"Health monitoring setup failed: {e}")
        
        return setup_result
    
    def _create_monitoring_scripts(self, domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create monitoring and maintenance scripts."""
        setup_result = {
            'success': True,
            'errors': []
        }
        
        try:
            if self.deployment_type == 'standalone':
                scripts_dir = "/opt/coffeebreak/bin"
            else:
                scripts_dir = "./scripts"
            
            os.makedirs(scripts_dir, exist_ok=True)
            
            # Log rotation script
            log_rotate_script = f"""#!/bin/bash
# Log rotation script for CoffeeBreak

LOG_DIR="/var/log/coffeebreak"
RETENTION_DAYS={config.get('log_retention_days', 30)}

# Rotate application logs
for log_file in "$LOG_DIR"/*.log; do
    if [ -f "$log_file" ]; then
        # Compress logs older than 1 day
        find "$(dirname "$log_file")" -name "$(basename "$log_file").*.gz" -mtime +$RETENTION_DAYS -delete
        
        # Rotate current log
        if [ -s "$log_file" ]; then
            timestamp=$(date +%Y%m%d_%H%M%S)
            mv "$log_file" "${{log_file}}.$timestamp"
            gzip "${{log_file}}.$timestamp"
            touch "$log_file"
            
            # Set appropriate permissions
            chmod 644 "$log_file"
            if id coffeebreak &>/dev/null; then
                chown coffeebreak:coffeebreak "$log_file"
            fi
        fi
    fi
done

echo "Log rotation completed at $(date)"
"""
            
            with open(f"{scripts_dir}/rotate-logs.sh", 'w') as f:
                f.write(log_rotate_script)
            os.chmod(f"{scripts_dir}/rotate-logs.sh", 0o755)
            
            # Metrics cleanup script
            metrics_cleanup_script = f"""#!/bin/bash
# Metrics cleanup script for CoffeeBreak

METRICS_DIR="/var/lib/prometheus"
RETENTION_DAYS={config.get('metrics_retention_days', 15)}

if [ -d "$METRICS_DIR" ]; then
    # Clean old metrics data
    find "$METRICS_DIR" -name "*.db" -mtime +$RETENTION_DAYS -delete
    find "$METRICS_DIR" -name "*.log" -mtime +$RETENTION_DAYS -delete
    
    echo "Metrics cleanup completed at $(date)"
fi
"""
            
            with open(f"{scripts_dir}/cleanup-metrics.sh", 'w') as f:
                f.write(metrics_cleanup_script)
            os.chmod(f"{scripts_dir}/cleanup-metrics.sh", 0o755)
            
            # System status script
            status_script = f"""#!/bin/bash
# System status script for CoffeeBreak

echo "CoffeeBreak System Status Report"
echo "================================"
echo "Generated: $(date)"
echo "Domain: {domain}"
echo ""

# Service status
echo "Service Status:"
echo "---------------"
services=("nginx" "postgresql" "mongod" "rabbitmq-server" "redis-server" "coffeebreak-api" "coffeebreak-frontend" "coffeebreak-events")

for service in "${{services[@]}}"; do
    if systemctl is-active --quiet "$service" 2>/dev/null; then
        echo "✓ $service: Running"
    else
        echo "✗ $service: Stopped"
    fi
done

echo ""

# System resources
echo "System Resources:"
echo "-----------------"
echo "CPU Usage: $(top -bn1 | grep "Cpu(s)" | awk '{{print $2}}' | sed 's/%us,//')%"
echo "Memory Usage: $(free | awk 'NR==2{{printf "%.1f", $3*100/$2 }}')%"
echo "Disk Usage: $(df / | awk 'NR==2 {{print $5}}')"

echo ""

# HTTPS connectivity
echo "Connectivity:"
echo "-------------"
if curl -s --max-time 10 "https://{domain}/health" > /dev/null; then
    echo "✓ HTTPS: Accessible"
else
    echo "✗ HTTPS: Not accessible"
fi

echo ""

# Recent logs
echo "Recent Errors (last 10):"
echo "------------------------"
journalctl -u coffeebreak-* --since "1 hour ago" --no-pager | grep -i error | tail -10 || echo "No recent errors"
"""
            
            with open(f"{scripts_dir}/system-status.sh", 'w') as f:
                f.write(status_script)
            os.chmod(f"{scripts_dir}/system-status.sh", 0o755)
            
        except Exception as e:
            setup_result['success'] = False
            setup_result['errors'].append(f"Monitoring scripts creation failed: {e}")
        
        return setup_result
    
    def _generate_grafana_docker_config(self, domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Grafana Docker configuration."""
        return {
            'image': 'grafana/grafana:latest',
            'ports': ['3001:3000'],
            'environment': [
                f"GF_SECURITY_ADMIN_PASSWORD={config['grafana_admin_password']}",
                'GF_SECURITY_ADMIN_USER=admin',
                f"GF_SERVER_DOMAIN={domain}",
                'GF_SERVER_ROOT_URL=https://%(domain)s/grafana/',
                'GF_SERVER_SERVE_FROM_SUB_PATH=true'
            ],
            'volumes': [
                './grafana/datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml',
                './grafana/dashboards:/etc/grafana/provisioning/dashboards',
                'grafana-data:/var/lib/grafana'
            ],
            'depends_on': ['prometheus']
        }
    
    def _create_grafana_dashboards(self, grafana_dir: Path) -> None:
        """Create Grafana dashboard configurations."""
        dashboards_dir = grafana_dir / 'dashboards'
        dashboards_dir.mkdir(exist_ok=True)
        
        # Dashboard provisioning config
        dashboard_config = {
            'apiVersion': 1,
            'providers': [{
                'name': 'CoffeeBreak',
                'type': 'file',
                'disableDeletion': False,
                'updateIntervalSeconds': 10,
                'options': {
                    'path': '/etc/grafana/provisioning/dashboards'
                }
            }]
        }
        
        import yaml
        with open(dashboards_dir / 'dashboard.yml', 'w') as f:
            yaml.dump(dashboard_config, f)
        
        # Main dashboard
        main_dashboard = {
            'dashboard': {
                'id': None,
                'title': 'CoffeeBreak Overview',
                'panels': [
                    {
                        'id': 1,
                        'title': 'HTTP Request Rate',
                        'type': 'graph',
                        'targets': [{
                            'expr': 'rate(http_requests_total[5m])',
                            'legendFormat': '{{method}} {{status}}'
                        }]
                    },
                    {
                        'id': 2,
                        'title': 'Response Time',
                        'type': 'graph',
                        'targets': [{
                            'expr': 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))',
                            'legendFormat': '95th percentile'
                        }]
                    },
                    {
                        'id': 3,
                        'title': 'System Resources',
                        'type': 'graph',
                        'targets': [
                            {
                                'expr': 'cpu_usage_percent',
                                'legendFormat': 'CPU %'
                            },
                            {
                                'expr': 'memory_usage_percent',
                                'legendFormat': 'Memory %'
                            }
                        ]
                    }
                ]
            }
        }
        
        import json
        with open(dashboards_dir / 'main-dashboard.json', 'w') as f:
            json.dump(main_dashboard, f, indent=2)
    
    def _install_grafana_standalone(self, config: Dict[str, Any]) -> None:
        """Install Grafana for standalone deployment."""
        try:
            # Add Grafana repository and install
            if subprocess.run(['which', 'apt-get'], capture_output=True).returncode == 0:
                # Ubuntu/Debian
                commands = [
                    ['wget', '-q', '-O', '-', 'https://packages.grafana.com/gpg.key', '|', 'apt-key', 'add', '-'],
                    ['echo', '"deb https://packages.grafana.com/oss/deb stable main"', '|', 'tee', '/etc/apt/sources.list.d/grafana.list'],
                    ['apt-get', 'update'],
                    ['apt-get', 'install', '-y', 'grafana']
                ]
            elif subprocess.run(['which', 'yum'], capture_output=True).returncode == 0:
                # CentOS/RHEL
                commands = [
                    ['yum', 'install', '-y', 'https://dl.grafana.com/oss/release/grafana-8.0.0-1.x86_64.rpm']
                ]
            
            for command in commands:
                subprocess.run(command, check=True)
            
            # Enable and start Grafana
            subprocess.run(['systemctl', 'enable', 'grafana-server'], check=True)
            subprocess.run(['systemctl', 'start', 'grafana-server'], check=True)
            
        except Exception as e:
            raise ConfigurationError(f"Failed to install Grafana: {e}")
    
    def _configure_grafana_standalone(self, domain: str, config: Dict[str, Any]) -> None:
        """Configure Grafana for standalone deployment."""
        try:
            # Update Grafana configuration
            grafana_config = f"""
[server]
domain = {domain}
root_url = https://{domain}/grafana/
serve_from_sub_path = true

[security]
admin_user = admin
admin_password = {config['grafana_admin_password']}

[auth.anonymous]
enabled = false
"""
            
            with open('/etc/grafana/grafana.ini', 'a') as f:
                f.write(grafana_config)
            
            # Restart Grafana
            subprocess.run(['systemctl', 'restart', 'grafana-server'], check=True)
            
        except Exception as e:
            raise ConfigurationError(f"Failed to configure Grafana: {e}")
    
    def _generate_password(self, length: int = 16) -> str:
        """Generate a random password."""
        import secrets
        import string
        
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))