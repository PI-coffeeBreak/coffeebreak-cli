"""Automated maintenance system for CoffeeBreak infrastructure."""

import os
import subprocess
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json

from ..utils.errors import ConfigurationError


class MaintenanceManager:
    """Manages automated maintenance tasks and procedures."""

    def __init__(self, deployment_type: str = "docker", verbose: bool = False):
        """
        Initialize maintenance manager.

        Args:
            deployment_type: Type of deployment (docker, standalone)
            verbose: Enable verbose output
        """
        self.deployment_type = deployment_type
        self.verbose = verbose

    def setup_automated_maintenance(
        self, domain: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Setup automated maintenance system.

        Args:
            domain: Production domain
            config: Maintenance configuration

        Returns:
            Dict[str, Any]: Setup results
        """
        setup_result = {"success": True, "errors": []}

        try:
            if self.deployment_type == "standalone":
                scripts_dir = "/opt/coffeebreak/bin"
            else:
                scripts_dir = "./scripts"

            # Create maintenance scripts
            scripts_result = self._create_maintenance_scripts(
                domain, config, scripts_dir
            )
            if not scripts_result["success"]:
                setup_result["errors"].extend(scripts_result["errors"])

            # Setup maintenance scheduling
            scheduling_result = self._setup_maintenance_scheduling(
                domain, config, scripts_dir
            )
            if not scheduling_result["success"]:
                setup_result["errors"].extend(scheduling_result["errors"])

            # Setup maintenance windows
            windows_result = self._setup_maintenance_windows(
                domain, config, scripts_dir
            )
            if not windows_result["success"]:
                setup_result["errors"].extend(windows_result["errors"])

            setup_result["success"] = len(setup_result["errors"]) == 0

            if self.verbose:
                print("Automated maintenance configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Automated maintenance setup failed: {e}")

        return setup_result

    def _create_maintenance_scripts(
        self, domain: str, config: Dict[str, Any], scripts_dir: str
    ) -> Dict[str, Any]:
        """Create automated maintenance scripts."""
        setup_result = {"success": True, "errors": []}

        try:
            # Main maintenance script
            maintenance_script = f"""#!/bin/bash
# CoffeeBreak Automated Maintenance Script

set -euo pipefail

DOMAIN="{domain}"
LOG_FILE="/var/log/coffeebreak/maintenance.log"
MAINTENANCE_WINDOW_START="{config.get("maintenance_window", "02:00").split("-")[0]}"
MAINTENANCE_WINDOW_END="{config.get("maintenance_window", "04:00").split("-")[1] if "-" in config.get("maintenance_window", "02:00-04:00") else "04:00"}"

# Function to log with timestamp
log_message() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}}

# Function to send alert
send_alert() {{
    local subject="$1"
    local message="$2"
    
    log_message "ALERT: $subject"
    
    if [ -f "/opt/coffeebreak/bin/notify.sh" ]; then
        /opt/coffeebreak/bin/notify.sh "$subject" "$message"
    fi
    
    logger -t coffeebreak-maintenance "ALERT: $subject - $message"
}}

# Function to check if we're in maintenance window
is_maintenance_window() {{
    local current_time=$(date +%H:%M)
    local start_time="$MAINTENANCE_WINDOW_START"
    local end_time="$MAINTENANCE_WINDOW_END"
    
    # Convert times to minutes for comparison
    local current_minutes=$(date -d "$current_time" +%H:%M | awk -F: '{{print ($1 * 60) + $2}}')
    local start_minutes=$(date -d "$start_time" +%H:%M | awk -F: '{{print ($1 * 60) + $2}}')
    local end_minutes=$(date -d "$end_time" +%H:%M | awk -F: '{{print ($1 * 60) + $2}}')
    
    # Handle overnight window (e.g., 23:00-03:00)
    if [ $start_minutes -gt $end_minutes ]; then
        # Overnight window
        if [ $current_minutes -ge $start_minutes ] || [ $current_minutes -le $end_minutes ]; then
            return 0
        fi
    else
        # Same day window
        if [ $current_minutes -ge $start_minutes ] && [ $current_minutes -le $end_minutes ]; then
            return 0
        fi
    fi
    
    return 1
}}

