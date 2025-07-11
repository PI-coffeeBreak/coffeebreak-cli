"""Infrastructure management and automation system."""

import os
import subprocess
from typing import Any, Dict, Optional

from ..utils.errors import ConfigurationError
from .deployment import DeploymentOrchestrator
from .maintenance import MaintenanceManager
from .scaling import AutoScaler


class InfrastructureManager:
    """Manages infrastructure automation and orchestration."""

    def __init__(self, deployment_type: str = "docker", verbose: bool = False):
        """
        Initialize infrastructure manager.

        Args:
            deployment_type: Type of deployment (docker, standalone)
            verbose: Enable verbose output
        """
        self.deployment_type = deployment_type
        self.verbose = verbose

        # Initialize components
        self.deployment = DeploymentOrchestrator(
            deployment_type=deployment_type, verbose=verbose
        )
        self.scaling = AutoScaler(deployment_type=deployment_type, verbose=verbose)
        self.maintenance = MaintenanceManager(
            deployment_type=deployment_type, verbose=verbose
        )

    def setup_infrastructure_automation(
        self, domain: str, infrastructure_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Set up comprehensive infrastructure automation.

        Args:
            domain: Production domain
            infrastructure_config: Optional infrastructure configuration

        Returns:
            Dict[str, Any]: Setup results
        """
        try:
            if self.verbose:
                print(f"Setting up infrastructure automation for {domain}")

            setup_result = {
                "success": True,
                "domain": domain,
                "deployment_type": self.deployment_type,
                "components_setup": [],
                "errors": [],
                "automation_scripts": [],
                "orchestration_endpoints": [],
            }

            # Default infrastructure configuration
            config = {
                "domain": domain,
                "enable_zero_downtime_deployment": True,
                "enable_auto_scaling": True,
                "enable_automated_maintenance": True,
                "enable_health_monitoring": True,
                "enable_rollback_automation": True,
                "deployment_strategy": "rolling",  # rolling, blue-green, canary
                "scaling_policy": "adaptive",  # adaptive, scheduled, manual
                "maintenance_window": "02:00-04:00",
                "max_instances": 5,
                "min_instances": 1,
                "cpu_threshold": 70,
                "memory_threshold": 80,
                "health_check_interval": 30,
                "deployment_timeout": 600,
            }

            if infrastructure_config:
                config.update(infrastructure_config)

            # 1. Setup deployment orchestration
            deployment_setup = self.deployment.setup_deployment_orchestration(
                domain, config
            )
            if deployment_setup["success"]:
                setup_result["components_setup"].append("deployment_orchestration")
                setup_result["automation_scripts"].extend(
                    deployment_setup.get("scripts", [])
                )
            else:
                setup_result["errors"].extend(deployment_setup["errors"])

            # 2. Setup auto-scaling
            if config["enable_auto_scaling"]:
                scaling_setup = self.scaling.setup_auto_scaling(domain, config)
                if scaling_setup["success"]:
                    setup_result["components_setup"].append("auto_scaling")
                else:
                    setup_result["errors"].extend(scaling_setup["errors"])

            # 3. Setup automated maintenance
            if config["enable_automated_maintenance"]:
                maintenance_setup = self.maintenance.setup_automated_maintenance(
                    domain, config
                )
                if maintenance_setup["success"]:
                    setup_result["components_setup"].append("automated_maintenance")
                else:
                    setup_result["errors"].extend(maintenance_setup["errors"])

            # 4. Setup infrastructure monitoring
            monitoring_setup = self._setup_infrastructure_monitoring(domain, config)
            if monitoring_setup["success"]:
                setup_result["components_setup"].append("infrastructure_monitoring")
            else:
                setup_result["errors"].extend(monitoring_setup["errors"])

            # 5. Setup orchestration API
            api_setup = self._setup_orchestration_api(domain, config)
            if api_setup["success"]:
                setup_result["components_setup"].append("orchestration_api")
                setup_result["orchestration_endpoints"] = api_setup.get("endpoints", [])
            else:
                setup_result["errors"].extend(api_setup["errors"])

            # 6. Create infrastructure management scripts
            scripts_setup = self._create_infrastructure_scripts(domain, config)
            if scripts_setup["success"]:
                setup_result["components_setup"].append("infrastructure_scripts")
                setup_result["automation_scripts"].extend(
                    scripts_setup.get("scripts", [])
                )
            else:
                setup_result["errors"].extend(scripts_setup["errors"])

            setup_result["success"] = len(setup_result["errors"]) == 0

            if self.verbose:
                if setup_result["success"]:
                    print(
                        f"Infrastructure automation setup completed successfully for {domain}"
                    )
                    print(f"Components: {', '.join(setup_result['components_setup'])}")
                else:
                    print(
                        f"Infrastructure automation setup completed with {len(setup_result['errors'])} errors"
                    )

            return setup_result

        except Exception as e:
            raise ConfigurationError(f"Failed to setup infrastructure automation: {e}")

    def _setup_infrastructure_monitoring(
        self, domain: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Setup infrastructure monitoring and alerting."""
        setup_result = {"success": True, "errors": []}

        try:
            if self.deployment_type == "standalone":
                scripts_dir = "/opt/coffeebreak/bin"
            else:
                scripts_dir = "./scripts"

            # Infrastructure monitoring script
            monitoring_script = f"""#!/bin/bash
# CoffeeBreak Infrastructure Monitoring Script

set -euo pipefail

DOMAIN="{domain}"
LOG_FILE="/var/log/coffeebreak/infrastructure-monitor.log"
ALERT_EMAIL="{config.get("alert_email", "admin@localhost")}"
HEALTH_CHECK_INTERVAL={config.get("health_check_interval", 30)}
CPU_THRESHOLD={config.get("cpu_threshold", 70)}
MEMORY_THRESHOLD={config.get("memory_threshold", 80)}

# Function to log with timestamp
log_message() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}}

# Function to send alert
send_alert() {{
    local subject="$1"
    local message="$2"
    
    log_message "ALERT: $subject"
    
    if command -v mail &> /dev/null && [ -n "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "CoffeeBreak Infrastructure Alert: $subject" "$ALERT_EMAIL"
    fi
    
    if [ -f "/opt/coffeebreak/bin/notify.sh" ]; then
        /opt/coffeebreak/bin/notify.sh "$subject" "$message"
    fi
    
    logger -t coffeebreak-infrastructure "ALERT: $subject - $message"
}}

# Function to check resource usage
check_resource_usage() {{
    log_message "Checking system resource usage"
    
    # Check CPU usage
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{{print $2}}' | sed 's/%us,//' | cut -d'%' -f1)
    cpu_usage=${{cpu_usage%.*}}  # Remove decimals
    
    if [ "$cpu_usage" -gt "$CPU_THRESHOLD" ]; then
        send_alert "High CPU Usage" "CPU usage is $cpu_usage% (threshold: $CPU_THRESHOLD%)"
    fi
    
    # Check memory usage
    local memory_usage=$(free | awk 'NR==2{{printf "%.0f", $3*100/$2 }}')
    
    if [ "$memory_usage" -gt "$MEMORY_THRESHOLD" ]; then
        send_alert "High Memory Usage" "Memory usage is $memory_usage% (threshold: $MEMORY_THRESHOLD%)"
    fi
    
    log_message "Resource usage: CPU $cpu_usage%, Memory $memory_usage%"
}}

# Function to check service health
check_service_health() {{
    log_message "Checking CoffeeBreak service health"
    
    local services=("coffeebreak-api" "coffeebreak-frontend" "coffeebreak-events")
    local failed_services=()
    
    for service in "${{services[@]}}"; do
        if ! systemctl is-active --quiet "$service"; then
            failed_services+=("$service")
            log_message "WARNING: Service $service is not running"
        fi
    done
    
    if [ ${{#failed_services[@]}} -gt 0 ]; then
        send_alert "Service Health Check Failed" "The following services are not running: ${{failed_services[*]}}"
        
        # Attempt automatic restart
        if [ "{config.get("auto_restart_services", True)}" = "True" ]; then
            log_message "Attempting automatic service restart"
            for service in "${{failed_services[@]}}"; do
                systemctl restart "$service" && log_message "Restarted $service" || log_message "Failed to restart $service"
            done
        fi
    else
        log_message "✓ All CoffeeBreak services are running"
    fi
}}

# Function to check application health
check_application_health() {{
    log_message "Checking application health endpoint"
    
    local health_url="https://$DOMAIN/health"
    local response_code=$(curl -s -o /dev/null -w "%{{http_code}}" --max-time 10 "$health_url" || echo "000")
    
    if [ "$response_code" != "200" ]; then
        send_alert "Application Health Check Failed" "Health endpoint returned HTTP $response_code"
    else
        log_message "✓ Application health check passed"
    fi
}}

# Function to check database connectivity
check_database_connectivity() {{
    log_message "Checking database connectivity"
    
    # Check PostgreSQL
    if systemctl is-active --quiet postgresql; then
        if sudo -u postgres psql -c "SELECT 1;" > /dev/null 2>&1; then
            log_message "✓ PostgreSQL connectivity OK"
        else
            send_alert "PostgreSQL Connection Failed" "Cannot connect to PostgreSQL database"
        fi
    fi
    
    # Check MongoDB
    if systemctl is-active --quiet mongod; then
        if mongo --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
            log_message "✓ MongoDB connectivity OK"
        else
            send_alert "MongoDB Connection Failed" "Cannot connect to MongoDB database"
        fi
    fi
}}

# Function to check load balancer health
check_load_balancer() {{
    log_message "Checking load balancer health"
    
    if systemctl is-active --quiet nginx; then
        if nginx -t > /dev/null 2>&1; then
            log_message "✓ Nginx configuration is valid"
        else
            send_alert "Nginx Configuration Invalid" "Nginx configuration test failed"
        fi
    else
        send_alert "Nginx Not Running" "Nginx service is not active"
    fi
}}

# Function to check SSL certificate status
check_ssl_certificates() {{
    log_message "Checking SSL certificate status"
    
    local expiry_days=$(echo | openssl s_client -servername "$DOMAIN" -connect "$DOMAIN:443" 2>/dev/null | \\
                       openssl x509 -noout -dates | grep notAfter | cut -d= -f2 | \\
                       xargs -I{{}} date -d{{}} +%s)
    
    if [ -n "$expiry_days" ]; then
        local current_time=$(date +%s)
        local days_left=$(( (expiry_days - current_time) / 86400 ))
        
        if [ "$days_left" -lt 7 ]; then
            send_alert "SSL Certificate Expiring Soon" "SSL certificate expires in $days_left days"
        elif [ "$days_left" -lt 30 ]; then
            log_message "WARNING: SSL certificate expires in $days_left days"
        else
            log_message "✓ SSL certificate valid for $days_left days"
        fi
    else
        send_alert "SSL Certificate Check Failed" "Unable to check SSL certificate expiry"
    fi
}}

# Function to check disk space
check_disk_space() {{
    log_message "Checking disk space"
    
    local usage=$(df / | awk 'NR==2 {{print $5}}' | sed 's/%//')
    
    if [ "$usage" -gt 90 ]; then
        send_alert "Critical Disk Space" "Disk usage is at $usage%"
    elif [ "$usage" -gt 80 ]; then
        log_message "WARNING: Disk usage is at $usage%"
    else
        log_message "✓ Disk space OK ($usage% used)"
    fi
}}

# Function to check for infrastructure anomalies
check_infrastructure_anomalies() {{
    log_message "Checking for infrastructure anomalies"
    
    # Check for unusual network connections
    local suspicious_connections=$(netstat -tn | grep ESTABLISHED | wc -l)
    if [ "$suspicious_connections" -gt 100 ]; then
        log_message "WARNING: High number of network connections ($suspicious_connections)"
    fi
    
    # Check for high I/O wait
    local iowait=$(top -bn1 | grep "Cpu(s)" | awk '{{print $5}}' | sed 's/%wa,//' | cut -d'%' -f1)
    iowait=${{iowait%.*}}
    if [ "$iowait" -gt 20 ]; then
        log_message "WARNING: High I/O wait time ($iowait%)"
    fi
    
    # Check system load
    local load_average=$(uptime | awk -F'load average:' '{{ print $2 }}' | awk '{{ print $1 }}' | sed 's/,//')
    if (( $(echo "$load_average > 4.0" | bc -l) )); then
        send_alert "High System Load" "System load average is $load_average"
    fi
}}

# Main monitoring function
main() {{
    log_message "Starting infrastructure monitoring check"
    
    check_resource_usage
    check_service_health
    check_application_health
    check_database_connectivity
    check_load_balancer
    check_ssl_certificates
    check_disk_space
    check_infrastructure_anomalies
    
    log_message "Infrastructure monitoring check completed"
}}

# Handle command line arguments
case "${{1:-monitor}}" in
    "monitor")
        main
        ;;
    "resources")
        check_resource_usage
        ;;
    "services")
        check_service_health
        ;;
    "application")
        check_application_health
        ;;
    "databases")
        check_database_connectivity
        ;;
    "ssl")
        check_ssl_certificates
        ;;
    *)
        echo "Usage: $0 {{monitor|resources|services|application|databases|ssl}}"
        exit 1
        ;;
esac
"""

            monitoring_script_path = f"{scripts_dir}/infrastructure-monitor.sh"
            os.makedirs(scripts_dir, exist_ok=True)

            with open(monitoring_script_path, "w") as f:
                f.write(monitoring_script)
            os.chmod(monitoring_script_path, 0o755)

            # Setup cron job for infrastructure monitoring
            cron_entry = f"*/{config.get('health_check_interval', 30)} * * * * {monitoring_script_path}"

            try:
                current_crontab = subprocess.run(
                    ["crontab", "-l"], capture_output=True, text=True
                )
                crontab_content = (
                    current_crontab.stdout if current_crontab.returncode == 0 else ""
                )
            except Exception:
                crontab_content = ""

            if "infrastructure-monitor.sh" not in crontab_content:
                new_crontab = crontab_content.rstrip() + "\\n" + cron_entry + "\\n"
                process = subprocess.Popen(
                    ["crontab", "-"], stdin=subprocess.PIPE, text=True
                )
                process.communicate(input=new_crontab)

            if self.verbose:
                print("Infrastructure monitoring configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(
                f"Infrastructure monitoring setup failed: {e}"
            )

        return setup_result

    def _setup_orchestration_api(
        self, domain: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Setup orchestration API for infrastructure management."""
        setup_result = {"success": True, "errors": [], "endpoints": []}

        try:
            if self.deployment_type == "standalone":
                scripts_dir = "/opt/coffeebreak/bin"
            else:
                scripts_dir = "./scripts"

            # Orchestration API script
            api_script = f"""#!/bin/bash
# CoffeeBreak Infrastructure Orchestration API

set -euo pipefail

API_PORT={config.get("orchestration_api_port", 8080)}
LOG_FILE="/var/log/coffeebreak/orchestration-api.log"

# Function to log with timestamp
log_message() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}}

