"""Backup storage management system."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict


class BackupStorage:
    """Manages backup storage configuration and setup."""

    def __init__(self, deployment_type: str = "docker", verbose: bool = False):
        """
        Initialize backup storage manager.

        Args:
            deployment_type: Type of deployment (docker, standalone)
            verbose: Enable verbose output
        """
        self.deployment_type = deployment_type
        self.verbose = verbose

    def setup_backup_storage(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Setup backup storage system.

        Args:
            config: Backup storage configuration

        Returns:
            Dict[str, Any]: Setup results
        """
        setup_result = {
            "success": True,
            "errors": [],
            "backup_path": None,
            "storage_type": "local",
            "storage_info": {},
        }

        try:
            # Determine backup directory
            if self.deployment_type == "standalone":
                backup_dir = config.get("backup_dir", "/opt/coffeebreak/backups")
            else:
                backup_dir = config.get("backup_dir", "./backups")

            # Setup local storage
            local_setup = self._setup_local_storage(backup_dir, config)
            if local_setup["success"]:
                setup_result["backup_path"] = local_setup["backup_path"]
                setup_result["storage_info"].update(local_setup["info"])
            else:
                setup_result["errors"].extend(local_setup["errors"])

            # Setup remote storage if configured
            if config.get("remote_storage", False):
                remote_setup = self._setup_remote_storage(backup_dir, config)
                if remote_setup["success"]:
                    setup_result["storage_type"] = "hybrid"
                    setup_result["storage_info"].update(remote_setup["info"])
                else:
                    setup_result["errors"].extend(remote_setup["errors"])

            # Setup storage monitoring
            monitoring_setup = self._setup_storage_monitoring(backup_dir, config)
            if not monitoring_setup["success"]:
                setup_result["errors"].extend(monitoring_setup["errors"])

            setup_result["success"] = len(setup_result["errors"]) == 0

            if self.verbose:
                print("Backup storage configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Backup storage setup failed: {e}")

        return setup_result

    def _setup_local_storage(self, backup_dir: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup local backup storage."""
        setup_result = {
            "success": True,
            "errors": [],
            "backup_path": backup_dir,
            "info": {},
        }

        try:
            # Create backup directory structure
            backup_path = Path(backup_dir)
            backup_path.mkdir(parents=True, exist_ok=True)

            # Create subdirectories for different backup types
            subdirs = ["postgresql", "mongodb", "files", "configs", "logs"]
            for subdir in subdirs:
                (backup_path / subdir).mkdir(exist_ok=True)

            # Set appropriate permissions
            if self.deployment_type == "standalone":
                # Create coffeebreak user if it doesn't exist
                try:
                    subprocess.run(["id", "coffeebreak"], capture_output=True, check=True)
                except subprocess.CalledProcessError:
                    # User doesn't exist, create it
                    subprocess.run(
                        [
                            "useradd",
                            "--system",
                            "--no-create-home",
                            "--shell",
                            "/bin/false",
                            "coffeebreak",
                        ],
                        capture_output=True,
                    )

                # Set ownership and permissions
                shutil.chown(backup_dir, user="coffeebreak", group="coffeebreak")
                os.chmod(backup_dir, 0o750)

                # Set permissions for subdirectories
                for subdir in subdirs:
                    subdir_path = backup_path / subdir
                    shutil.chown(str(subdir_path), user="coffeebreak", group="coffeebreak")
                    os.chmod(str(subdir_path), 0o750)

            # Get storage information
            storage_info = self._get_storage_info(backup_dir)
            setup_result["info"] = storage_info

            # Create backup configuration file
            backup_config = {
                "backup_dir": backup_dir,
                "created": str(Path().cwd()),
                "deployment_type": self.deployment_type,
                "retention_days": config.get("retention_days", 30),
                "encryption_enabled": config.get("enable_encryption", True),
                "compression_enabled": config.get("enable_compression", True),
            }

            config_file = backup_path / "backup-config.json"
            with open(config_file, "w") as f:
                json.dump(backup_config, f, indent=2)

            if self.deployment_type == "standalone":
                shutil.chown(str(config_file), user="coffeebreak", group="coffeebreak")
                os.chmod(str(config_file), 0o640)

            if self.verbose:
                print(f"Local backup storage created: {backup_dir}")
                print(f"Available space: {storage_info.get('available_gb', 'unknown')} GB")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Local storage setup failed: {e}")

        return setup_result

    def _setup_remote_storage(self, backup_dir: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup remote backup storage."""
        setup_result = {"success": True, "errors": [], "info": {}}

        try:
            remote_type = config.get("remote_storage_type", "s3")

            if remote_type == "s3":
                s3_setup = self._setup_s3_storage(backup_dir, config)
                setup_result.update(s3_setup)
            elif remote_type == "rsync":
                rsync_setup = self._setup_rsync_storage(backup_dir, config)
                setup_result.update(rsync_setup)
            elif remote_type == "sftp":
                sftp_setup = self._setup_sftp_storage(backup_dir, config)
                setup_result.update(sftp_setup)
            else:
                setup_result["success"] = False
                setup_result["errors"].append(f"Unsupported remote storage type: {remote_type}")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Remote storage setup failed: {e}")

        return setup_result

    def _setup_s3_storage(self, backup_dir: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup S3-compatible storage."""
        setup_result = {"success": True, "errors": [], "info": {"remote_type": "s3"}}

        try:
            # Check if AWS CLI is available
            result = subprocess.run(["which", "aws"], capture_output=True)
            if result.returncode != 0:
                # Try to install AWS CLI
                try:
                    if subprocess.run(["which", "pip3"], capture_output=True).returncode == 0:
                        subprocess.run(["pip3", "install", "awscli"], check=True)
                    else:
                        raise Exception("AWS CLI not available and pip3 not found")
                except Exception as e:
                    setup_result["errors"].append(f"Failed to install AWS CLI: {e}")
                    return setup_result

            # Create S3 sync script
            s3_bucket = config.get("s3_bucket")
            s3_region = config.get("s3_region", "us-east-1")
            s3_prefix = config.get("s3_prefix", "coffeebreak-backups")

            if not s3_bucket:
                setup_result["errors"].append("S3 bucket not specified in configuration")
                return setup_result

            if self.deployment_type == "standalone":
                scripts_dir = "/opt/coffeebreak/bin"
            else:
                scripts_dir = "./scripts"

            s3_sync_script = f"""#!/bin/bash
# CoffeeBreak S3 Backup Sync Script

set -euo pipefail

BACKUP_DIR="{backup_dir}"
S3_BUCKET="{s3_bucket}"
S3_PREFIX="{s3_prefix}"
LOG_FILE="/var/log/coffeebreak/s3-sync.log"

# Function to log with timestamp
log_message() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}}

