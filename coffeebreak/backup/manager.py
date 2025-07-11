"""Backup management system for production deployments."""

import os
import subprocess
from datetime import datetime
from typing import Any, Dict, Optional

from coffeebreak.utils.errors import CoffeeBreakError

from .recovery import RecoveryManager
from .scheduler import BackupScheduler
from .storage import BackupStorage


class BackupManager:
    """Manages backup operations for production deployments."""

    def __init__(self, deployment_type: str = "docker", verbose: bool = False):
        """
        Initialize backup manager.

        Args:
            deployment_type: Type of deployment (docker, standalone)
            verbose: Enable verbose output
        """
        self.deployment_type = deployment_type
        self.verbose = verbose

        # Initialize components
        self.scheduler = BackupScheduler(deployment_type=deployment_type, verbose=verbose)
        self.recovery = RecoveryManager(deployment_type=deployment_type, verbose=verbose)
        self.storage = BackupStorage(deployment_type=deployment_type, verbose=verbose)

    def setup_backup_system(self, domain: str, backup_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Set up comprehensive backup system.

        Args:
            domain: Production domain
            backup_config: Optional backup configuration

        Returns:
            Dict[str, Any]: Setup results
        """
        try:
            if self.verbose:
                print(f"Setting up backup system for {domain}")

            setup_result = {
                "success": True,
                "domain": domain,
                "deployment_type": self.deployment_type,
                "components_setup": [],
                "errors": [],
                "backup_location": None,
                "recovery_scripts": [],
            }

            # Default backup configuration
            config = {
                "domain": domain,
                "retention_days": 30,
                "backup_schedule": "0 2 * * *",  # Daily at 2 AM
                "full_backup_schedule": "0 3 * * 0",  # Weekly on Sunday at 3 AM
                "enable_encryption": True,
                "enable_compression": True,
                "backup_databases": True,
                "backup_files": True,
                "backup_configs": True,
                "remote_storage": False,
                "verify_backups": True,
            }

            if backup_config:
                config.update(backup_config)

            # 1. Setup backup storage
            storage_setup = self.storage.setup_backup_storage(config)
            if storage_setup["success"]:
                setup_result["components_setup"].append("backup_storage")
                setup_result["backup_location"] = storage_setup.get("backup_path")
            else:
                setup_result["errors"].extend(storage_setup["errors"])

            # 2. Create backup scripts
            scripts_setup = self._create_backup_scripts(domain, config)
            if scripts_setup["success"]:
                setup_result["components_setup"].append("backup_scripts")
                setup_result["recovery_scripts"] = scripts_setup.get("scripts", [])
            else:
                setup_result["errors"].extend(scripts_setup["errors"])

            # 3. Setup backup scheduling
            schedule_setup = self.scheduler.setup_backup_schedule(domain, config)
            if schedule_setup["success"]:
                setup_result["components_setup"].append("backup_scheduling")
            else:
                setup_result["errors"].extend(schedule_setup["errors"])

            # 4. Setup recovery procedures
            recovery_setup = self.recovery.setup_recovery_procedures(domain, config)
            if recovery_setup["success"]:
                setup_result["components_setup"].append("recovery_procedures")
            else:
                setup_result["errors"].extend(recovery_setup["errors"])

            # 5. Create backup verification system
            verification_setup = self._setup_backup_verification(domain, config)
            if verification_setup["success"]:
                setup_result["components_setup"].append("backup_verification")
            else:
                setup_result["errors"].extend(verification_setup["errors"])

            # 6. Setup monitoring and alerting
            monitoring_setup = self._setup_backup_monitoring(domain, config)
            if monitoring_setup["success"]:
                setup_result["components_setup"].append("backup_monitoring")
            else:
                setup_result["errors"].extend(monitoring_setup["errors"])

            setup_result["success"] = len(setup_result["errors"]) == 0

            if self.verbose:
                if setup_result["success"]:
                    print(f"Backup system setup completed successfully for {domain}")
                    print(f"Components: {', '.join(setup_result['components_setup'])}")
                else:
                    print(f"Backup system setup completed with {len(setup_result['errors'])} errors")

            return setup_result

        except Exception as e:
            raise CoffeeBreakError(f"Failed to setup backup system: {e}") from e

    def _create_backup_scripts(self, domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create backup scripts."""
        setup_result = {"success": True, "errors": [], "scripts": []}

        try:
            if self.deployment_type == "standalone":
                scripts_dir = "/opt/coffeebreak/bin"
                backup_dir = "/opt/coffeebreak/backups"
            else:
                scripts_dir = "./scripts"
                backup_dir = "./backups"

            os.makedirs(scripts_dir, exist_ok=True)
            os.makedirs(backup_dir, exist_ok=True)

            # Main backup script
            backup_script = f"""#!/bin/bash
# CoffeeBreak Backup Script
# Domain: {domain}
# Generated: {datetime.now().isoformat()}

set -euo pipefail

DOMAIN="{domain}"
BACKUP_DIR="{backup_dir}"
LOG_FILE="/var/log/coffeebreak/backup.log"
RETENTION_DAYS={config.get("retention_days", 30)}
ENABLE_ENCRYPTION={str(config.get("enable_encryption", True)).lower()}
ENABLE_COMPRESSION={str(config.get("enable_compression", True)).lower()}

# Create log directory
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log with timestamp
log_message() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}}

# Function to handle errors
handle_error() {{
    local error_msg="$1"
    log_message "ERROR: $error_msg"
    
    # Send alert if notification script exists
    if [ -f "/opt/coffeebreak/bin/notify.sh" ]; then
        /opt/coffeebreak/bin/notify.sh "Backup Failed" "$error_msg"
    fi
    
    exit 1
}}

# Function to create timestamped backup directory
create_backup_dir() {{
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_type="$1"
    local backup_path="$BACKUP_DIR/$backup_type/$timestamp"
    
    mkdir -p "$backup_path"
    echo "$backup_path"
}}

# Function to compress and encrypt backup
finalize_backup() {{
    local backup_path="$1"
    local backup_name="$(basename "$backup_path")"
    local parent_dir="$(dirname "$backup_path")"
    
    cd "$parent_dir"
    
    if [ "$ENABLE_COMPRESSION" = "true" ]; then
        log_message "Compressing backup: $backup_name"
        tar -czf "${{backup_name}}.tar.gz" "$backup_name"
        rm -rf "$backup_name"
        backup_name="${{backup_name}}.tar.gz"
    fi
    
    if [ "$ENABLE_ENCRYPTION" = "true" ]; then
        log_message "Encrypting backup: $backup_name"
        if command -v gpg &> /dev/null; then
            gpg --symmetric --cipher-algo AES256 --compress-algo 1 --output "${{backup_name}}.gpg" "$backup_name"
            rm -f "$backup_name"
            backup_name="${{backup_name}}.gpg"
        else
            log_message "WARNING: GPG not available, skipping encryption"
        fi
    fi
    
    log_message "Backup finalized: $parent_dir/$backup_name"
}}

# Function to backup PostgreSQL databases
backup_postgresql() {{
    log_message "Starting PostgreSQL backup"
    
    local backup_path=$(create_backup_dir "postgresql")
    
    # Get list of databases
    local databases
    if systemctl is-active --quiet postgresql; then
        databases=$(sudo -u postgres psql -t -c "SELECT datname FROM pg_database WHERE NOT datistemplate AND datname != 'postgres';" 2>/dev/null || echo "")
    else
        log_message "WARNING: PostgreSQL not running, skipping database backup"
        return 0
    fi
    
    if [ -n "$databases" ]; then
        for db in $databases; do
            db=$(echo "$db" | xargs)  # Trim whitespace
            if [ -n "$db" ]; then
                log_message "Backing up PostgreSQL database: $db"
                sudo -u postgres pg_dump "$db" > "$backup_path/${{db}}.sql" || handle_error "Failed to backup PostgreSQL database: $db"
            fi
        done
        
        # Backup globals (users, roles, etc.)
        log_message "Backing up PostgreSQL globals"
        sudo -u postgres pg_dumpall --globals-only > "$backup_path/globals.sql" || handle_error "Failed to backup PostgreSQL globals"
        
        finalize_backup "$backup_path"
    else
        log_message "No PostgreSQL databases found to backup"
        rmdir "$backup_path" 2>/dev/null || true
    fi
}}

# Function to backup MongoDB databases
backup_mongodb() {{
    log_message "Starting MongoDB backup"
    
    local backup_path=$(create_backup_dir "mongodb")
    
    if systemctl is-active --quiet mongod || pgrep mongod > /dev/null; then
        log_message "Backing up MongoDB databases"
        mongodump --out "$backup_path" || handle_error "Failed to backup MongoDB"
        finalize_backup "$backup_path"
    else
        log_message "WARNING: MongoDB not running, skipping database backup"
        rmdir "$backup_path" 2>/dev/null || true
    fi
}}

# Function to backup application files
backup_files() {{
    log_message "Starting file backup"
    
    local backup_path=$(create_backup_dir "files")
    
    # List of directories to backup
    local dirs_to_backup=(
        "/opt/coffeebreak/data"
        "/opt/coffeebreak/uploads"
        "/opt/coffeebreak/plugins"
        "/var/log/coffeebreak"
    )
    
    for dir in "${{dirs_to_backup[@]}}"; do
        if [ -d "$dir" ]; then
            log_message "Backing up directory: $dir"
            cp -r "$dir" "$backup_path/" || handle_error "Failed to backup directory: $dir"
        fi
    done
    
    # Backup Docker volumes if Docker deployment
    if [ -f "/usr/bin/docker" ] && docker ps -q > /dev/null 2>&1; then
        log_message "Backing up Docker volumes"
        mkdir -p "$backup_path/docker-volumes"
        
        # Get CoffeeBreak-related volumes
        local volumes=$(docker volume ls --filter name=coffeebreak --format "{{{{.Name}}}}" 2>/dev/null || echo "")
        
        for volume in $volumes; do
            if [ -n "$volume" ]; then
                log_message "Backing up Docker volume: $volume"
                docker run --rm -v "$volume:/source" -v "$backup_path/docker-volumes:/backup" ubuntu tar czf "/backup/${{volume}}.tar.gz" -C /source . || log_message "WARNING: Failed to backup volume $volume"
            fi
        done
    fi
    
    finalize_backup "$backup_path"
}}

# Function to backup configuration files
backup_configs() {{
    log_message "Starting configuration backup"
    
    local backup_path=$(create_backup_dir "configs")
    
    # List of config files/directories to backup
    local configs_to_backup=(
        "/opt/coffeebreak/config"
        "/opt/coffeebreak/.env"
        "/etc/nginx/sites-available/coffeebreak"
        "/etc/systemd/system/coffeebreak-*"
        "/etc/cron.d/coffeebreak"
        "/etc/logrotate.d/coffeebreak"
    )
    
    for config in "${{configs_to_backup[@]}}"; do
        if [ -e "$config" ]; then
            log_message "Backing up config: $config"
            
            # Create directory structure in backup
            local relative_path="${{config#/}}"
            local backup_config_path="$backup_path/$relative_path"
            mkdir -p "$(dirname "$backup_config_path")"
            
            cp -r "$config" "$backup_config_path" 2>/dev/null || log_message "WARNING: Failed to backup config: $config"
        fi
    done
    
    # Backup Docker Compose files if they exist
    if [ -f "docker-compose.yml" ]; then
        log_message "Backing up Docker Compose configuration"
        cp docker-compose.yml "$backup_path/" || log_message "WARNING: Failed to backup docker-compose.yml"
    fi
    
    finalize_backup "$backup_path"
}}

# Function to cleanup old backups
cleanup_old_backups() {{
    log_message "Cleaning up backups older than $RETENTION_DAYS days"
    
    find "$BACKUP_DIR" -type f -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
    find "$BACKUP_DIR" -type d -empty -delete 2>/dev/null || true
    
    log_message "Backup cleanup completed"
}}

# Function to verify backup integrity
verify_backups() {{
    log_message "Verifying recent backups"
    
    local today=$(date +%Y%m%d)
    local recent_backups=$(find "$BACKUP_DIR" -name "*$today*" -type f 2>/dev/null || echo "")
    
    for backup_file in $recent_backups; do
        if [[ "$backup_file" == *.tar.gz ]]; then
            if tar -tzf "$backup_file" > /dev/null 2>&1; then
                log_message "✓ Backup verified: $backup_file"
            else
                log_message "✗ Backup corrupted: $backup_file"
            fi
        elif [[ "$backup_file" == *.gpg ]]; then
            if gpg --list-packets "$backup_file" > /dev/null 2>&1; then
                log_message "✓ Encrypted backup verified: $backup_file"
            else
                log_message "✗ Encrypted backup corrupted: $backup_file"
            fi
        fi
    done
}}

# Main backup function
main() {{
    local backup_type="${{1:-incremental}}"
    
    log_message "Starting CoffeeBreak backup (type: $backup_type)"
    
    # Create backup directory structure
    mkdir -p "$BACKUP_DIR"/{{postgresql,mongodb,files,configs}}
    
    # Perform backups based on configuration
    if [ "{config.get("backup_databases", True)}" = "True" ]; then
        backup_postgresql
        backup_mongodb
    fi
    
    if [ "{config.get("backup_files", True)}" = "True" ]; then
        backup_files
    fi
    
    if [ "{config.get("backup_configs", True)}" = "True" ]; then
        backup_configs
    fi
    
    # Verify backups if enabled
    if [ "{config.get("verify_backups", True)}" = "True" ]; then
        verify_backups
    fi
    
    # Cleanup old backups
    cleanup_old_backups
    
    # Calculate backup size
    local backup_size=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1 || echo "unknown")
    
    log_message "Backup completed successfully (Total size: $backup_size)"
    
    # Send success notification
    if [ -f "/opt/coffeebreak/bin/notify.sh" ]; then
        /opt/coffeebreak/bin/notify.sh "Backup Completed" "CoffeeBreak backup completed successfully. Type: $backup_type, Size: $backup_size"
    fi
}}

# Handle command line arguments
case "${{1:-incremental}}" in
    "incremental"|"full")
        main "$1"
        ;;
    "verify")
        verify_backups
        ;;
    "cleanup")
        cleanup_old_backups
        ;;
    *)
        echo "Usage: $0 {{incremental|full|verify|cleanup}}"
        exit 1
        ;;
esac
"""

            backup_script_path = f"{scripts_dir}/backup.sh"
            with open(backup_script_path, "w") as f:
                f.write(backup_script)
            os.chmod(backup_script_path, 0o755)

            setup_result["scripts"].append(backup_script_path)

            if self.verbose:
                print("Backup scripts created")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Backup scripts creation failed: {e}")

        return setup_result

    def _setup_backup_verification(self, domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup backup verification system."""
        setup_result = {"success": True, "errors": []}

        try:
            if self.deployment_type == "standalone":
                scripts_dir = "/opt/coffeebreak/bin"
            else:
                scripts_dir = "./scripts"

            # Backup verification script
            verify_script = f"""#!/bin/bash
# CoffeeBreak Backup Verification Script

BACKUP_DIR="{config.get("backup_dir", "/opt/coffeebreak/backups")}"
LOG_FILE="/var/log/coffeebreak/backup-verify.log"

# Function to log with timestamp
log_message() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}}