# Function to perform system updates
perform_system_updates() {{
    log_message "Starting system updates"
    
    if ! is_maintenance_window; then
        log_message "Not in maintenance window, skipping system updates"
        return 0
    fi
    
    # Update package lists
    if command -v apt-get &> /dev/null; then
        log_message "Updating apt package lists"
        apt-get update -qq || log_message "WARNING: Failed to update package lists"
        
        # Install security updates only
        log_message "Installing security updates"
        DEBIAN_FRONTEND=noninteractive apt-get upgrade -y --only-upgrade \\
            $(apt list --upgradable 2>/dev/null | grep -i security | cut -d'/' -f1) 2>/dev/null || true
            
    elif command -v yum &> /dev/null; then
        log_message "Installing system updates with yum"
        yum update -y --security || log_message "WARNING: Failed to install updates"
    fi
    
    log_message "System updates completed"
}}

# Function to clean temporary files
cleanup_temp_files() {{
    log_message "Starting temporary file cleanup"
    
    # Clean /tmp files older than 7 days
    find /tmp -type f -mtime +7 -delete 2>/dev/null || true
    
    # Clean log files older than retention period
    local log_retention_days={config.get("log_retention_days", 30)}
    find /var/log -name "*.log" -mtime +$log_retention_days -delete 2>/dev/null || true
    
    # Clean old deployment artifacts
    if [ -d "/opt/coffeebreak/deployments" ]; then
        find /opt/coffeebreak/deployments -name "*.json" -mtime +30 -delete 2>/dev/null || true
    fi
    
    # Clean Docker artifacts (if Docker is available)
    if command -v docker &> /dev/null; then
        log_message "Cleaning Docker artifacts"
        docker system prune -f --volumes || true
        docker image prune -a -f || true
    fi
    
    log_message "Temporary file cleanup completed"
}}

# Function to optimize databases
optimize_databases() {{
    log_message "Starting database optimization"
    
    if ! is_maintenance_window; then
        log_message "Not in maintenance window, skipping database optimization"
        return 0
    fi
    
    # PostgreSQL optimization
    if systemctl is-active --quiet postgresql; then
        log_message "Optimizing PostgreSQL databases"
        
        # Get list of databases
        local databases=$(sudo -u postgres psql -t -c "SELECT datname FROM pg_database WHERE NOT datistemplate AND datname != 'postgres';" 2>/dev/null || echo "")
        
        for db in $databases; do
            db=$(echo "$db" | xargs)  # Trim whitespace
            if [ -n "$db" ]; then
                log_message "Analyzing database: $db"
                sudo -u postgres psql -d "$db" -c "ANALYZE;" 2>/dev/null || log_message "WARNING: Failed to analyze $db"
                
                log_message "Vacuuming database: $db"
                sudo -u postgres psql -d "$db" -c "VACUUM;" 2>/dev/null || log_message "WARNING: Failed to vacuum $db"
            fi
        done
    fi
    
    # MongoDB optimization
    if systemctl is-active --quiet mongod; then
        log_message "Optimizing MongoDB databases"
        
        # Compact collections and reindex
        mongo --eval "
            db.adminCommand('listCollections').cursor.firstBatch.forEach(
                function(collection) {{
                    db.runCommand({{compact: collection.name}});
                    db[collection.name].reIndex();
                }}
            );
        " 2>/dev/null || log_message "WARNING: Failed to optimize MongoDB"
    fi
    
    log_message "Database optimization completed"
}}

# Function to rotate logs
rotate_logs() {{
    log_message "Starting log rotation"
    
    # Force logrotate to run
    /usr/sbin/logrotate -f /etc/logrotate.conf 2>/dev/null || true
    
    # Rotate CoffeeBreak specific logs
    if [ -d "/var/log/coffeebreak" ]; then
        find /var/log/coffeebreak -name "*.log" -size +100M -exec gzip {{}} \\; 2>/dev/null || true
    fi
    
    log_message "Log rotation completed"
}}

# Function to check and update SSL certificates
update_ssl_certificates() {{
    log_message "Checking SSL certificates"
    
    # Check certificate expiry
    local expiry_days=$(echo | openssl s_client -servername "$DOMAIN" -connect "$DOMAIN:443" 2>/dev/null | \\
                       openssl x509 -noout -dates | grep notAfter | cut -d= -f2 | \\
                       xargs -I{{}} date -d{{}} +%s)
    
    if [ -n "$expiry_days" ]; then
        local current_time=$(date +%s)
        local days_left=$(( (expiry_days - current_time) / 86400 ))
        
        log_message "SSL certificate expires in $days_left days"
        
        # Renew if expires in less than 30 days
        if [ "$days_left" -lt 30 ]; then
            log_message "Renewing SSL certificate"
            
            if command -v certbot &> /dev/null; then
                certbot renew --quiet || log_message "WARNING: Failed to renew SSL certificate"
                
                # Reload nginx if certificate was renewed
                if systemctl is-active --quiet nginx; then
                    systemctl reload nginx || log_message "WARNING: Failed to reload nginx"
                fi
            fi
        fi
    fi
}}

