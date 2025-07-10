"""Backup scheduling system for automated backups."""

import os
import subprocess
from typing import Dict, Any
from datetime import datetime

from ..utils.errors import ConfigurationError


class BackupScheduler:
    """Manages backup scheduling and automation."""

    def __init__(self, deployment_type: str = "docker", verbose: bool = False):
        """
        Initialize backup scheduler.

        Args:
            deployment_type: Type of deployment (docker, standalone)
            verbose: Enable verbose output
        """
        self.deployment_type = deployment_type
        self.verbose = verbose

    def setup_backup_schedule(
        self, domain: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Setup automated backup scheduling.

        Args:
            domain: Production domain
            config: Backup configuration

        Returns:
            Dict[str, Any]: Setup results
        """
        setup_result = {"success": True, "errors": [], "scheduled_jobs": []}

        try:
            if self.deployment_type == "standalone":
                scripts_dir = "/opt/coffeebreak/bin"
            else:
                scripts_dir = "./scripts"

            # Create scheduler script
            scheduler_script = self._create_scheduler_script(
                domain, config, scripts_dir
            )

            # Setup cron jobs
            cron_setup = self._setup_cron_jobs(domain, config, scripts_dir)
            if cron_setup["success"]:
                setup_result["scheduled_jobs"] = cron_setup["jobs"]
            else:
                setup_result["errors"].extend(cron_setup["errors"])

            # Setup systemd timers (for standalone deployments)
            if self.deployment_type == "standalone":
                timer_setup = self._setup_systemd_timers(domain, config, scripts_dir)
                if not timer_setup["success"]:
                    setup_result["errors"].extend(timer_setup["errors"])

            setup_result["success"] = len(setup_result["errors"]) == 0

            if self.verbose:
                print("Backup scheduling configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Backup scheduling setup failed: {e}")

        return setup_result

    def _create_scheduler_script(
        self, domain: str, config: Dict[str, Any], scripts_dir: str
    ) -> str:
        """Create backup scheduler script."""
        scheduler_script = f"""#!/bin/bash
# CoffeeBreak Backup Scheduler Script
# Domain: {domain}
# Generated: {datetime.now().isoformat()}

set -euo pipefail

BACKUP_SCRIPT="{scripts_dir}/backup.sh"
LOG_FILE="/var/log/coffeebreak/backup-scheduler.log"

# Function to log with timestamp
log_message() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}}

# Function to run backup with proper logging
run_backup() {{
    local backup_type="$1"
    
    log_message "Starting scheduled backup (type: $backup_type)"
    
    if [ -f "$BACKUP_SCRIPT" ]; then
        if "$BACKUP_SCRIPT" "$backup_type" >> "$LOG_FILE" 2>&1; then
            log_message "Scheduled backup completed successfully (type: $backup_type)"
            return 0
        else
            log_message "Scheduled backup failed (type: $backup_type)"
            
            # Send failure notification
            if [ -f "/opt/coffeebreak/bin/notify.sh" ]; then
                /opt/coffeebreak/bin/notify.sh "Scheduled Backup Failed" "Backup type: $backup_type failed to complete"
            fi
            return 1
        fi
    else
        log_message "ERROR: Backup script not found: $BACKUP_SCRIPT"
        return 1
    fi
}}

# Function to check system load before backup
check_system_load() {{
    local max_load="{config.get("max_load_threshold", 2.0)}"
    local current_load=$(uptime | awk -F'load average:' '{{ print $2 }}' | awk '{{ print $1 }}' | sed 's/,//')
    
    if (( $(echo "$current_load > $max_load" | bc -l) )); then
        log_message "WARNING: System load too high ($current_load), delaying backup"
        
        # Wait up to 30 minutes for load to decrease
        local wait_count=0
        while (( $(echo "$current_load > $max_load" | bc -l) )) && [ "$wait_count" -lt 30 ]; do
            sleep 60
            current_load=$(uptime | awk -F'load average:' '{{ print $2 }}' | awk '{{ print $1 }}' | sed 's/,//')
            ((wait_count++))
        done
        
        if (( $(echo "$current_load > $max_load" | bc -l) )); then
            log_message "ERROR: System load still too high after 30 minutes, skipping backup"
            return 1
        fi
    fi
    
    return 0
}}

# Function to check disk space before backup
check_disk_space() {{
    local backup_dir="{config.get("backup_dir", "/opt/coffeebreak/backups")}"
    local min_space_gb="{config.get("min_free_space_gb", 5)}"
    
    # Get available space in GB
    local available_gb=$(df "$backup_dir" | tail -1 | awk '{{print int($4/1024/1024)}}')
    
    if [ "$available_gb" -lt "$min_space_gb" ]; then
        log_message "ERROR: Insufficient disk space ($available_gb GB available, need $min_space_gb GB)"
        
        # Send low disk space alert
        if [ -f "/opt/coffeebreak/bin/notify.sh" ]; then
            /opt/coffeebreak/bin/notify.sh "Low Disk Space" "Only $available_gb GB available for backups (need $min_space_gb GB)"
        fi
        
        return 1
    fi
    
    return 0
}}

