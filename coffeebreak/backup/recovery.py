"""Recovery and disaster recovery system for CoffeeBreak."""

import os
from datetime import datetime
from typing import Any, Dict


class RecoveryManager:
    """Manages backup recovery and disaster recovery procedures."""

    def __init__(self, deployment_type: str = "docker", verbose: bool = False):
        """
        Initialize recovery manager.

        Args:
            deployment_type: Type of deployment (docker, standalone)
            verbose: Enable verbose output
        """
        self.deployment_type = deployment_type
        self.verbose = verbose

    def setup_recovery_procedures(self, domain: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Setup recovery procedures and disaster recovery plans.

        Args:
            domain: Production domain
            config: Recovery configuration

        Returns:
            Dict[str, Any]: Setup results
        """
        setup_result = {
            "success": True,
            "errors": [],
            "recovery_scripts": [],
            "disaster_recovery_plan": None,
        }

        try:
            if self.deployment_type == "standalone":
                scripts_dir = "/opt/coffeebreak/bin"
                recovery_dir = "/opt/coffeebreak/recovery"
            else:
                scripts_dir = "./scripts"
                recovery_dir = "./recovery"

            os.makedirs(scripts_dir, exist_ok=True)
            os.makedirs(recovery_dir, exist_ok=True)

            # Create recovery scripts
            scripts_result = self._create_recovery_scripts(domain, config, scripts_dir)
            if scripts_result["success"]:
                setup_result["recovery_scripts"] = scripts_result["scripts"]
            else:
                setup_result["errors"].extend(scripts_result["errors"])

            # Create disaster recovery plan
            dr_plan_result = self._create_disaster_recovery_plan(domain, config, recovery_dir)
            if dr_plan_result["success"]:
                setup_result["disaster_recovery_plan"] = dr_plan_result["plan_file"]
            else:
                setup_result["errors"].extend(dr_plan_result["errors"])

            # Create recovery documentation
            docs_result = self._create_recovery_documentation(domain, config, recovery_dir)
            if not docs_result["success"]:
                setup_result["errors"].extend(docs_result["errors"])

            setup_result["success"] = len(setup_result["errors"]) == 0

            if self.verbose:
                print("Recovery procedures configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Recovery procedures setup failed: {e}")

        return setup_result

    def _create_recovery_scripts(self, domain: str, config: Dict[str, Any], scripts_dir: str) -> Dict[str, Any]:
        """Create recovery scripts for different scenarios."""
        setup_result = {"success": True, "errors": [], "scripts": []}

        try:
            backup_dir = config.get("backup_dir", "/opt/coffeebreak/backups")

            # Main recovery script
            recovery_script = f"""#!/bin/bash
# CoffeeBreak Recovery Script
# Domain: {domain}
# Generated: {datetime.now().isoformat()}

set -euo pipefail

DOMAIN="{domain}"
BACKUP_DIR="{backup_dir}"
LOG_FILE="/var/log/coffeebreak/recovery.log"
RECOVERY_MODE="${{1:-interactive}}"

# Function to log with timestamp
log_message() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}}

# Function to handle errors
handle_error() {{
    local error_msg="$1"
    log_message "ERROR: $error_msg"

    # Send alert
    if [ -f "/opt/coffeebreak/bin/notify.sh" ]; then
        /opt/coffeebreak/bin/notify.sh "Recovery Failed" "$error_msg"
    fi

    exit 1
}}

# Function to prompt user for confirmation
confirm_action() {{
    local message="$1"

    if [ "$RECOVERY_MODE" = "interactive" ]; then
        echo "$message"
        read -p "Do you want to continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_message "Recovery cancelled by user"
            exit 0
        fi
    else
        log_message "AUTO: $message"
    fi
}}

# Function to list available backups
list_backups() {{
    local backup_type="$1"

    echo "Available $backup_type backups:"
    find "$BACKUP_DIR/$backup_type" -type f -name "*.tar.gz" -o -name "*.gpg" | sort -r | head -10 | while read backup; do
        local backup_date=$(basename "$backup" | grep -oE '[0-9]{{8}}_[0-9]{{6}}' || echo "unknown")
        local backup_size=$(du -h "$backup" | cut -f1)
        echo "  $(basename "$backup") ($backup_size, $backup_date)"
    done
}}