# Function to perform health checks
perform_health_checks() {{
    log_message "Performing health checks"
    
    # Check service status
    local services=("nginx" "postgresql" "mongod" "coffeebreak-api" "coffeebreak-frontend" "coffeebreak-events")
    local failed_services=()
    
    for service in "${{services[@]}}"; do
        if ! systemctl is-active --quiet "$service"; then
            failed_services+=("$service")
        fi
    done
    
    if [ ${{#failed_services[@]}} -gt 0 ]; then
        send_alert "Service Health Check Failed" "The following services are not running: ${{failed_services[*]}}"
    fi
    
    # Check application health
    if ! curl -s --max-time 10 "https://$DOMAIN/health" > /dev/null; then
        send_alert "Application Health Check Failed" "Application health endpoint is not responding"
    fi
    
    # Check disk space
    local disk_usage=$(df / | awk 'NR==2 {{print $5}}' | sed 's/%//')
    if [ "$disk_usage" -gt 85 ]; then
        send_alert "High Disk Usage" "Disk usage is at $disk_usage%"
    fi
    
    log_message "Health checks completed"
}}

# Function to backup critical data
backup_critical_data() {{
    log_message "Starting critical data backup"
    
    # Perform incremental backup
    if [ -f "/opt/coffeebreak/bin/backup.sh" ]; then
        /opt/coffeebreak/bin/backup.sh incremental || log_message "WARNING: Backup failed"
    fi
    
    log_message "Critical data backup completed"
}}

# Function to update application dependencies
update_dependencies() {{
    log_message "Checking for dependency updates"
    
    if ! is_maintenance_window; then
        log_message "Not in maintenance window, skipping dependency updates"
        return 0
    fi
    
    # Update Node.js dependencies (if package.json exists)
    if [ -f "/opt/coffeebreak/package.json" ]; then
        log_message "Updating Node.js dependencies"
        cd /opt/coffeebreak
        npm audit fix --only=prod 2>/dev/null || log_message "WARNING: Failed to update Node.js dependencies"
    fi
    
    # Update Python dependencies (if requirements.txt exists)
    if [ -f "/opt/coffeebreak/requirements.txt" ]; then
        log_message "Updating Python dependencies"
        cd /opt/coffeebreak
        pip install --upgrade -r requirements.txt 2>/dev/null || log_message "WARNING: Failed to update Python dependencies"
    fi
    
    log_message "Dependency updates completed"
}}

# Function to generate maintenance report
generate_maintenance_report() {{
    local report_file="/var/log/coffeebreak/maintenance-report-$(date +%Y%m%d).log"
    
    {{
        echo "CoffeeBreak Maintenance Report"
        echo "=============================="
        echo "Generated: $(date)"
        echo "Domain: $DOMAIN"
        echo
        
        echo "System Information:"
        echo "- Uptime: $(uptime)"
        echo "- Load Average: $(uptime | awk -F'load average:' '{{ print $2 }}')"
        echo "- Disk Usage: $(df -h / | awk 'NR==2{{print $5}}')"
        echo "- Memory Usage: $(free -h | awk 'NR==2{{printf \"%s/%s\", $3,$2}}')"
        echo
        
        echo "Service Status:"
        local services=("nginx" "postgresql" "mongod" "coffeebreak-api" "coffeebreak-frontend" "coffeebreak-events")
        for service in "${{services[@]}}"; do
            if systemctl is-active --quiet "$service"; then
                echo "- $service: Running"
            else
                echo "- $service: Stopped"
            fi
        done
        echo
        
        echo "Recent Maintenance Activities:"
        tail -20 "$LOG_FILE" | grep "$(date +%Y-%m-%d)" || echo "No activities today"
        
    }} > "$report_file"
    
    log_message "Maintenance report generated: $report_file"
}}

# Main maintenance functions
perform_daily_maintenance() {{
    log_message "Starting daily maintenance tasks"
    
    cleanup_temp_files
    rotate_logs
    perform_health_checks
    backup_critical_data
    
    log_message "Daily maintenance tasks completed"
}}

perform_weekly_maintenance() {{
    log_message "Starting weekly maintenance tasks"
    
    perform_daily_maintenance
    optimize_databases
    update_ssl_certificates
    
    log_message "Weekly maintenance tasks completed"
}}

perform_monthly_maintenance() {{
    log_message "Starting monthly maintenance tasks"
    
    perform_weekly_maintenance
    perform_system_updates
    update_dependencies
    generate_maintenance_report
    
    log_message "Monthly maintenance tasks completed"
}}

# Function to perform emergency maintenance
perform_emergency_maintenance() {{
    log_message "Starting emergency maintenance"
    
    # Stop non-essential services temporarily
    systemctl stop coffeebreak-events || true
    
    # Clear caches
    if [ -d "/opt/coffeebreak/cache" ]; then
        rm -rf /opt/coffeebreak/cache/*
    fi
    
    # Restart essential services
    systemctl restart nginx
    systemctl restart coffeebreak-api
    systemctl restart coffeebreak-frontend
    systemctl start coffeebreak-events
    
    # Verify health
    sleep 10
    if curl -s --max-time 10 "https://$DOMAIN/health" > /dev/null; then
        log_message "Emergency maintenance completed successfully"
        send_alert "Emergency Maintenance Completed" "Emergency maintenance procedures completed successfully"
    else
        log_message "Emergency maintenance failed - manual intervention required"
        send_alert "Emergency Maintenance Failed" "Emergency maintenance failed - manual intervention required"
    fi
}}

# Main maintenance function
main() {{
    local maintenance_type="${{1:-daily}}"
    
    log_message "Maintenance task started: $maintenance_type"
    
    case "$maintenance_type" in
        "daily")
            perform_daily_maintenance
            ;;
        "weekly")
            perform_weekly_maintenance
            ;;
        "monthly")
            perform_monthly_maintenance
            ;;
        "emergency")
            perform_emergency_maintenance
            ;;
        "update")
            perform_system_updates
            update_dependencies
            ;;
        "cleanup")
            cleanup_temp_files
            ;;
        "health")
            perform_health_checks
            ;;
        "backup")
            backup_critical_data
            ;;
        "ssl")
            update_ssl_certificates
            ;;
        "report")
            generate_maintenance_report
            ;;
        *)
            echo "Usage: $0 {{daily|weekly|monthly|emergency|update|cleanup|health|backup|ssl|report}}"
            exit 1
            ;;
    esac
    
    log_message "Maintenance task completed: $maintenance_type"
}}

main "$@"
"""

            maintenance_script_path = f"{scripts_dir}/maintenance.sh"
            with open(maintenance_script_path, "w") as f:
                f.write(maintenance_script)
            os.chmod(maintenance_script_path, 0o755)

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Maintenance scripts creation failed: {e}")

        return setup_result

    def _setup_maintenance_scheduling(
        self, domain: str, config: Dict[str, Any], scripts_dir: str
    ) -> Dict[str, Any]:
        """Setup maintenance task scheduling."""
        setup_result = {"success": True, "errors": []}

        try:
            # Maintenance scheduling configuration
            maintenance_schedule = [
                "# CoffeeBreak maintenance tasks",
                "0 3 * * * /opt/coffeebreak/bin/maintenance.sh daily",  # Daily at 3 AM
                "0 4 * * 0 /opt/coffeebreak/bin/maintenance.sh weekly",  # Weekly on Sunday at 4 AM
                "0 5 1 * * /opt/coffeebreak/bin/maintenance.sh monthly",  # Monthly on 1st at 5 AM
                "*/30 * * * * /opt/coffeebreak/bin/maintenance.sh health",  # Health checks every 30 minutes
            ]

            # Get current crontab
            try:
                current_crontab = subprocess.run(
                    ["crontab", "-l"], capture_output=True, text=True
                )
                crontab_content = (
                    current_crontab.stdout if current_crontab.returncode == 0 else ""
                )
            except:
                crontab_content = ""

            # Add new maintenance entries
            new_entries = []
            for entry in maintenance_schedule:
                if "maintenance.sh" in entry and entry not in crontab_content:
                    new_entries.append(entry)

            if new_entries:
                new_crontab = crontab_content.rstrip()
                if new_crontab:
                    new_crontab += "\\n"
                new_crontab += "\\n".join(new_entries) + "\\n"

                process = subprocess.Popen(
                    ["crontab", "-"], stdin=subprocess.PIPE, text=True
                )
                process.communicate(input=new_crontab)

            if self.verbose:
                print("Maintenance scheduling configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Maintenance scheduling setup failed: {e}")

        return setup_result

    def _setup_maintenance_windows(
        self, domain: str, config: Dict[str, Any], scripts_dir: str
    ) -> Dict[str, Any]:
        """Setup maintenance windows and policies."""
        setup_result = {"success": True, "errors": []}

        try:
            # Create maintenance window configuration
            maintenance_config = {
                "maintenance_windows": [
                    {
                        "name": "daily_maintenance",
                        "start_time": "02:00",
                        "end_time": "04:00",
                        "days": [1, 2, 3, 4, 5, 6, 7],
                        "allowed_operations": ["cleanup", "health_checks", "backups"],
                        "description": "Daily maintenance window",
                    },
                    {
                        "name": "weekly_maintenance",
                        "start_time": "01:00",
                        "end_time": "05:00",
                        "days": [7],  # Sunday
                        "allowed_operations": ["updates", "optimization", "restarts"],
                        "description": "Weekly maintenance window",
                    },
                ],
                "emergency_procedures": {
                    "max_downtime_minutes": 15,
                    "notification_channels": ["email", "webhook"],
                    "rollback_timeout_minutes": 5,
                    "health_check_retries": 3,
                },
                "maintenance_policies": {
                    "require_approval": config.get(
                        "require_maintenance_approval", False
                    ),
                    "auto_rollback_on_failure": True,
                    "max_concurrent_operations": 1,
                    "pre_maintenance_backup": True,
                },
            }

            if self.deployment_type == "standalone":
                config_dir = "/opt/coffeebreak/config"
            else:
                config_dir = "./config"

            os.makedirs(config_dir, exist_ok=True)

            config_file = f"{config_dir}/maintenance-config.json"
            with open(config_file, "w") as f:
                json.dump(maintenance_config, f, indent=2)

            # Create maintenance window checker script
            window_checker_script = f"""#!/bin/bash
# CoffeeBreak Maintenance Window Checker

CONFIG_FILE="{config_file}"

# Function to check if current time is in maintenance window
check_maintenance_window() {{
    local operation_type="${{1:-general}}"
    local current_time=$(date +%H:%M)
    local current_day=$(date +%u)  # 1=Monday, 7=Sunday
    
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "false"
        return 1
    fi
    
    # Check if operation is allowed in any current maintenance window
    local allowed=$(jq -r --arg time "$current_time" --arg day "$current_day" --arg op "$operation_type" '
        .maintenance_windows[] | 
        select(
            (.days[] | tostring) == $day and
            (.allowed_operations[] | contains($op) or $op == "general") and
            (
                ($time >= .start_time and $time <= .end_time) or
                (.start_time > .end_time and ($time >= .start_time or $time <= .end_time))
            )
        ) | 
        .name
    ' "$CONFIG_FILE" | head -1)
    
    if [ -n "$allowed" ] && [ "$allowed" != "null" ]; then
        echo "true"
        return 0
    else
        echo "false"
        return 1
    fi
}}

# Function to get next maintenance window
get_next_maintenance_window() {{
    local operation_type="${{1:-general}}"
    
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "No maintenance window configuration found"
        return 1
    fi
    
    echo "Next maintenance windows for '$operation_type' operations:"
    jq -r --arg op "$operation_type" '
        .maintenance_windows[] | 
        select(.allowed_operations[] | contains($op) or $op == "general") |
        "\\(.name): \\(.start_time)-\\(.end_time) on days \\(.days | join(\",\\"))"
    ' "$CONFIG_FILE"
}}

# Main function
main() {{
    local action="${{1:-check}}"
    local operation_type="$2"
    
    case "$action" in
        "check")
            check_maintenance_window "$operation_type"
            ;;
        "next")
            get_next_maintenance_window "$operation_type"
            ;;
        *)
            echo "Usage: $0 {{check|next}} [operation_type]"
            exit 1
            ;;
    esac
}}

main "$@"
"""

            window_checker_path = f"{scripts_dir}/maintenance-window.sh"
            with open(window_checker_path, "w") as f:
                f.write(window_checker_script)
            os.chmod(window_checker_path, 0o755)

            if self.verbose:
                print("Maintenance windows configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Maintenance windows setup failed: {e}")

        return setup_result
