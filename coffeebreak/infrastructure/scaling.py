"""Auto-scaling system for CoffeeBreak infrastructure."""

import json
import os
import subprocess
from typing import Any, Dict


class AutoScaler:
    """Manages automatic scaling of CoffeeBreak infrastructure."""

    def __init__(self, deployment_type: str = "docker", verbose: bool = False):
        """
        Initialize auto-scaler.

        Args:
            deployment_type: Type of deployment (docker, standalone)
            verbose: Enable verbose output
        """
        self.deployment_type = deployment_type
        self.verbose = verbose

    def setup_auto_scaling(self, domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Setup auto-scaling system.

        Args:
            domain: Production domain
            config: Scaling configuration

        Returns:
            Dict[str, Any]: Setup results
        """
        setup_result = {"success": True, "errors": []}

        try:
            if self.deployment_type == "standalone":
                scripts_dir = "/opt/coffeebreak/bin"
            else:
                scripts_dir = "./scripts"

            # Create scaling scripts
            scripts_result = self._create_scaling_scripts(domain, config, scripts_dir)
            if not scripts_result["success"]:
                setup_result["errors"].extend(scripts_result["errors"])

            # Setup scaling policies
            policies_result = self._setup_scaling_policies(domain, config, scripts_dir)
            if not policies_result["success"]:
                setup_result["errors"].extend(policies_result["errors"])

            # Setup scaling monitoring
            monitoring_result = self._setup_scaling_monitoring(domain, config, scripts_dir)
            if not monitoring_result["success"]:
                setup_result["errors"].extend(monitoring_result["errors"])

            setup_result["success"] = len(setup_result["errors"]) == 0

            if self.verbose:
                print("Auto-scaling configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Auto-scaling setup failed: {e}")

        return setup_result

    def _create_scaling_scripts(self, domain: str, config: Dict[str, Any], scripts_dir: str) -> Dict[str, Any]:
        """Create scaling management scripts."""
        setup_result = {"success": True, "errors": []}

        try:
            # Main scaling script
            scaling_script = f"""#!/bin/bash
# CoffeeBreak Auto-Scaling Script

set -euo pipefail

DOMAIN="{domain}"
LOG_FILE="/var/log/coffeebreak/scaling.log"
MIN_INSTANCES={config.get("min_instances", 1)}
MAX_INSTANCES={config.get("max_instances", 5)}
CPU_SCALE_UP_THRESHOLD={config.get("cpu_threshold", 70)}
CPU_SCALE_DOWN_THRESHOLD={config.get("cpu_scale_down_threshold", 30)}
MEMORY_SCALE_UP_THRESHOLD={config.get("memory_threshold", 80)}
MEMORY_SCALE_DOWN_THRESHOLD={config.get("memory_scale_down_threshold", 40)}
SCALE_COOLDOWN={config.get("scale_cooldown", 300)}  # 5 minutes

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

    logger -t coffeebreak-scaling "ALERT: $subject - $message"
}}

# Function to get current instance count
get_current_instances() {{
    if [ "{self.deployment_type}" = "docker" ]; then
        # For Docker deployment, count running containers
        docker ps --filter "name=coffeebreak" --format "table {{{{.Names}}}}" | grep -c coffeebreak || echo "1"
    else
        # For standalone deployment, count active services
        systemctl list-units --state=active coffeebreak-* | grep -c coffeebreak || echo "1"
    fi
}}

# Function to get resource metrics
get_resource_metrics() {{
    # Get CPU usage
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{{print $2}}' | sed 's/%us,//' | cut -d'%' -f1)
    cpu_usage=${{cpu_usage%.*}}  # Remove decimals

    # Get memory usage
    local memory_usage=$(free | awk 'NR==2{{printf "%.0f", $3*100/$2 }}')

    # Get load average
    local load_average=$(uptime | awk -F'load average:' '{{ print $2 }}' | awk '{{ print $1 }}' | sed 's/,//')

    echo "$cpu_usage,$memory_usage,$load_average"
}}

# Function to check if scaling is on cooldown
is_scaling_on_cooldown() {{
    local cooldown_file="/tmp/coffeebreak-scaling-cooldown"

    if [ -f "$cooldown_file" ]; then
        local last_scale=$(cat "$cooldown_file")
        local current_time=$(date +%s)
        local time_diff=$((current_time - last_scale))

        if [ $time_diff -lt $SCALE_COOLDOWN ]; then
            log_message "Scaling on cooldown ($((SCALE_COOLDOWN - time_diff)) seconds remaining)"
            return 0
        fi
    fi

    return 1
}}