# Function to sync to S3
sync_to_s3() {{
    log_message "Starting S3 sync"

    # Sync backup directory to S3
    if aws s3 sync "$BACKUP_DIR" "s3://$S3_BUCKET/$S3_PREFIX" --region {s3_region} --delete; then
        log_message "S3 sync completed successfully"
        return 0
    else
        log_message "S3 sync failed"
        return 1
    fi
}}

# Function to verify S3 sync
verify_s3_sync() {{
    log_message "Verifying S3 sync"

    local local_files=$(find "$BACKUP_DIR" -type f | wc -l)
    local s3_files=$(aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX" --recursive | wc -l)

    log_message "Local files: $local_files, S3 files: $s3_files"

    if [ "$s3_files" -gt 0 ]; then
        log_message "S3 sync verification passed"
        return 0
    else
        log_message "S3 sync verification failed"
        return 1
    fi
}}

# Main function
main() {{
    local action="${{1:-sync}}"

    case "$action" in
        "sync")
            sync_to_s3
            ;;
        "verify")
            verify_s3_sync
            ;;
        *)
            echo "Usage: $0 {{sync|verify}}"
            exit 1
            ;;
    esac
}}

main "$@"
"""

            s3_script_path = f"{scripts_dir}/s3-sync.sh"
            os.makedirs(scripts_dir, exist_ok=True)

            with open(s3_script_path, "w") as f:
                f.write(s3_sync_script)
            os.chmod(s3_script_path, 0o755)

            # Setup S3 sync cron job
            cron_entry = f"0 */6 * * * {s3_script_path} sync"

            try:
                current_crontab = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
                crontab_content = current_crontab.stdout if current_crontab.returncode == 0 else ""
            except Exception:
                crontab_content = ""

            if "s3-sync.sh" not in crontab_content:
                new_crontab = crontab_content.rstrip() + "\\n" + cron_entry + "\\n"
                process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
                process.communicate(input=new_crontab)

            setup_result["info"].update(
                {
                    "bucket": s3_bucket,
                    "region": s3_region,
                    "prefix": s3_prefix,
                    "sync_script": s3_script_path,
                }
            )

            if self.verbose:
                print(f"S3 storage configured: s3://{s3_bucket}/{s3_prefix}")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"S3 storage setup failed: {e}")

        return setup_result

    def _setup_rsync_storage(self, backup_dir: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup rsync-based remote storage."""
        setup_result = {"success": True, "errors": [], "info": {"remote_type": "rsync"}}

        try:
            rsync_host = config.get("rsync_host")
            rsync_path = config.get("rsync_path")
            rsync_user = config.get("rsync_user", "backup")

            if not rsync_host or not rsync_path:
                setup_result["errors"].append("Rsync host and path must be specified")
                return setup_result

            if self.deployment_type == "standalone":
                scripts_dir = "/opt/coffeebreak/bin"
            else:
                scripts_dir = "./scripts"

            rsync_script = f"""#!/bin/bash
# CoffeeBreak Rsync Backup Sync Script

set -euo pipefail

BACKUP_DIR="{backup_dir}"
RSYNC_HOST="{rsync_host}"
RSYNC_PATH="{rsync_path}"
RSYNC_USER="{rsync_user}"
LOG_FILE="/var/log/coffeebreak/rsync-sync.log"

# Function to log with timestamp
log_message() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}}

# Function to sync via rsync
sync_via_rsync() {{
    log_message "Starting rsync sync"

    # Sync backup directory via rsync
    if rsync -avz --delete "$BACKUP_DIR/" "$RSYNC_USER@$RSYNC_HOST:$RSYNC_PATH/"; then
        log_message "Rsync sync completed successfully"
        return 0
    else
        log_message "Rsync sync failed"
        return 1
    fi
}}

# Function to verify rsync sync
verify_rsync_sync() {{
    log_message "Verifying rsync sync"

    # Check if remote directory exists and has files
    if ssh "$RSYNC_USER@$RSYNC_HOST" "test -d $RSYNC_PATH && find $RSYNC_PATH -type f | head -1"; then
        log_message "Rsync sync verification passed"
        return 0
    else
        log_message "Rsync sync verification failed"
        return 1
    fi
}}

# Main function
main() {{
    local action="${{1:-sync}}"

    case "$action" in
        "sync")
            sync_via_rsync
            ;;
        "verify")
            verify_rsync_sync
            ;;
        *)
            echo "Usage: $0 {{sync|verify}}"
            exit 1
            ;;
    esac
}}

main "$@"
"""

            rsync_script_path = f"{scripts_dir}/rsync-sync.sh"
            os.makedirs(scripts_dir, exist_ok=True)

            with open(rsync_script_path, "w") as f:
                f.write(rsync_script)
            os.chmod(rsync_script_path, 0o755)

            setup_result["info"].update(
                {
                    "host": rsync_host,
                    "path": rsync_path,
                    "user": rsync_user,
                    "sync_script": rsync_script_path,
                }
            )

            if self.verbose:
                print(f"Rsync storage configured: {rsync_user}@{rsync_host}:{rsync_path}")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Rsync storage setup failed: {e}")

        return setup_result

    def _setup_sftp_storage(self, backup_dir: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup SFTP-based remote storage."""
        setup_result = {"success": True, "errors": [], "info": {"remote_type": "sftp"}}

        try:
            sftp_host = config.get("sftp_host")
            sftp_path = config.get("sftp_path")
            sftp_user = config.get("sftp_user", "backup")

            if not sftp_host or not sftp_path:
                setup_result["errors"].append("SFTP host and path must be specified")
                return setup_result

            if self.deployment_type == "standalone":
                scripts_dir = "/opt/coffeebreak/bin"
            else:
                scripts_dir = "./scripts"

            sftp_script = f"""#!/bin/bash
# CoffeeBreak SFTP Backup Sync Script

set -euo pipefail

BACKUP_DIR="{backup_dir}"
SFTP_HOST="{sftp_host}"
SFTP_PATH="{sftp_path}"
SFTP_USER="{sftp_user}"
LOG_FILE="/var/log/coffeebreak/sftp-sync.log"

# Function to log with timestamp
log_message() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}}