# Function to verify PostgreSQL backup
verify_postgresql_backup() {{
    local backup_file="$1"
    
    log_message "Verifying PostgreSQL backup: $backup_file"
    
    if [[ "$backup_file" == *.sql ]]; then
        # Check SQL syntax
        if pg_verifybackup --parse-only "$backup_file" 2>/dev/null; then
            log_message "✓ PostgreSQL backup syntax valid: $backup_file"
            return 0
        else
            # Fallback: Basic SQL syntax check
            if grep -q "CREATE\\|INSERT\\|COPY" "$backup_file"; then
                log_message "✓ PostgreSQL backup appears valid: $backup_file"
                return 0
            else
                log_message "✗ PostgreSQL backup appears invalid: $backup_file"
                return 1
            fi
        fi
    fi
    
    return 1
}}

# Function to verify MongoDB backup
verify_mongodb_backup() {{
    local backup_dir="$1"
    
    log_message "Verifying MongoDB backup: $backup_dir"
    
    if [ -d "$backup_dir" ]; then
        # Check for BSON files
        local bson_files=$(find "$backup_dir" -name "*.bson" | wc -l)
        if [ "$bson_files" -gt 0 ]; then
            log_message "✓ MongoDB backup contains $bson_files BSON files: $backup_dir"
            return 0
        else
            log_message "✗ MongoDB backup contains no BSON files: $backup_dir"
            return 1
        fi
    fi
    
    return 1
}}