# Function to select backup
select_backup() {{
    local backup_type="$1"
    local backup_date="${{2:-latest}}"

    if [ "$backup_date" = "latest" ]; then
        local selected_backup=$(find "$BACKUP_DIR/$backup_type" -type f \\( -name "*.tar.gz" -o -name "*.gpg" \\) | sort -r | head -1)
    else
        local selected_backup=$(find "$BACKUP_DIR/$backup_type" -type f -name "*$backup_date*" | head -1)
    fi

    if [ -z "$selected_backup" ]; then
        handle_error "No backup found for type: $backup_type, date: $backup_date"
    fi

    echo "$selected_backup"
}}

# Function to decrypt and extract backup
extract_backup() {{
    local backup_file="$1"
    local extract_dir="$2"

    log_message "Extracting backup: $backup_file"

    mkdir -p "$extract_dir"
    cd "$extract_dir"

    if [[ "$backup_file" == *.gpg ]]; then
        log_message "Decrypting backup..."
        if ! gpg --decrypt "$backup_file" > "$(basename "$backup_file" .gpg)"; then
            handle_error "Failed to decrypt backup: $backup_file"
        fi
        backup_file="$extract_dir/$(basename "$backup_file" .gpg)"
    fi

    if [[ "$backup_file" == *.tar.gz ]]; then
        log_message "Extracting archive..."
        if ! tar -xzf "$backup_file"; then
            handle_error "Failed to extract backup: $backup_file"
        fi
    fi

    log_message "Backup extracted successfully"
}}

# Function to recover PostgreSQL
recover_postgresql() {{
    local backup_date="${{1:-latest}}"

    log_message "Starting PostgreSQL recovery"
    confirm_action "This will restore PostgreSQL databases from backup ($backup_date). This will OVERWRITE existing data!"

    # Stop CoffeeBreak services
    log_message "Stopping CoffeeBreak services..."
    systemctl stop coffeebreak-* 2>/dev/null || true

    # Get backup file
    local backup_file=$(select_backup "postgresql" "$backup_date")
    local extract_dir="/tmp/coffeebreak-recovery-pg"

    # Extract backup
    extract_backup "$backup_file" "$extract_dir"

    # Find SQL files
    local sql_files=$(find "$extract_dir" -name "*.sql" | sort)

    if [ -z "$sql_files" ]; then
        handle_error "No SQL files found in backup"
    fi

    # Stop PostgreSQL temporarily for full restore
    systemctl stop postgresql

    # Restore globals first
    local globals_file=$(echo "$sql_files" | grep "globals.sql" || echo "")
    if [ -n "$globals_file" ]; then
        log_message "Restoring PostgreSQL globals..."
        sudo -u postgres psql -f "$globals_file" postgres || handle_error "Failed to restore PostgreSQL globals"
    fi

    # Start PostgreSQL
    systemctl start postgresql

    # Restore individual databases
    for sql_file in $sql_files; do
        if [[ "$sql_file" != *"globals.sql" ]]; then
            local db_name=$(basename "$sql_file" .sql)
            log_message "Restoring database: $db_name"

            # Drop and recreate database
            sudo -u postgres dropdb "$db_name" 2>/dev/null || true
            sudo -u postgres createdb "$db_name" || handle_error "Failed to create database: $db_name"

            # Restore database
            sudo -u postgres psql -d "$db_name" -f "$sql_file" || handle_error "Failed to restore database: $db_name"
        fi
    done

    # Cleanup
    rm -rf "$extract_dir"

    log_message "PostgreSQL recovery completed"
}}

# Function to recover MongoDB
recover_mongodb() {{
    local backup_date="${{1:-latest}}"

    log_message "Starting MongoDB recovery"
    confirm_action "This will restore MongoDB databases from backup ($backup_date). This will OVERWRITE existing data!"

    # Stop CoffeeBreak services
    log_message "Stopping CoffeeBreak services..."
    systemctl stop coffeebreak-* 2>/dev/null || true

    # Get backup file
    local backup_file=$(select_backup "mongodb" "$backup_date")
    local extract_dir="/tmp/coffeebreak-recovery-mongo"

    # Extract backup
    extract_backup "$backup_file" "$extract_dir"

    # Find dump directory
    local dump_dir=$(find "$extract_dir" -type d -name "*" | head -1)

    if [ -z "$dump_dir" ] || [ ! -d "$dump_dir" ]; then
        handle_error "No MongoDB dump directory found in backup"
    fi

    # Drop existing databases and restore
    log_message "Restoring MongoDB databases..."
    mongorestore --drop "$dump_dir" || handle_error "Failed to restore MongoDB"

    # Cleanup
    rm -rf "$extract_dir"

    log_message "MongoDB recovery completed"
}}