# Function to sync via SFTP
sync_via_sftp() {{
    log_message "Starting SFTP sync"

    # Create SFTP batch file
    local batch_file="/tmp/sftp-batch-$(date +%s)"

    cat > "$batch_file" << EOF
mkdir $SFTP_PATH
put -r $BACKUP_DIR/* $SFTP_PATH/
quit
EOF

    # Execute SFTP batch
    if sftp -b "$batch_file" "$SFTP_USER@$SFTP_HOST"; then
        log_message "SFTP sync completed successfully"
        rm -f "$batch_file"
        return 0
    else
        log_message "SFTP sync failed"
        rm -f "$batch_file"
        return 1
    fi
}}

# Function to verify SFTP sync
verify_sftp_sync() {{
    log_message "Verifying SFTP sync"

    # Check if remote directory exists
    if sftp "$SFTP_USER@$SFTP_HOST" <<< "ls $SFTP_PATH" | grep -q "."; then
        log_message "SFTP sync verification passed"
        return 0
    else
        log_message "SFTP sync verification failed"
        return 1
    fi
}}

# Main function
main() {{
    local action="${{1:-sync}}"

    case "$action" in
        "sync")
            sync_via_sftp
            ;;
        "verify")
            verify_sftp_sync
            ;;
        *)
            echo "Usage: $0 {{sync|verify}}"
            exit 1
            ;;
    esac
}}

main "$@"
"""

            sftp_script_path = f"{scripts_dir}/sftp-sync.sh"
            os.makedirs(scripts_dir, exist_ok=True)

            with open(sftp_script_path, "w") as f:
                f.write(sftp_script)
            os.chmod(sftp_script_path, 0o755)

            setup_result["info"].update(
                {
                    "host": sftp_host,
                    "path": sftp_path,
                    "user": sftp_user,
                    "sync_script": sftp_script_path,
                }
            )

            if self.verbose:
                print(f"SFTP storage configured: {sftp_user}@{sftp_host}:{sftp_path}")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"SFTP storage setup failed: {e}")

        return setup_result

    def _setup_storage_monitoring(self, backup_dir: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup storage monitoring and alerts."""
        setup_result = {"success": True, "errors": []}

        try:
            if self.deployment_type == "standalone":
                scripts_dir = "/opt/coffeebreak/bin"
            else:
                scripts_dir = "./scripts"

            # Storage monitoring script
            monitoring_script = f"""#!/bin/bash
# CoffeeBreak Storage Monitoring Script

BACKUP_DIR="{backup_dir}"
LOG_FILE="/var/log/coffeebreak/storage-monitor.log"
ALERT_EMAIL="{config.get("alert_email", "admin@localhost")}"
WARNING_THRESHOLD={config.get("storage_warning_percent", 80)}
CRITICAL_THRESHOLD={config.get("storage_critical_percent", 90)}

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
        echo "$message" | mail -s "CoffeeBreak Storage Alert: $subject" "$ALERT_EMAIL"
    fi

    if [ -f "/opt/coffeebreak/bin/notify.sh" ]; then
        /opt/coffeebreak/bin/notify.sh "$subject" "$message"
    fi

    logger -t coffeebreak-storage "ALERT: $subject - $message"
}}

# Function to check disk usage
check_disk_usage() {{
    log_message "Checking backup storage disk usage"

    local usage_info=$(df "$BACKUP_DIR" | tail -1)
    local usage_percent=$(echo "$usage_info" | awk '{{print $5}}' | sed 's/%//')
    local available_gb=$(echo "$usage_info" | awk '{{print int($4/1024/1024)}}')

    log_message "Storage usage: $usage_percent% ($available_gb GB available)"

    if [ "$usage_percent" -ge "$CRITICAL_THRESHOLD" ]; then
        send_alert "Critical Storage Usage" "Backup storage is $usage_percent% full ($available_gb GB available). Immediate action required!"
    elif [ "$usage_percent" -ge "$WARNING_THRESHOLD" ]; then
        send_alert "High Storage Usage" "Backup storage is $usage_percent% full ($available_gb GB available). Consider cleanup."
    fi
}}

# Function to check backup directory health
check_backup_health() {{
    log_message "Checking backup directory health"

    if [ ! -d "$BACKUP_DIR" ]; then
        send_alert "Backup Directory Missing" "Backup directory $BACKUP_DIR does not exist"
        return 1
    fi

    if [ ! -w "$BACKUP_DIR" ]; then
        send_alert "Backup Directory Not Writable" "Cannot write to backup directory $BACKUP_DIR"
        return 1
    fi

    # Check subdirectories
    local subdirs=("postgresql" "mongodb" "files" "configs")
    for subdir in "${{subdirs[@]}}"; do
        if [ ! -d "$BACKUP_DIR/$subdir" ]; then
            send_alert "Backup Subdirectory Missing" "Backup subdirectory $BACKUP_DIR/$subdir is missing"
        fi
    done
}}

# Function to check storage performance
check_storage_performance() {{
    log_message "Checking storage performance"

    local test_file="$BACKUP_DIR/.storage-test-$(date +%s)"
    local start_time=$(date +%s.%N)

    # Write test (10MB)
    if dd if=/dev/zero of="$test_file" bs=1M count=10 &>/dev/null; then
        local end_time=$(date +%s.%N)
        local write_time=$(echo "$end_time - $start_time" | bc)
        local write_speed=$(echo "scale=2; 10 / $write_time" | bc)

        log_message "Storage write speed: ${{write_speed}} MB/s"

        # Cleanup test file
        rm -f "$test_file"

        # Alert if write speed is too slow (less than 1 MB/s)
        if (( $(echo "$write_speed < 1" | bc -l) )); then
            send_alert "Slow Storage Performance" "Storage write speed is only ${{write_speed}} MB/s"
        fi
    else
        send_alert "Storage Write Test Failed" "Cannot write test file to $BACKUP_DIR"
    fi
}}

# Function to monitor remote storage sync
check_remote_sync() {{
    local sync_script_patterns=("s3-sync.sh" "rsync-sync.sh" "sftp-sync.sh")

    for pattern in "${{sync_script_patterns[@]}}"; do
        local sync_script=$(find /opt/coffeebreak/bin -name "$pattern" 2>/dev/null | head -1)

        if [ -f "$sync_script" ]; then
            log_message "Checking remote sync: $pattern"

            if "$sync_script" verify; then
                log_message "✓ Remote sync verification passed: $pattern"
            else
                send_alert "Remote Sync Failed" "Remote sync verification failed for $pattern"
            fi
        fi
    done
}}

# Main monitoring function
main() {{
    log_message "Starting storage monitoring check"

    check_disk_usage
    check_backup_health
    check_storage_performance
    check_remote_sync

    log_message "Storage monitoring check completed"
}}

main "$@"
"""

            monitoring_script_path = f"{scripts_dir}/storage-monitor.sh"
            os.makedirs(scripts_dir, exist_ok=True)

            with open(monitoring_script_path, "w") as f:
                f.write(monitoring_script)
            os.chmod(monitoring_script_path, 0o755)

            # Setup cron job for storage monitoring
            cron_entry = f"0 */4 * * * {monitoring_script_path}"

            try:
                current_crontab = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
                crontab_content = current_crontab.stdout if current_crontab.returncode == 0 else ""
            except Exception:
                crontab_content = ""

            if "storage-monitor.sh" not in crontab_content:
                new_crontab = crontab_content.rstrip() + "\\n" + cron_entry + "\\n"
                process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
                process.communicate(input=new_crontab)

            if self.verbose:
                print("Storage monitoring configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Storage monitoring setup failed: {e}")

        return setup_result

    def _get_storage_info(self, backup_dir: str) -> Dict[str, Any]:
        """Get storage information for backup directory."""
        try:
            # Get disk usage information
            result = subprocess.run(["df", backup_dir], capture_output=True, text=True)

            if result.returncode == 0:
                lines = result.stdout.strip().split("\\n")
                if len(lines) >= 2:
                    fields = lines[1].split()

                    return {
                        "filesystem": fields[0],
                        "total_kb": int(fields[1]),
                        "used_kb": int(fields[2]),
                        "available_kb": int(fields[3]),
                        "total_gb": round(int(fields[1]) / 1024 / 1024, 2),
                        "used_gb": round(int(fields[2]) / 1024 / 1024, 2),
                        "available_gb": round(int(fields[3]) / 1024 / 1024, 2),
                        "usage_percent": fields[4],
                    }

            return {"error": "Could not get storage information"}

        except Exception as e:
            return {"error": f"Failed to get storage info: {e}"}
