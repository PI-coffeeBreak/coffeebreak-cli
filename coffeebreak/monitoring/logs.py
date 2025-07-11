"""Log management system for production deployments."""

import os
import subprocess
from typing import Any, Dict


class LogManager:
    """Manages log aggregation and processing."""

    def __init__(self, deployment_type: str = "docker", verbose: bool = False):
        """Initialize log manager."""
        self.deployment_type = deployment_type
        self.verbose = verbose

    def setup_log_aggregation(self, domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup log aggregation system."""
        setup_result = {"success": True, "errors": []}

        try:
            # Setup log rotation
            rotation_setup = self._setup_log_rotation(config)
            if not rotation_setup["success"]:
                setup_result["errors"].extend(rotation_setup["errors"])

            # Setup centralized logging
            if config.get("enable_log_aggregation", True):
                centralized_setup = self._setup_centralized_logging(domain, config)
                if not centralized_setup["success"]:
                    setup_result["errors"].extend(centralized_setup["errors"])

            # Setup log monitoring
            monitoring_setup = self._setup_log_monitoring(config)
            if not monitoring_setup["success"]:
                setup_result["errors"].extend(monitoring_setup["errors"])

            setup_result["success"] = len(setup_result["errors"]) == 0

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Log aggregation setup failed: {e}")

        return setup_result

    def _setup_log_rotation(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup log rotation configuration."""
        setup_result = {"success": True, "errors": []}

        try:
            log_retention_days = config.get("log_retention_days", 30)

            # Create logrotate configuration
            logrotate_config = f"""
/var/log/coffeebreak/*.log {{
    daily
    missingok
    rotate {log_retention_days}
    compress
    delaycompress
    notifempty
    copytruncate
    create 644 coffeebreak coffeebreak
    postrotate
        systemctl reload nginx > /dev/null 2>&1 || true
        systemctl reload coffeebreak-* > /dev/null 2>&1 || true
    endscript
}}

/var/log/nginx/*.log {{
    daily
    missingok
    rotate {log_retention_days}
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
    postrotate
        systemctl reload nginx > /dev/null 2>&1 || true
    endscript
}}
"""

            # Write logrotate configuration
            with open("/etc/logrotate.d/coffeebreak", "w") as f:
                f.write(logrotate_config)

            if self.verbose:
                print("Log rotation configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Log rotation setup failed: {e}")

        return setup_result

    def _setup_centralized_logging(self, domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup centralized logging with rsyslog."""
        setup_result = {"success": True, "errors": []}

        try:
            # Configure rsyslog for CoffeeBreak
            rsyslog_config = """
# CoffeeBreak logging configuration
$ModLoad imudp
$UDPServerRun 514
$UDPServerAddress 127.0.0.1

# CoffeeBreak application logs
:programname, isequal, "coffeebreak-api" /var/log/coffeebreak/api.log
:programname, isequal, "coffeebreak-frontend" /var/log/coffeebreak/frontend.log
:programname, isequal, "coffeebreak-events" /var/log/coffeebreak/events.log
:programname, isequal, "coffeebreak-health" /var/log/coffeebreak/health.log

# Stop processing after CoffeeBreak logs
& stop
"""

            # Write rsyslog configuration
            with open("/etc/rsyslog.d/49-coffeebreak.conf", "w") as f:
                f.write(rsyslog_config)

            # Restart rsyslog
            subprocess.run(["systemctl", "restart", "rsyslog"], check=True)

            if self.verbose:
                print("Centralized logging configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Centralized logging setup failed: {e}")

        return setup_result

    def _setup_log_monitoring(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup log monitoring and alerting."""
        setup_result = {"success": True, "errors": []}

        try:
            # Create log monitoring script
            log_monitor_script = """#!/bin/bash
# Log monitoring script for CoffeeBreak

LOG_DIR="/var/log/coffeebreak"
ALERT_PATTERNS=("ERROR" "FATAL" "CRITICAL" "EXCEPTION")
ALERT_EMAIL="${ALERT_EMAIL:-admin@localhost}"
LAST_CHECK_FILE="/tmp/coffeebreak-log-check"

# Get timestamp of last check
if [ -f "$LAST_CHECK_FILE" ]; then
    LAST_CHECK=$(cat "$LAST_CHECK_FILE")
else
    LAST_CHECK=$(date -d "1 minute ago" +%s)
fi

# Update last check timestamp
date +%s > "$LAST_CHECK_FILE"

# Function to send alert
send_alert() {
    local log_file="$1"
    local pattern="$2"
    local count="$3"

    local subject="CoffeeBreak Log Alert: $pattern in $log_file"
    local message="Found $count occurrences of '$pattern' in $log_file since last check"

    echo "$message" | logger -t coffeebreak-log-monitor

    if command -v mail &> /dev/null && [ -n "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "$subject" "$ALERT_EMAIL"
    fi
}

# Check each log file for alert patterns
for log_file in "$LOG_DIR"/*.log; do
    if [ -f "$log_file" ]; then
        for pattern in "${ALERT_PATTERNS[@]}"; do
            # Count occurrences since last check
            count=$(awk -v last_check="$LAST_CHECK" -v pattern="$pattern" '
                {
                    # Simple timestamp parsing (adjust based on your log format)
                    if (index($0, pattern) > 0) {
                        print $0
                    }
                }
            ' "$log_file" | wc -l)

            if [ "$count" -gt 0 ]; then
                send_alert "$(basename "$log_file")" "$pattern" "$count"
            fi
        done
    fi
done
"""

            # Write log monitoring script
            if self.deployment_type == "standalone":
                script_path = "/opt/coffeebreak/bin/log-monitor.sh"
            else:
                script_path = "./log-monitor.sh"

            os.makedirs(os.path.dirname(script_path), exist_ok=True)

            with open(script_path, "w") as f:
                f.write(log_monitor_script)
            os.chmod(script_path, 0o755)

            # Setup cron job for log monitoring
            cron_entry = f"*/5 * * * * {script_path}"

            try:
                current_crontab = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
                crontab_content = current_crontab.stdout if current_crontab.returncode == 0 else ""
            except Exception:
                crontab_content = ""

            if "log-monitor.sh" not in crontab_content:
                new_crontab = crontab_content.rstrip() + "\n" + cron_entry + "\n"
                process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
                process.communicate(input=new_crontab)

            if self.verbose:
                print("Log monitoring configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Log monitoring setup failed: {e}")

        return setup_result