# Function to handle deployment request
handle_deployment() {{
    local deployment_type="$1"
    local version="${{2:-latest}}"
    
    log_message "Deployment request received: type=$deployment_type, version=$version"
    
    case "$deployment_type" in
        "rolling")
            /opt/coffeebreak/bin/deploy.sh rolling "$version"
            ;;
        "blue-green")
            /opt/coffeebreak/bin/deploy.sh blue-green "$version"
            ;;
        "canary")
            /opt/coffeebreak/bin/deploy.sh canary "$version"
            ;;
        *)
            echo "ERROR: Unknown deployment type: $deployment_type"
            return 1
            ;;
    esac
}}

# Function to handle scaling request
handle_scaling() {{
    local action="$1"
    local instances="${{2:-1}}"
    
    log_message "Scaling request received: action=$action, instances=$instances"
    
    case "$action" in
        "scale-up")
            /opt/coffeebreak/bin/scale.sh up "$instances"
            ;;
        "scale-down")
            /opt/coffeebreak/bin/scale.sh down "$instances"
            ;;
        "auto-scale")
            /opt/coffeebreak/bin/scale.sh auto
            ;;
        *)
            echo "ERROR: Unknown scaling action: $action"
            return 1
            ;;
    esac
}}

# Function to handle maintenance request
handle_maintenance() {{
    local maintenance_type="$1"
    
    log_message "Maintenance request received: type=$maintenance_type"
    
    case "$maintenance_type" in
        "update")
            /opt/coffeebreak/bin/maintenance.sh update
            ;;
        "backup")
            /opt/coffeebreak/bin/backup.sh full
            ;;
        "cleanup")
            /opt/coffeebreak/bin/maintenance.sh cleanup
            ;;
        *)
            echo "ERROR: Unknown maintenance type: $maintenance_type"
            return 1
            ;;
    esac
}}