# Function to set scaling cooldown
set_scaling_cooldown() {{
    local cooldown_file="/tmp/coffeebreak-scaling-cooldown"
    date +%s > "$cooldown_file"
}}

# Function to scale up
scale_up() {{
    local target_instances="$1"
    local current_instances=$(get_current_instances)

    if [ "$target_instances" -le "$current_instances" ]; then
        log_message "Target instances ($target_instances) not greater than current ($current_instances), skipping scale up"
        return 0
    fi

    if [ "$target_instances" -gt "$MAX_INSTANCES" ]; then
        target_instances=$MAX_INSTANCES
        log_message "Target instances capped at maximum: $MAX_INSTANCES"
    fi

    log_message "Scaling up from $current_instances to $target_instances instances"

    if [ "{self.deployment_type}" = "docker" ]; then
        # Scale Docker services
        local services=("coffeebreak-api" "coffeebreak-frontend" "coffeebreak-events")

        for service in "${{services[@]}}"; do
            log_message "Scaling Docker service: $service"
            docker service scale "$service=$target_instances" || log_message "WARNING: Failed to scale $service"
        done
    else
        # Scale standalone services (create additional service instances)
        local additional_instances=$((target_instances - current_instances))

        for i in $(seq 1 $additional_instances); do
            local instance_num=$((current_instances + i))

            # Create additional service instances
            log_message "Creating additional service instance: $instance_num"

            # This would involve creating new systemd services or process instances
            # Implementation depends on specific architecture
        done
    fi

    set_scaling_cooldown
    send_alert "Scaled Up" "Scaled from $current_instances to $target_instances instances"
}}

# Function to scale down
scale_down() {{
    local target_instances="$1"
    local current_instances=$(get_current_instances)

    if [ "$target_instances" -ge "$current_instances" ]; then
        log_message "Target instances ($target_instances) not less than current ($current_instances), skipping scale down"
        return 0
    fi

    if [ "$target_instances" -lt "$MIN_INSTANCES" ]; then
        target_instances=$MIN_INSTANCES
        log_message "Target instances raised to minimum: $MIN_INSTANCES"
    fi

    log_message "Scaling down from $current_instances to $target_instances instances"

    if [ "{self.deployment_type}" = "docker" ]; then
        # Scale Docker services
        local services=("coffeebreak-api" "coffeebreak-frontend" "coffeebreak-events")

        for service in "${{services[@]}}"; do
            log_message "Scaling Docker service: $service"
            docker service scale "$service=$target_instances" || log_message "WARNING: Failed to scale $service"
        done
    else
        # Scale down standalone services
        local instances_to_remove=$((current_instances - target_instances))

        for i in $(seq 1 $instances_to_remove); do
            local instance_num=$((current_instances - i + 1))

            # Remove service instances
            log_message "Removing service instance: $instance_num"

            # This would involve stopping and removing systemd services
            # Implementation depends on specific architecture
        done
    fi

    set_scaling_cooldown
    send_alert "Scaled Down" "Scaled from $current_instances to $target_instances instances"
}}