# Function to verify file backup integrity
verify_file_backup() {{
    local backup_file="$1"
    
    log_message "Verifying file backup: $backup_file"
    
    if [[ "$backup_file" == *.tar.gz ]]; then
        if tar -tzf "$backup_file" > /dev/null 2>&1; then
            log_message "✓ File backup archive valid: $backup_file"
            return 0
        else
            log_message "✗ File backup archive corrupted: $backup_file"
            return 1
        fi
    elif [[ "$backup_file" == *.gpg ]]; then
        if gpg --list-packets "$backup_file" > /dev/null 2>&1; then
            log_message "✓ Encrypted backup valid: $backup_file"
            return 0
        else
            log_message "✗ Encrypted backup corrupted: $backup_file"
            return 1
        fi
    fi
    
    return 1
}}

# Main verification function
main() {{
    local backup_date="${{1:-$(date +%Y%m%d)}}"
    
    log_message "Starting backup verification for date: $backup_date"
    
    local total_verified=0
    local total_failed=0
    
    # Verify PostgreSQL backups
    for backup_file in "$BACKUP_DIR"/postgresql/*"$backup_date"*; do
        if [ -f "$backup_file" ]; then
            if verify_postgresql_backup "$backup_file"; then
                ((total_verified++))
            else
                ((total_failed++))
            fi
        fi
    done
    
    # Verify MongoDB backups
    for backup_dir in "$BACKUP_DIR"/mongodb/*"$backup_date"*; do
        if [ -d "$backup_dir" ]; then
            if verify_mongodb_backup "$backup_dir"; then
                ((total_verified++))
            else
                ((total_failed++))
            fi
        fi
    done
    
    # Verify file backups
    for backup_file in "$BACKUP_DIR"/files/*"$backup_date"* "$BACKUP_DIR"/configs/*"$backup_date"*; do
        if [ -f "$backup_file" ]; then
            if verify_file_backup "$backup_file"; then
                ((total_verified++))
            else
                ((total_failed++))
            fi
        fi
    done
    
    log_message "Backup verification completed: $total_verified verified, $total_failed failed"
    
    # Send notification if there are failures
    if [ "$total_failed" -gt 0 ] && [ -f "/opt/coffeebreak/bin/notify.sh" ]; then
        /opt/coffeebreak/bin/notify.sh "Backup Verification Failed" "$total_failed backup(s) failed verification for date $backup_date"
    fi
    
    exit $total_failed
}}

main "$@"
"""

            verify_script_path = f"{scripts_dir}/verify-backup.sh"
            with open(verify_script_path, "w") as f:
                f.write(verify_script)
            os.chmod(verify_script_path, 0o755)

            if self.verbose:
                print("Backup verification system configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Backup verification setup failed: {e}")

        return setup_result

    def _setup_backup_monitoring(self, domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup backup monitoring and alerting."""
        setup_result = {"success": True, "errors": []}

        try:
            if self.deployment_type == "standalone":
                scripts_dir = "/opt/coffeebreak/bin"
            else:
                scripts_dir = "./scripts"

            # Backup monitoring script
            monitor_script = f"""#!/bin/bash
# CoffeeBreak Backup Monitoring Script

BACKUP_DIR="{config.get("backup_dir", "/opt/coffeebreak/backups")}"
LOG_FILE="/var/log/coffeebreak/backup-monitor.log"
ALERT_EMAIL="{config.get("alert_email", "admin@localhost")}"
MAX_BACKUP_AGE_HOURS=25  # Alert if no backup in 25 hours

# Function to log with timestamp
log_message() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}}

# Function to send alert
send_alert() {{
    local subject="$1"
    local message="$2"
    
    log_message "ALERT: $subject"
    
    # Send email if available
    if command -v mail &> /dev/null && [ -n "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "CoffeeBreak Backup Alert: $subject" "$ALERT_EMAIL"
    fi
    
    # Send via notification script if available
    if [ -f "/opt/coffeebreak/bin/notify.sh" ]; then
        /opt/coffeebreak/bin/notify.sh "$subject" "$message"
    fi
    
    # Log to syslog
    logger -t coffeebreak-backup "ALERT: $subject - $message"
}}

# Function to check backup freshness
check_backup_freshness() {{
    log_message "Checking backup freshness"
    
    local current_time=$(date +%s)
    local max_age_seconds=$((MAX_BACKUP_AGE_HOURS * 3600))
    
    # Check for recent backups in each category
    local categories=("postgresql" "mongodb" "files" "configs")
    local stale_categories=()
    
    for category in "${{categories[@]}}"; do
        local category_dir="$BACKUP_DIR/$category"
        
        if [ -d "$category_dir" ]; then
            local latest_backup=$(find "$category_dir" -type f -printf '%T@ %p
' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
            
            if [ -n "$latest_backup" ]; then
                local backup_time=$(stat -c %Y "$latest_backup" 2>/dev/null || echo 0)
                local age_seconds=$((current_time - backup_time))
                
                if [ "$age_seconds" -gt "$max_age_seconds" ]; then
                    stale_categories+=("$category")
                    log_message "WARNING: Stale backup in category $category ($(( age_seconds / 3600 )) hours old)"
                else
                    log_message "✓ Fresh backup found in category $category"
                fi
            else
                stale_categories+=("$category")
                log_message "WARNING: No backups found in category $category"
            fi
        else
            log_message "WARNING: Backup category directory missing: $category_dir"
        fi
    done
    
    if [ ${{#stale_categories[@]}} -gt 0 ]; then
        send_alert "Stale Backups Detected" "The following backup categories are stale: ${{stale_categories[*]}}"
    fi
}}

# Function to check backup sizes
check_backup_sizes() {{
    log_message "Checking backup sizes"
    
    local today=$(date +%Y%m%d)
    local yesterday=$(date -d "yesterday" +%Y%m%d)
    
    # Get today's backup size
    local today_size=$(find "$BACKUP_DIR" -name "*$today*" -type f -exec du -cb {{}} + 2>/dev/null | tail -1 | cut -f1 || echo 0)
    
    # Get yesterday's backup size
    local yesterday_size=$(find "$BACKUP_DIR" -name "*$yesterday*" -type f -exec du -cb {{}} + 2>/dev/null | tail -1 | cut -f1 || echo 0)
    
    if [ "$today_size" -eq 0 ]; then
        send_alert "No Backups Today" "No backups found for today ($today)"
    elif [ "$yesterday_size" -gt 0 ]; then
        # Check for significant size difference (more than 50% change)
        local size_ratio=$((today_size * 100 / yesterday_size))
        
        if [ "$size_ratio" -lt 50 ]; then
            send_alert "Backup Size Anomaly" "Today's backup is significantly smaller than yesterday's ($today_size vs $yesterday_size bytes)"
        elif [ "$size_ratio" -gt 200 ]; then
            send_alert "Backup Size Anomaly" "Today's backup is significantly larger than yesterday's ($today_size vs $yesterday_size bytes)"
        fi
    fi
    
    log_message "Today's backup size: $today_size bytes"
}}

# Function to check disk space
check_disk_space() {{
    log_message "Checking backup disk space"
    
    local backup_fs=$(df "$BACKUP_DIR" | tail -1)
    local usage_percent=$(echo "$backup_fs" | awk '{{print $5}}' | sed 's/%//')
    local available_gb=$(echo "$backup_fs" | awk '{{print int($4/1024/1024)}}')
    
    if [ "$usage_percent" -gt 90 ]; then
        send_alert "Backup Disk Space Critical" "Backup filesystem is $usage_percent% full ($available_gb GB available)"
    elif [ "$usage_percent" -gt 80 ]; then
        log_message "WARNING: Backup filesystem is $usage_percent% full ($available_gb GB available)"
    else
        log_message "✓ Backup disk space OK: $usage_percent% used ($available_gb GB available)"
    fi
}}

# Function to verify backup processes
check_backup_processes() {{
    log_message "Checking backup processes"
    
    # Check if backup is currently running
    local backup_pids=$(pgrep -f "backup.sh" || echo "")
    
    if [ -n "$backup_pids" ]; then
        log_message "Backup process running (PIDs: $backup_pids)"
        
        # Check if backup has been running too long (more than 4 hours)
        for pid in $backup_pids; do
            local start_time=$(ps -o lstart= -p "$pid" 2>/dev/null | xargs -I{{}} date -d{{}} +%s || echo 0)
            local current_time=$(date +%s)
            local runtime_hours=$(( (current_time - start_time) / 3600 ))
            
            if [ "$runtime_hours" -gt 4 ]; then
                send_alert "Backup Process Stuck" "Backup process (PID: $pid) has been running for $runtime_hours hours"
            fi
        done
    fi
}}

# Main monitoring function
main() {{
    log_message "Starting backup monitoring check"
    
    check_backup_freshness
    check_backup_sizes
    check_disk_space
    check_backup_processes
    
    log_message "Backup monitoring check completed"
}}

main "$@"
"""

            monitor_script_path = f"{scripts_dir}/monitor-backup.sh"
            with open(monitor_script_path, "w") as f:
                f.write(monitor_script)
            os.chmod(monitor_script_path, 0o755)

            # Setup cron job for backup monitoring
            cron_entry = f"0 */6 * * * {monitor_script_path}"

            try:
                current_crontab = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
                crontab_content = current_crontab.stdout if current_crontab.returncode == 0 else ""
            except:
                crontab_content = ""

            if "monitor-backup.sh" not in crontab_content:
                new_crontab = crontab_content.rstrip() + "\n" + cron_entry + "\n"
                process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
                process.communicate(input=new_crontab)

            if self.verbose:
                print("Backup monitoring configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Backup monitoring setup failed: {e}")

        return setup_result