# Function to get system status
get_status() {{
    local status_type="${{1:-all}}"
    
    case "$status_type" in
        "services")
            systemctl status coffeebreak-* --no-pager
            ;;
        "resources")
            /opt/coffeebreak/bin/infrastructure-monitor.sh resources
            ;;
        "health")
            /opt/coffeebreak/bin/infrastructure-monitor.sh application
            ;;
        "all")
            echo "=== Services ==="
            systemctl status coffeebreak-* --no-pager
            echo
            echo "=== Resources ==="
            /opt/coffeebreak/bin/infrastructure-monitor.sh resources
            echo
            echo "=== Health ==="
            /opt/coffeebreak/bin/infrastructure-monitor.sh application
            ;;
        *)
            echo "ERROR: Unknown status type: $status_type"
            return 1
            ;;
    esac
}}

# Function to start API server
start_api_server() {{
    log_message "Starting orchestration API server on port $API_PORT"
    
    # Simple HTTP server using netcat
    while true; do
        request=$(echo -e "HTTP/1.1 200 OK

CoffeeBreak Orchestration API" | nc -l -p "$API_PORT" -q 1)
        
        # Parse request
        method=$(echo "$request" | head -1 | awk '{{print $1}}')
        path=$(echo "$request" | head -1 | awk '{{print $2}}')
        
        log_message "API request: $method $path"
        
        # Handle different endpoints
        case "$path" in
            "/deploy/"*)
                deployment_type=$(echo "$path" | cut -d'/' -f3)
                version=$(echo "$path" | cut -d'/' -f4)
                handle_deployment "$deployment_type" "$version"
                ;;
            "/scale/"*)
                action=$(echo "$path" | cut -d'/' -f3)
                instances=$(echo "$path" | cut -d'/' -f4)
                handle_scaling "$action" "$instances"
                ;;
            "/maintenance/"*)
                maintenance_type=$(echo "$path" | cut -d'/' -f3)
                handle_maintenance "$maintenance_type"
                ;;
            "/status/"*)
                status_type=$(echo "$path" | cut -d'/' -f3)
                get_status "$status_type"
                ;;
            "/health")
                echo "OK"
                ;;
            *)
                echo "ERROR: Unknown endpoint: $path"
                ;;
        esac
        
        sleep 1
    done
}}