# Function to perform adaptive scaling
adaptive_scaling() {{
    log_message "Performing adaptive scaling evaluation"

    if is_scaling_on_cooldown; then
        return 0
    fi

    local metrics=$(get_resource_metrics)
    local cpu_usage=$(echo "$metrics" | cut -d',' -f1)
    local memory_usage=$(echo "$metrics" | cut -d',' -f2)
    local load_average=$(echo "$metrics" | cut -d',' -f3)
    local current_instances=$(get_current_instances)

    log_message "Current metrics: CPU=$cpu_usage%, Memory=$memory_usage%, Load=$load_average, Instances=$current_instances"

    # Determine if scaling is needed
    local scale_action=""
    local target_instances=$current_instances

    # Scale up conditions
    if [ "$cpu_usage" -gt "$CPU_SCALE_UP_THRESHOLD" ] || [ "$memory_usage" -gt "$MEMORY_SCALE_UP_THRESHOLD" ]; then
        scale_action="up"

        # Calculate target instances based on resource usage
        if [ "$cpu_usage" -gt "$CPU_SCALE_UP_THRESHOLD" ]; then
            local cpu_scale_factor=$(echo "scale=0; $cpu_usage / $CPU_SCALE_UP_THRESHOLD" | bc)
            target_instances=$((current_instances + cpu_scale_factor))
        fi

        if [ "$memory_usage" -gt "$MEMORY_SCALE_UP_THRESHOLD" ]; then
            local memory_scale_factor=$(echo "scale=0; $memory_usage / $MEMORY_SCALE_UP_THRESHOLD" | bc)
            local memory_target=$((current_instances + memory_scale_factor))

            if [ "$memory_target" -gt "$target_instances" ]; then
                target_instances=$memory_target
            fi
        fi

    # Scale down conditions
    elif [ "$cpu_usage" -lt "$CPU_SCALE_DOWN_THRESHOLD" ] && [ "$memory_usage" -lt "$MEMORY_SCALE_DOWN_THRESHOLD" ] && [ "$current_instances" -gt "$MIN_INSTANCES" ]; then
        scale_action="down"

        # Conservative scale down - reduce by 1 instance at a time
        target_instances=$((current_instances - 1))
    fi

    # Execute scaling action
    case "$scale_action" in
        "up")
            scale_up "$target_instances"
            ;;
        "down")
            scale_down "$target_instances"
            ;;
        *)
            log_message "No scaling action required"
            ;;
    esac
}}

# Function to perform scheduled scaling
scheduled_scaling() {{
    local schedule_config="/opt/coffeebreak/config/scaling-schedule.json"

    if [ ! -f "$schedule_config" ]; then
        log_message "No scaling schedule configuration found"
        return 0
    fi

    local current_hour=$(date +%H)
    local current_day=$(date +%u)  # 1=Monday, 7=Sunday

    # Parse schedule and determine target instances
    local target_instances=$(jq -r --arg hour "$current_hour" --arg day "$current_day" \\
        '.schedule[] | select(.hour == ($hour | tonumber) and (.days[] | tostring) == $day) | .instances' \\
        "$schedule_config" | head -1)

    if [ -n "$target_instances" ] && [ "$target_instances" != "null" ]; then
        log_message "Scheduled scaling to $target_instances instances (hour=$current_hour, day=$current_day)"

        local current_instances=$(get_current_instances)

        if [ "$target_instances" -gt "$current_instances" ]; then
            scale_up "$target_instances"
        elif [ "$target_instances" -lt "$current_instances" ]; then
            scale_down "$target_instances"
        else
            log_message "Already at scheduled instance count: $target_instances"
        fi
    fi
}}

# Function to handle manual scaling
manual_scaling() {{
    local action="$1"
    local instances="${{2:-1}}"

    case "$action" in
        "up")
            local current_instances=$(get_current_instances)
            scale_up $((current_instances + instances))
            ;;
        "down")
            local current_instances=$(get_current_instances)
            scale_down $((current_instances - instances))
            ;;
        "set")
            local current_instances=$(get_current_instances)
            if [ "$instances" -gt "$current_instances" ]; then
                scale_up "$instances"
            elif [ "$instances" -lt "$current_instances" ]; then
                scale_down "$instances"
            else
                log_message "Already at target instance count: $instances"
            fi
            ;;
        *)
            echo "ERROR: Unknown manual scaling action: $action"
            return 1
            ;;
    esac
}}

# Function to show scaling status
show_scaling_status() {{
    local current_instances=$(get_current_instances)
    local metrics=$(get_resource_metrics)
    local cpu_usage=$(echo "$metrics" | cut -d',' -f1)
    local memory_usage=$(echo "$metrics" | cut -d',' -f2)
    local load_average=$(echo "$metrics" | cut -d',' -f3)

    echo "CoffeeBreak Scaling Status"
    echo "========================="
    echo "Current Instances: $current_instances"
    echo "Min Instances: $MIN_INSTANCES"
    echo "Max Instances: $MAX_INSTANCES"
    echo
    echo "Current Metrics:"
    echo "  CPU Usage: $cpu_usage%"
    echo "  Memory Usage: $memory_usage%"
    echo "  Load Average: $load_average"
    echo
    echo "Scaling Thresholds:"
    echo "  CPU Scale Up: $CPU_SCALE_UP_THRESHOLD%"
    echo "  CPU Scale Down: $CPU_SCALE_DOWN_THRESHOLD%"
    echo "  Memory Scale Up: $MEMORY_SCALE_UP_THRESHOLD%"
    echo "  Memory Scale Down: $MEMORY_SCALE_DOWN_THRESHOLD%"
    echo
    echo "Cooldown: $SCALE_COOLDOWN seconds"

    if is_scaling_on_cooldown; then
        echo "Status: On cooldown"
    else
        echo "Status: Ready for scaling"
    fi
}}