# Main scheduler function
main() {{
    local backup_type="${{1:-incremental}}"
    
    log_message "Backup scheduler started (type: $backup_type)"
    
    # Pre-backup checks
    if ! check_system_load; then
        exit 1
    fi
    
    if ! check_disk_space; then
        exit 1
    fi
    
    # Lock file to prevent concurrent backups
    local lock_file="/tmp/coffeebreak-backup.lock"
    
    if [ -f "$lock_file" ]; then
        local lock_pid=$(cat "$lock_file" 2>/dev/null || echo "")
        
        if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
            log_message "Backup already running (PID: $lock_pid), exiting"
            exit 0
        else
            log_message "Stale lock file found, removing"
            rm -f "$lock_file"
        fi
    fi
    
    # Create lock file
    echo $$ > "$lock_file"
    
    # Ensure lock file is removed on exit
    trap 'rm -f "$lock_file"' EXIT
    
    # Run the backup
    if run_backup "$backup_type"; then
        log_message "Backup scheduler completed successfully"
        exit 0
    else
        log_message "Backup scheduler completed with errors"
        exit 1
    fi
}}

# Handle command line arguments
case "${{1:-incremental}}" in
    "incremental"|"full")
        main "$1"
        ;;
    *)
        echo "Usage: $0 {{incremental|full}}"
        exit 1
        ;;
esac
"""

        scheduler_script_path = f"{scripts_dir}/backup-scheduler.sh"
        with open(scheduler_script_path, "w") as f:
            f.write(scheduler_script)
        os.chmod(scheduler_script_path, 0o755)

        return scheduler_script_path

    def _setup_cron_jobs(
        self, domain: str, config: Dict[str, Any], scripts_dir: str
    ) -> Dict[str, Any]:
        """Setup cron jobs for backup scheduling."""
        setup_result = {"success": True, "errors": [], "jobs": []}

        try:
            # Default schedules
            incremental_schedule = config.get(
                "backup_schedule", "0 2 * * *"
            )  # Daily at 2 AM
            full_schedule = config.get(
                "full_backup_schedule", "0 3 * * 0"
            )  # Weekly on Sunday at 3 AM

            # Cron entries
            cron_entries = [
                f"# CoffeeBreak incremental backup",
                f"{incremental_schedule} {scripts_dir}/backup-scheduler.sh incremental",
                f"# CoffeeBreak full backup",
                f"{full_schedule} {scripts_dir}/backup-scheduler.sh full",
                f"# CoffeeBreak backup verification",
                f"0 4 * * * {scripts_dir}/verify-backup.sh",
                f"# CoffeeBreak backup monitoring",
                f"0 */6 * * * {scripts_dir}/monitor-backup.sh",
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

            # Add new entries if they don't exist
            new_entries = []
            for entry in cron_entries:
                if (
                    "backup-scheduler.sh" in entry
                    or "verify-backup.sh" in entry
                    or "monitor-backup.sh" in entry
                ):
                    if entry not in crontab_content:
                        new_entries.append(entry)
                        setup_result["jobs"].append(entry)
                else:
                    new_entries.append(entry)  # Comments

            if new_entries:
                # Create new crontab
                new_crontab = crontab_content.rstrip()
                if new_crontab:
                    new_crontab += "\\n"
                new_crontab += "\\n".join(new_entries) + "\\n"

                # Install new crontab
                process = subprocess.Popen(
                    ["crontab", "-"], stdin=subprocess.PIPE, text=True
                )
                process.communicate(input=new_crontab)

                if process.returncode != 0:
                    setup_result["success"] = False
                    setup_result["errors"].append("Failed to install crontab")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Cron setup failed: {e}")

        return setup_result

    def _setup_systemd_timers(
        self, domain: str, config: Dict[str, Any], scripts_dir: str
    ) -> Dict[str, Any]:
        """Setup systemd timers for backup scheduling."""
        setup_result = {"success": True, "errors": []}

        try:
            # Create systemd service files
            service_content = f"""[Unit]
Description=CoffeeBreak Backup Service
After=network.target

[Service]
Type=oneshot
ExecStart={scripts_dir}/backup-scheduler.sh %i
User=root
StandardOutput=journal
StandardError=journal
"""

            with open("/etc/systemd/system/coffeebreak-backup@.service", "w") as f:
                f.write(service_content)

            # Create timer for incremental backups
            incremental_timer = f"""[Unit]
Description=CoffeeBreak Incremental Backup Timer
Requires=coffeebreak-backup@incremental.service

[Timer]
OnCalendar={config.get("backup_schedule", "daily")}
Persistent=true

[Install]
WantedBy=timers.target
"""

            with open(
                "/etc/systemd/system/coffeebreak-backup-incremental.timer", "w"
            ) as f:
                f.write(incremental_timer)

            # Create timer for full backups
            full_timer = f"""[Unit]
Description=CoffeeBreak Full Backup Timer
Requires=coffeebreak-backup@full.service

[Timer]
OnCalendar={config.get("full_backup_schedule", "weekly")}
Persistent=true

[Install]
WantedBy=timers.target
"""

            with open("/etc/systemd/system/coffeebreak-backup-full.timer", "w") as f:
                f.write(full_timer)

            # Reload systemd and enable timers
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            subprocess.run(
                ["systemctl", "enable", "coffeebreak-backup-incremental.timer"],
                check=True,
            )
            subprocess.run(
                ["systemctl", "enable", "coffeebreak-backup-full.timer"], check=True
            )
            subprocess.run(
                ["systemctl", "start", "coffeebreak-backup-incremental.timer"],
                check=True,
            )
            subprocess.run(
                ["systemctl", "start", "coffeebreak-backup-full.timer"], check=True
            )

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Systemd timer setup failed: {e}")

        return setup_result