# Function to recover files
recover_files() {{
    local backup_date="${{1:-latest}}"

    log_message "Starting file recovery"
    confirm_action "This will restore application files from backup ($backup_date). This will OVERWRITE existing files!"

    # Stop CoffeeBreak services
    log_message "Stopping CoffeeBreak services..."
    systemctl stop coffeebreak-* 2>/dev/null || true

    # Get backup file
    local backup_file=$(select_backup "files" "$backup_date")
    local extract_dir="/tmp/coffeebreak-recovery-files"

    # Extract backup
    extract_backup "$backup_file" "$extract_dir"

    # Restore directories
    local restore_dirs=(
        "opt/coffeebreak/data:/opt/coffeebreak/data"
        "opt/coffeebreak/uploads:/opt/coffeebreak/uploads"
        "opt/coffeebreak/plugins:/opt/coffeebreak/plugins"
        "var/log/coffeebreak:/var/log/coffeebreak"
    )

    for dir_mapping in "${{restore_dirs[@]}}"; do
        local src_dir="$extract_dir/${{dir_mapping%%:*}}"
        local dest_dir="${{dir_mapping##*:}}"

        if [ -d "$src_dir" ]; then
            log_message "Restoring directory: $dest_dir"

            # Backup current directory
            if [ -d "$dest_dir" ]; then
                mv "$dest_dir" "$dest_dir.backup.$(date +%Y%m%d_%H%M%S)" || true
            fi

            # Create parent directory
            mkdir -p "$(dirname "$dest_dir")"

            # Copy files
            cp -r "$src_dir" "$dest_dir" || handle_error "Failed to restore directory: $dest_dir"

            # Fix permissions
            if id coffeebreak &>/dev/null; then
                chown -R coffeebreak:coffeebreak "$dest_dir" 2>/dev/null || true
            fi
        fi
    done

    # Restore Docker volumes if Docker deployment
    if [ -f "/usr/bin/docker" ] && docker ps -q > /dev/null 2>&1; then
        local volumes_dir="$extract_dir/docker-volumes"

        if [ -d "$volumes_dir" ]; then
            log_message "Restoring Docker volumes..."

            for volume_archive in "$volumes_dir"/*.tar.gz; do
                if [ -f "$volume_archive" ]; then
                    local volume_name=$(basename "$volume_archive" .tar.gz)

                    log_message "Restoring Docker volume: $volume_name"

                    # Remove existing volume
                    docker volume rm "$volume_name" 2>/dev/null || true

                    # Create new volume
                    docker volume create "$volume_name"

                    # Restore volume content
                    docker run --rm -v "$volume_name:/dest" -v "$volumes_dir:/backup" ubuntu tar xzf "/backup/$(basename "$volume_archive")" -C /dest || log_message "WARNING: Failed to restore volume $volume_name"
                fi
            done
        fi
    fi

    # Cleanup
    rm -rf "$extract_dir"

    log_message "File recovery completed"
}}

# Function to recover configurations
recover_configs() {{
    local backup_date="${{1:-latest}}"

    log_message "Starting configuration recovery"
    confirm_action "This will restore configuration files from backup ($backup_date). This will OVERWRITE existing configs!"

    # Get backup file
    local backup_file=$(select_backup "configs" "$backup_date")
    local extract_dir="/tmp/coffeebreak-recovery-configs"

    # Extract backup
    extract_backup "$backup_file" "$extract_dir"

    # Restore configuration files
    local config_files=$(find "$extract_dir" -type f)

    for config_file in $config_files; do
        local relative_path="${{config_file#$extract_dir/}}"
        local dest_file="/$relative_path"

        log_message "Restoring config: $dest_file"

        # Backup current file
        if [ -f "$dest_file" ]; then
            cp "$dest_file" "$dest_file.backup.$(date +%Y%m%d_%H%M%S)" || true
        fi

        # Create parent directory
        mkdir -p "$(dirname "$dest_file")"

        # Copy file
        cp "$config_file" "$dest_file" || log_message "WARNING: Failed to restore config: $dest_file"
    done

    # Cleanup
    rm -rf "$extract_dir"

    log_message "Configuration recovery completed"
}}

# Function to perform full system recovery
full_recovery() {{
    local backup_date="${{1:-latest}}"

    log_message "Starting full system recovery"
    confirm_action "This will perform a COMPLETE SYSTEM RECOVERY from backup ($backup_date). This will OVERWRITE ALL DATA!"

    # Recovery order: configs -> files -> databases
    recover_configs "$backup_date"
    recover_files "$backup_date"
    recover_postgresql "$backup_date"
    recover_mongodb "$backup_date"

    # Restart services
    log_message "Restarting CoffeeBreak services..."
    systemctl daemon-reload
    systemctl start coffeebreak-* || handle_error "Failed to start CoffeeBreak services"

    # Verify recovery
    log_message "Verifying recovery..."
    sleep 10

    if systemctl is-active --quiet coffeebreak-api; then
        log_message "✓ CoffeeBreak API is running"
    else
        log_message "✗ CoffeeBreak API is not running"
    fi

    # Test basic connectivity
    if curl -s --max-time 10 "https://{domain}/health" > /dev/null; then
        log_message "✓ CoffeeBreak is responding to HTTPS requests"
    else
        log_message "✗ CoffeeBreak is not responding to HTTPS requests"
    fi

    log_message "Full system recovery completed"

    # Send success notification
    if [ -f "/opt/coffeebreak/bin/notify.sh" ]; then
        /opt/coffeebreak/bin/notify.sh "System Recovery Completed" "Full system recovery from backup ($backup_date) completed successfully"
    fi
}}

# Function to show recovery menu
show_menu() {{
    echo "CoffeeBreak Recovery System"
    echo "=========================="
    echo "1. List available backups"
    echo "2. Recover PostgreSQL databases"
    echo "3. Recover MongoDB databases"
    echo "4. Recover application files"
    echo "5. Recover configuration files"
    echo "6. Full system recovery"
    echo "7. Exit"
    echo
}}

# Main recovery function
main() {{
    local action="${{1:-menu}}"
    local backup_date="${{2:-latest}}"

    log_message "CoffeeBreak recovery system started (action: $action)"

    case "$action" in
        "list")
            echo "PostgreSQL backups:"
            list_backups "postgresql"
            echo
            echo "MongoDB backups:"
            list_backups "mongodb"
            echo
            echo "File backups:"
            list_backups "files"
            echo
            echo "Config backups:"
            list_backups "configs"
            ;;
        "postgresql"|"pg")
            recover_postgresql "$backup_date"
            ;;
        "mongodb"|"mongo")
            recover_mongodb "$backup_date"
            ;;
        "files")
            recover_files "$backup_date"
            ;;
        "configs")
            recover_configs "$backup_date"
            ;;
        "full")
            full_recovery "$backup_date"
            ;;
        "menu")
            while true; do
                show_menu
                read -p "Select an option (1-7): " choice

                case $choice in
                    1) main "list" ;;
                    2)
                        read -p "Enter backup date (YYYYMMDD_HHMMSS) or 'latest': " date
                        main "postgresql" "$date"
                        ;;
                    3)
                        read -p "Enter backup date (YYYYMMDD_HHMMSS) or 'latest': " date
                        main "mongodb" "$date"
                        ;;
                    4)
                        read -p "Enter backup date (YYYYMMDD_HHMMSS) or 'latest': " date
                        main "files" "$date"
                        ;;
                    5)
                        read -p "Enter backup date (YYYYMMDD_HHMMSS) or 'latest': " date
                        main "configs" "$date"
                        ;;
                    6)
                        read -p "Enter backup date (YYYYMMDD_HHMMSS) or 'latest': " date
                        main "full" "$date"
                        ;;
                    7)
                        echo "Exiting recovery system"
                        exit 0
                        ;;
                    *)
                        echo "Invalid option. Please try again."
                        ;;
                esac

                echo
                read -p "Press Enter to continue..."
            done
            ;;
        *)
            echo "Usage: $0 {{list|postgresql|mongodb|files|configs|full|menu}} [backup_date]"
            echo "  backup_date: YYYYMMDD_HHMMSS format or 'latest'"
            exit 1
            ;;
    esac

    log_message "Recovery operation completed"
}}

main "$@"
"""

            recovery_script_path = f"{scripts_dir}/recovery.sh"
            with open(recovery_script_path, "w") as f:
                f.write(recovery_script)
            os.chmod(recovery_script_path, 0o755)

            setup_result["scripts"].append(recovery_script_path)

            # Quick recovery script for emergencies
            quick_recovery_script = f"""#!/bin/bash
# CoffeeBreak Quick Recovery Script - Emergency Use Only

set -euo pipefail

RECOVERY_SCRIPT="{scripts_dir}/recovery.sh"

echo "CoffeeBreak Emergency Recovery"
echo "============================="
echo "This will perform an automated full system recovery using the latest backup."
echo "This is intended for emergency situations only."
echo
echo "WARNING: This will OVERWRITE ALL EXISTING DATA!"
echo

read -p "Are you absolutely sure you want to continue? Type 'YES' to confirm: " confirmation

if [ "$confirmation" != "YES" ]; then
    echo "Recovery cancelled."
    exit 0
fi

echo "Starting emergency recovery in 5 seconds..."
sleep 5

# Run full recovery in non-interactive mode
RECOVERY_MODE=auto "$RECOVERY_SCRIPT" full latest

echo "Emergency recovery completed. Please verify system functionality."
"""

            quick_recovery_script_path = f"{scripts_dir}/emergency-recovery.sh"
            with open(quick_recovery_script_path, "w") as f:
                f.write(quick_recovery_script)
            os.chmod(quick_recovery_script_path, 0o755)

            setup_result["scripts"].append(quick_recovery_script_path)

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Recovery scripts creation failed: {e}")

        return setup_result

    def _create_disaster_recovery_plan(self, domain: str, config: Dict[str, Any], recovery_dir: str) -> Dict[str, Any]:
        """Create disaster recovery plan documentation."""
        setup_result = {"success": True, "errors": [], "plan_file": None}

        try:
            # Disaster recovery plan content
            dr_plan = f"""# CoffeeBreak Disaster Recovery Plan
# Domain: {domain}
# Generated: {datetime.now().isoformat()}

## Overview
This document outlines the disaster recovery procedures for the CoffeeBreak application deployment at {domain}.

## Recovery Objectives
- **Recovery Time Objective (RTO)**: {config.get("rto_hours", 4)} hours
- **Recovery Point Objective (RPO)**: {config.get("rpo_hours", 1)} hour
- **Backup Retention**: {config.get("retention_days", 30)} days

## Emergency Contacts
- Primary Administrator: {config.get("admin_email", "admin@" + domain)}
- Secondary Contact: {config.get("secondary_email", "backup-admin@" + domain)}
- Hosting Provider: {config.get("hosting_contact", "N/A")}

## Pre-Disaster Preparation Checklist
- [ ] Verify backup automation is functioning
- [ ] Test recovery procedures monthly
- [ ] Maintain off-site backup copies
- [ ] Document all passwords and access credentials
- [ ] Keep emergency contact list updated

## Disaster Scenarios and Procedures

### Scenario 1: Application Service Failure
**Symptoms**: CoffeeBreak application not responding, 500 errors
**Recovery Steps**:
1. Check service status: `systemctl status coffeebreak-*`
2. Check logs: `journalctl -u coffeebreak-* --since "1 hour ago"`
3. Restart services: `systemctl restart coffeebreak-*`
4. If issues persist, check database connectivity
5. If still failing, consider configuration recovery

### Scenario 2: Database Corruption
**Symptoms**: Database connection errors, data inconsistencies
**Recovery Steps**:
1. Stop CoffeeBreak services: `systemctl stop coffeebreak-*`
2. Backup current database state (if possible)
3. Run database recovery: `/opt/coffeebreak/bin/recovery.sh postgresql`
4. Verify data integrity
5. Restart services

### Scenario 3: File System Corruption
**Symptoms**: File access errors, missing files
**Recovery Steps**:
1. Assess extent of corruption
2. Stop all services
3. Recover files: `/opt/coffeebreak/bin/recovery.sh files`
4. Verify file permissions
5. Restart services

### Scenario 4: Complete System Failure
**Symptoms**: Server not responding, hardware failure
**Recovery Steps**:
1. Provision new server with same specifications
2. Install base CoffeeBreak system
3. Run emergency recovery: `/opt/coffeebreak/bin/emergency-recovery.sh`
4. Update DNS if IP address changed
5. Verify all functionality

### Scenario 5: Security Breach
**Symptoms**: Unauthorized access, suspicious activity
**Recovery Steps**:
1. Immediately stop all services
2. Disconnect from network if necessary
3. Assess breach extent
4. Recover from clean backup: `/opt/coffeebreak/bin/recovery.sh full`
5. Update all passwords and certificates
6. Review logs for breach timeline

## Recovery Procedures

### Quick Recovery Commands
```bash
# List available backups
/opt/coffeebreak/bin/recovery.sh list

# Emergency full recovery (latest backup)
/opt/coffeebreak/bin/emergency-recovery.sh

# Interactive recovery menu
/opt/coffeebreak/bin/recovery.sh menu

# Specific component recovery
/opt/coffeebreak/bin/recovery.sh postgresql latest
/opt/coffeebreak/bin/recovery.sh mongodb latest
/opt/coffeebreak/bin/recovery.sh files latest
/opt/coffeebreak/bin/recovery.sh configs latest
```

### Post-Recovery Verification
1. **Service Status**:
   ```bash
   systemctl status coffeebreak-*
   systemctl status nginx
   systemctl status postgresql
   systemctl status mongod
   ```

2. **Application Health**:
   ```bash
   curl -k https://{domain}/health
   ```

3. **Database Connectivity**:
   ```bash
   sudo -u postgres psql -c "\\l"
   mongo --eval "db.adminCommand('listDatabases')"
   ```

4. **File Permissions**:
   ```bash
   ls -la /opt/coffeebreak/
   ```

## Backup Verification Schedule
- **Daily**: Automated backup verification
- **Weekly**: Manual recovery test
- **Monthly**: Full disaster recovery simulation

## Communication Plan
1. **Assessment Phase**: Notify primary stakeholders of incident
2. **Recovery Phase**: Provide hourly updates on recovery progress
3. **Resolution Phase**: Confirm system restoration and lessons learned

## Recovery Time Estimates
- **Service Restart**: 5-10 minutes
- **Configuration Recovery**: 15-30 minutes
- **Database Recovery**: 30-60 minutes
- **File Recovery**: 45-90 minutes
- **Full System Recovery**: 2-4 hours
- **New Server Provisioning**: 4-8 hours

## Testing Schedule
- **Monthly**: Recovery procedure testing
- **Quarterly**: Full disaster recovery simulation
- **Annually**: Plan review and update

## Documentation Updates
This plan should be reviewed and updated:
- After any significant system changes
- Following any disaster recovery events
- Quarterly as part of routine maintenance

## Appendix A: System Architecture
```
[Architecture details would be included here]
```

## Appendix B: Network Configuration
```
[Network configuration details would be included here]
```

## Appendix C: Vendor Contacts
```
[Vendor contact information would be included here]
```

---
**Last Updated**: {datetime.now().isoformat()}
**Next Review Date**: {(datetime.now().replace(month=datetime.now().month + 3)).isoformat()[:10]}
"""

            plan_file_path = f"{recovery_dir}/disaster-recovery-plan.md"
            with open(plan_file_path, "w") as f:
                f.write(dr_plan)

            setup_result["plan_file"] = plan_file_path

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Disaster recovery plan creation failed: {e}")

        return setup_result

    def _create_recovery_documentation(self, domain: str, config: Dict[str, Any], recovery_dir: str) -> Dict[str, Any]:
        """Create additional recovery documentation."""
        setup_result = {"success": True, "errors": []}

        try:
            # Recovery checklist
            checklist = f"""# CoffeeBreak Recovery Checklist
# Domain: {domain}

## Pre-Recovery Checklist
- [ ] Identify the type of failure
- [ ] Assess the scope of impact
- [ ] Notify stakeholders
- [ ] Stop affected services
- [ ] Identify appropriate backup to restore

## During Recovery
- [ ] Follow the disaster recovery plan
- [ ] Document all actions taken
- [ ] Monitor recovery progress
- [ ] Keep stakeholders informed

## Post-Recovery Checklist
- [ ] Verify all services are running
- [ ] Test application functionality
- [ ] Check database integrity
- [ ] Verify file permissions
- [ ] Test user authentication
- [ ] Monitor system for 24 hours
- [ ] Document lessons learned
- [ ] Update recovery procedures if needed

## Recovery Commands Reference
```bash
# Service management
systemctl status coffeebreak-*
systemctl restart coffeebreak-*
systemctl stop coffeebreak-*

# Recovery operations
/opt/coffeebreak/bin/recovery.sh list
/opt/coffeebreak/bin/recovery.sh menu
/opt/coffeebreak/bin/emergency-recovery.sh

# Health checks
curl -k https://{domain}/health
systemctl is-active coffeebreak-api

# Log inspection
journalctl -u coffeebreak-* --since "1 hour ago"
tail -f /var/log/coffeebreak/*.log
```
"""

            with open(f"{recovery_dir}/recovery-checklist.md", "w") as f:
                f.write(checklist)

            # Recovery runbook
            runbook = f"""# CoffeeBreak Recovery Runbook
# Domain: {domain}

## Emergency Contacts
- Primary: {config.get("admin_email", "admin@" + domain)}
- Secondary: {config.get("secondary_email", "backup-admin@" + domain)}

## Critical Information
- Backup Location: {config.get("backup_dir", "/opt/coffeebreak/backups")}
- Recovery Scripts: /opt/coffeebreak/bin/
- Log Files: /var/log/coffeebreak/

## Step-by-Step Recovery Procedures

### 1. Initial Assessment
1. Access the server
2. Run system status check: `/opt/coffeebreak/bin/system-status.sh`
3. Identify failed components
4. Check recent logs for error patterns

### 2. Service Recovery
```bash
# Check service status
systemctl status coffeebreak-api coffeebreak-frontend coffeebreak-events

# Restart individual services
systemctl restart coffeebreak-api
systemctl restart coffeebreak-frontend
systemctl restart coffeebreak-events

# Check if recovery is successful
curl -k https://{domain}/health
```

### 3. Database Recovery
```bash
# PostgreSQL recovery
/opt/coffeebreak/bin/recovery.sh postgresql latest

# MongoDB recovery
/opt/coffeebreak/bin/recovery.sh mongodb latest

# Verify database connectivity
sudo -u postgres psql -c "\\l"
mongo --eval "db.adminCommand('listDatabases')"
```

### 4. File Recovery
```bash
# Recover application files
/opt/coffeebreak/bin/recovery.sh files latest

# Check file permissions
ls -la /opt/coffeebreak/
chown -R coffeebreak:coffeebreak /opt/coffeebreak/
```

### 5. Configuration Recovery
```bash
# Recover configuration files
/opt/coffeebreak/bin/recovery.sh configs latest

# Reload systemd
systemctl daemon-reload

# Restart services
systemctl restart coffeebreak-*
```

### 6. Full System Recovery
```bash
# Emergency full recovery
/opt/coffeebreak/bin/emergency-recovery.sh

# Or interactive recovery
/opt/coffeebreak/bin/recovery.sh menu
```

## Troubleshooting Common Issues

### Issue: Services won't start
**Symptoms**: systemctl start fails
**Solutions**:
1. Check service logs: `journalctl -u coffeebreak-api`
2. Verify configuration files
3. Check file permissions
4. Ensure databases are running

### Issue: Database connection errors
**Symptoms**: Connection refused, authentication errors
**Solutions**:
1. Check database service status
2. Verify connection credentials
3. Check network connectivity
4. Review database logs

### Issue: SSL/HTTPS errors
**Symptoms**: Certificate errors, HTTPS not working
**Solutions**:
1. Check certificate expiry
2. Verify nginx configuration
3. Check file permissions on certificates
4. Restart nginx service

### Issue: High disk usage
**Symptoms**: No space left on device
**Solutions**:
1. Clean old logs: `find /var/log -name "*.log" -mtime +7 -delete`
2. Clean old backups: `/opt/coffeebreak/bin/backup.sh cleanup`
3. Check for large files: `du -sh /* | sort -hr`

## Recovery Validation Steps
1. All services show as active: `systemctl is-active coffeebreak-*`
2. Application responds: `curl -k https://{domain}/health`
3. User can log in through web interface
4. Database queries work properly
5. File uploads/downloads work
6. Monitor system for 24 hours

## Escalation Procedures
1. If recovery fails after 2 hours, escalate to senior admin
2. If data loss is detected, immediately contact stakeholders
3. If security breach is suspected, follow security incident procedures
"""

            with open(f"{recovery_dir}/recovery-runbook.md", "w") as f:
                f.write(runbook)

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Recovery documentation creation failed: {e}")

        return setup_result