# Main function
main() {{
    local action="${{1:-server}}"
    
    case "$action" in
        "server")
            start_api_server
            ;;
        "deploy")
            handle_deployment "$2" "$3"
            ;;
        "scale")
            handle_scaling "$2" "$3"
            ;;
        "maintenance")
            handle_maintenance "$2"
            ;;
        "status")
            get_status "$2"
            ;;
        *)
            echo "Usage: $0 {{server|deploy|scale|maintenance|status}}"
            exit 1
            ;;
    esac
}}

main "$@"
"""

            api_script_path = f"{scripts_dir}/orchestration-api.sh"
            with open(api_script_path, "w") as f:
                f.write(api_script)
            os.chmod(api_script_path, 0o755)

            # Create systemd service for orchestration API
            if self.deployment_type == "standalone":
                service_content = f"""[Unit]
Description=CoffeeBreak Orchestration API
After=network.target

[Service]
Type=simple
ExecStart={api_script_path} server
Restart=always
RestartSec=10
User=root
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

                with open(
                    "/etc/systemd/system/coffeebreak-orchestration.service", "w"
                ) as f:
                    f.write(service_content)

                subprocess.run(["systemctl", "daemon-reload"], check=True)
                subprocess.run(
                    ["systemctl", "enable", "coffeebreak-orchestration"], check=True
                )
                subprocess.run(
                    ["systemctl", "start", "coffeebreak-orchestration"], check=True
                )

            setup_result["endpoints"] = [
                f"http://localhost:{config.get('orchestration_api_port', 8080)}/health",
                f"http://localhost:{config.get('orchestration_api_port', 8080)}/status/all",
                f"http://localhost:{config.get('orchestration_api_port', 8080)}/deploy/rolling",
                f"http://localhost:{config.get('orchestration_api_port', 8080)}/scale/auto",
            ]

            if self.verbose:
                print("Orchestration API configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Orchestration API setup failed: {e}")

        return setup_result

    def _create_infrastructure_scripts(
        self, domain: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create infrastructure management scripts."""
        setup_result = {"success": True, "errors": [], "scripts": []}

        try:
            if self.deployment_type == "standalone":
                scripts_dir = "/opt/coffeebreak/bin"
            else:
                scripts_dir = "./scripts"

            # Infrastructure status script
            status_script = f"""#!/bin/bash
# CoffeeBreak Infrastructure Status Script

echo "CoffeeBreak Infrastructure Status Report"
echo "======================================="
echo "Generated: $(date)"
echo "Domain: {domain}"
echo

# System information
echo "System Information:"
echo "------------------"
echo "Hostname: $(hostname)"
echo "Uptime: $(uptime)"
echo "Load Average: $(uptime | awk -F'load average:' '{{ print $2 }}')"
echo

# Resource usage
echo "Resource Usage:"
echo "--------------"
echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{{print $2}}')"
echo "Memory: $(free -h | awk 'NR==2{{printf "%s/%s (%.1f%%)", $3,$2,$3*100/$2 }}')"
echo "Disk: $(df -h / | awk 'NR==2{{printf "%s/%s (%s)", $3,$2,$5}}')"
echo

# Service status
echo "Service Status:"
echo "--------------"
services=("nginx" "postgresql" "mongod" "coffeebreak-api" "coffeebreak-frontend" "coffeebreak-events")
for service in "${{services[@]}}"; do
    if systemctl is-active --quiet "$service"; then
        echo "✓ $service: Running"
    else
        echo "✗ $service: Stopped"
    fi
done
echo

# Application health
echo "Application Health:"
echo "------------------"
if curl -s --max-time 10 "https://{domain}/health" > /dev/null; then
    echo "✓ HTTPS: Accessible"
else
    echo "✗ HTTPS: Not accessible"
fi

# Database connectivity
echo
echo "Database Connectivity:"
echo "---------------------"
if sudo -u postgres psql -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✓ PostgreSQL: Connected"
else
    echo "✗ PostgreSQL: Connection failed"
fi

if mongo --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
    echo "✓ MongoDB: Connected"
else
    echo "✗ MongoDB: Connection failed"
fi

# Recent logs
echo
echo "Recent Errors (last 10):"
echo "------------------------"
journalctl -u coffeebreak-* --since "1 hour ago" --no-pager | grep -i error | tail -10 || echo "No recent errors"
"""

            status_script_path = f"{scripts_dir}/infrastructure-status.sh"
            with open(status_script_path, "w") as f:
                f.write(status_script)
            os.chmod(status_script_path, 0o755)

            setup_result["scripts"].append(status_script_path)

            # Infrastructure restart script
            restart_script = f"""#!/bin/bash
# CoffeeBreak Infrastructure Restart Script

set -euo pipefail

LOG_FILE="/var/log/coffeebreak/infrastructure-restart.log"

# Function to log with timestamp
log_message() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}}