# Main scaling function
main() {{
    local action="${{1:-adaptive}}"
    local param1="$2"
    local param2="$3"

    log_message "Scaling action requested: $action"

    case "$action" in
        "adaptive"|"auto")
            adaptive_scaling
            ;;
        "scheduled")
            scheduled_scaling
            ;;
        "up"|"down"|"set")
            manual_scaling "$action" "$param1"
            ;;
        "status")
            show_scaling_status
            ;;
        *)
            echo "Usage: $0 {{adaptive|scheduled|up|down|set|status}} [instances]"
            exit 1
            ;;
    esac
}}

main "$@"
"""

            scaling_script_path = f"{scripts_dir}/scale.sh"
            with open(scaling_script_path, "w") as f:
                f.write(scaling_script)
            os.chmod(scaling_script_path, 0o755)

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Scaling scripts creation failed: {e}")

        return setup_result

    def _setup_scaling_policies(self, domain: str, config: Dict[str, Any], scripts_dir: str) -> Dict[str, Any]:
        """Setup scaling policies and configuration."""
        setup_result = {"success": True, "errors": []}

        try:
            # Create scaling policy configuration
            scaling_config = {
                "scaling_policy": config.get("scaling_policy", "adaptive"),
                "min_instances": config.get("min_instances", 1),
                "max_instances": config.get("max_instances", 5),
                "cpu_threshold": config.get("cpu_threshold", 70),
                "memory_threshold": config.get("memory_threshold", 80),
                "scale_cooldown": config.get("scale_cooldown", 300),
                "schedule": [
                    {
                        "hour": 8,
                        "days": [1, 2, 3, 4, 5],
                        "instances": 3,
                        "description": "Morning peak hours",
                    },
                    {
                        "hour": 12,
                        "days": [1, 2, 3, 4, 5],
                        "instances": 4,
                        "description": "Lunch peak hours",
                    },
                    {
                        "hour": 18,
                        "days": [1, 2, 3, 4, 5],
                        "instances": 3,
                        "description": "Evening peak hours",
                    },
                    {
                        "hour": 22,
                        "days": [1, 2, 3, 4, 5, 6, 7],
                        "instances": 1,
                        "description": "Night hours",
                    },
                ],
            }

            if self.deployment_type == "standalone":
                config_dir = "/opt/coffeebreak/config"
            else:
                config_dir = "./config"

            os.makedirs(config_dir, exist_ok=True)

            config_file = f"{config_dir}/scaling-schedule.json"
            with open(config_file, "w") as f:
                json.dump(scaling_config, f, indent=2)

            if self.verbose:
                print("Scaling policies configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Scaling policies setup failed: {e}")

        return setup_result

    def _setup_scaling_monitoring(self, domain: str, config: Dict[str, Any], scripts_dir: str) -> Dict[str, Any]:
        """Setup scaling monitoring and automation."""
        setup_result = {"success": True, "errors": []}

        try:
            # Setup cron job for adaptive scaling
            if config.get("scaling_policy") == "adaptive":
                cron_entry = f"*/5 * * * * {scripts_dir}/scale.sh adaptive"

                try:
                    current_crontab = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
                    crontab_content = current_crontab.stdout if current_crontab.returncode == 0 else ""
                except Exception:
                    crontab_content = ""

                if "scale.sh adaptive" not in crontab_content:
                    new_crontab = crontab_content.rstrip() + "\n" + cron_entry + "\n"
                    process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
                    process.communicate(input=new_crontab)

            # Setup cron job for scheduled scaling
            if config.get("enable_scheduled_scaling", True):
                cron_entry = f"0 * * * * {scripts_dir}/scale.sh scheduled"

                try:
                    current_crontab = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
                    crontab_content = current_crontab.stdout if current_crontab.returncode == 0 else ""
                except Exception:
                    crontab_content = ""

                if "scale.sh scheduled" not in crontab_content:
                    new_crontab = crontab_content.rstrip() + "\n" + cron_entry + "\n"
                    process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
                    process.communicate(input=new_crontab)

            if self.verbose:
                print("Scaling monitoring configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Scaling monitoring setup failed: {e}")

        return setup_result