# Function to restart service with health check
restart_service() {{
    local service="$1"
    local max_wait="${{2:-60}}"
    
    log_message "Restarting service: $service"
    
    systemctl restart "$service"
    
    # Wait for service to become active
    local wait_time=0
    while [ $wait_time -lt $max_wait ]; do
        if systemctl is-active --quiet "$service"; then
            log_message "Service $service restarted successfully"
            return 0
        fi
        
        sleep 5
        wait_time=$((wait_time + 5))
    done
    
    log_message "ERROR: Service $service failed to start within $max_wait seconds"
    return 1
}}

# Function to perform graceful restart
graceful_restart() {{
    log_message "Starting graceful infrastructure restart"
    
    # Stop application services first
    log_message "Stopping application services..."
    systemctl stop coffeebreak-events || true
    systemctl stop coffeebreak-frontend || true
    systemctl stop coffeebreak-api || true
    
    # Restart infrastructure services
    log_message "Restarting infrastructure services..."
    restart_service nginx
    restart_service postgresql
    restart_service mongod
    
    # Start application services
    log_message "Starting application services..."
    restart_service coffeebreak-api 120
    restart_service coffeebreak-frontend 60
    restart_service coffeebreak-events 60
    
    # Verify health
    log_message "Verifying application health..."
    sleep 10
    
    if curl -s --max-time 10 "https://{domain}/health" > /dev/null; then
        log_message "✓ Application health check passed"
        return 0
    else
        log_message "✗ Application health check failed"
        return 1
    fi
}}

# Function to perform emergency restart
emergency_restart() {{
    log_message "Starting emergency infrastructure restart"
    
    # Force restart all services
    systemctl restart nginx
    systemctl restart postgresql
    systemctl restart mongod
    systemctl restart coffeebreak-*
    
    # Wait and verify
    sleep 15
    
    if curl -s --max-time 10 "https://{domain}/health" > /dev/null; then
        log_message "Emergency restart completed successfully"
    else
        log_message "Emergency restart failed - manual intervention required"
    fi
}}

# Main function
main() {{
    local restart_type="${{1:-graceful}}"
    
    case "$restart_type" in
        "graceful")
            graceful_restart
            ;;
        "emergency")
            emergency_restart
            ;;
        *)
            echo "Usage: $0 {{graceful|emergency}}"
            exit 1
            ;;
    esac
}}

main "$@"
"""

            restart_script_path = f"{scripts_dir}/infrastructure-restart.sh"
            with open(restart_script_path, "w") as f:
                f.write(restart_script)
            os.chmod(restart_script_path, 0o755)

            setup_result["scripts"].append(restart_script_path)

            if self.verbose:
                print("Infrastructure management scripts created")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(
                f"Infrastructure scripts creation failed: {e}"
            )

        return setup_result
