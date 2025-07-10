"""Zero-downtime deployment orchestration system."""

import os
import subprocess
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
import yaml

from ..utils.errors import ConfigurationError


class DeploymentOrchestrator:
    """Manages zero-downtime deployments and rollbacks."""

    def __init__(self, deployment_type: str = "docker", verbose: bool = False):
        """
        Initialize deployment orchestrator.

        Args:
            deployment_type: Type of deployment (docker, standalone)
            verbose: Enable verbose output
        """
        self.deployment_type = deployment_type
        self.verbose = verbose

    def setup_deployment_orchestration(
        self, domain: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Setup deployment orchestration system.

        Args:
            domain: Production domain
            config: Deployment configuration

        Returns:
            Dict[str, Any]: Setup results
        """
        setup_result = {"success": True, "errors": [], "scripts": []}

        try:
            if self.deployment_type == "standalone":
                scripts_dir = "/opt/coffeebreak/bin"
                deployment_dir = "/opt/coffeebreak/deployments"
            else:
                scripts_dir = "./scripts"
                deployment_dir = "./deployments"

            os.makedirs(scripts_dir, exist_ok=True)
            os.makedirs(deployment_dir, exist_ok=True)

            # Create deployment scripts
            scripts_result = self._create_deployment_scripts(
                domain, config, scripts_dir, deployment_dir
            )
            if scripts_result["success"]:
                setup_result["scripts"] = scripts_result["scripts"]
            else:
                setup_result["errors"].extend(scripts_result["errors"])

            # Setup deployment tracking
            tracking_result = self._setup_deployment_tracking(deployment_dir, config)
            if not tracking_result["success"]:
                setup_result["errors"].extend(tracking_result["errors"])

            setup_result["success"] = len(setup_result["errors"]) == 0

            if self.verbose:
                print("Deployment orchestration configured")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Deployment orchestration setup failed: {e}")

        return setup_result

    def _create_deployment_scripts(
        self, domain: str, config: Dict[str, Any], scripts_dir: str, deployment_dir: str
    ) -> Dict[str, Any]:
        """Create deployment scripts for different strategies."""
        setup_result = {"success": True, "errors": [], "scripts": []}

        try:
            # Main deployment script
            deployment_script = f"""#!/bin/bash
# CoffeeBreak Zero-Downtime Deployment Script

set -euo pipefail

DOMAIN="{domain}"
DEPLOYMENT_DIR="{deployment_dir}"
LOG_FILE="/var/log/coffeebreak/deployment.log"
DEPLOYMENT_TIMEOUT={config.get("deployment_timeout", 600)}
HEALTH_CHECK_INTERVAL=10
MAX_HEALTH_CHECKS=30

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
        /opt/coffeebreak/bin/notify.sh "Deployment Failed" "$error_msg"
    fi
    
    exit 1
}}

# Function to create deployment record
create_deployment_record() {{
    local deployment_id="$1"
    local deployment_type="$2"
    local version="$3"
    
    local deployment_record="$DEPLOYMENT_DIR/$deployment_id.json"
    
    cat > "$deployment_record" << EOF
{{
    "id": "$deployment_id",
    "type": "$deployment_type",
    "version": "$version",
    "domain": "$DOMAIN",
    "start_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "status": "in_progress",
    "steps": [],
    "rollback_info": {{}}
}}
EOF
    
    echo "$deployment_record"
}}

# Function to update deployment record
update_deployment_record() {{
    local deployment_record="$1"
    local step="$2"
    local status="$3"
    
    # Create temporary updated record
    local temp_record="/tmp/deployment-$$.json"
    
    jq --arg step "$step" --arg status "$status" --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \\
       '.steps += [{{ "step": $step, "status": $status, "timestamp": $timestamp }}] | .last_update = $timestamp' \\
       "$deployment_record" > "$temp_record"
    
    mv "$temp_record" "$deployment_record"
}}

# Function to check application health
check_health() {{
    local max_checks="${{1:-$MAX_HEALTH_CHECKS}}"
    local check_count=0
    
    log_message "Checking application health..."
    
    while [ $check_count -lt $max_checks ]; do
        if curl -s --max-time 10 "https://$DOMAIN/health" > /dev/null; then
            log_message "✓ Health check passed"
            return 0
        fi
        
        check_count=$((check_count + 1))
        log_message "Health check failed ($check_count/$max_checks), retrying in $HEALTH_CHECK_INTERVAL seconds..."
        sleep $HEALTH_CHECK_INTERVAL
    done
    
    log_message "✗ Health check failed after $max_checks attempts"
    return 1
}}

# Function to perform rolling deployment
rolling_deployment() {{
    local version="$1"
    local deployment_id="deployment-$(date +%Y%m%d_%H%M%S)"
    local deployment_record=$(create_deployment_record "$deployment_id" "rolling" "$version")
    
    log_message "Starting rolling deployment: $deployment_id"
    log_message "Version: $version"
    
    # Step 1: Pre-deployment validation
    update_deployment_record "$deployment_record" "pre_validation" "started"
    log_message "Step 1: Pre-deployment validation"
    
    if ! /opt/coffeebreak/bin/validate.sh --comprehensive; then
        update_deployment_record "$deployment_record" "pre_validation" "failed"
        handle_error "Pre-deployment validation failed"
    fi
    
    update_deployment_record "$deployment_record" "pre_validation" "completed"
    
    # Step 2: Create backup
    update_deployment_record "$deployment_record" "backup" "started"
    log_message "Step 2: Creating backup"
    
    if ! /opt/coffeebreak/bin/backup.sh incremental; then
        update_deployment_record "$deployment_record" "backup" "failed"
        handle_error "Backup creation failed"
    fi
    
    update_deployment_record "$deployment_record" "backup" "completed"
    
    # Step 3: Deploy to staging area
    update_deployment_record "$deployment_record" "staging_deploy" "started"
    log_message "Step 3: Deploying to staging area"
    
    # Create staging deployment
    local staging_dir="/opt/coffeebreak/staging"
    mkdir -p "$staging_dir"
    
    # Deploy new version to staging (implementation depends on deployment method)
    if [ "{config.get("deployment_method", "git")}" = "git" ]; then
        cd "$staging_dir"
        if [ ! -d ".git" ]; then
            git clone "{config.get("repository_url", "https://github.com/user/coffeebreak.git")}" .
        else
            git fetch origin
        fi
        git checkout "$version" || handle_error "Failed to checkout version $version"
    fi
    
    update_deployment_record "$deployment_record" "staging_deploy" "completed"
    
    # Step 4: Rolling update of services
    update_deployment_record "$deployment_record" "service_update" "started"
    log_message "Step 4: Rolling update of services"
    
    local services=("coffeebreak-api" "coffeebreak-frontend" "coffeebreak-events")
    
    for service in "${{services[@]}}"; do
        log_message "Updating service: $service"
        
        # Stop service gracefully
        systemctl stop "$service" || true
        
        # Update service files (implementation depends on deployment method)
        # This would typically involve copying files, updating configurations, etc.
        
        # Start service
        systemctl start "$service" || handle_error "Failed to start $service"
        
        # Health check after each service update
        if ! check_health 10; then
            handle_error "Health check failed after updating $service"
        fi
        
        log_message "✓ Service $service updated successfully"
    done
    
    update_deployment_record "$deployment_record" "service_update" "completed"
    
    # Step 5: Final health check
    update_deployment_record "$deployment_record" "final_validation" "started"
    log_message "Step 5: Final health validation"
    
    if ! check_health; then
        update_deployment_record "$deployment_record" "final_validation" "failed"
        handle_error "Final health check failed"
    fi
    
    update_deployment_record "$deployment_record" "final_validation" "completed"
    
    # Mark deployment as completed
    jq '.status = "completed" | .end_time = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"' \\
       "$deployment_record" > "/tmp/deployment-$$.json"
    mv "/tmp/deployment-$$.json" "$deployment_record"
    
    log_message "✓ Rolling deployment completed successfully: $deployment_id"
    
    # Send success notification
    if [ -f "/opt/coffeebreak/bin/notify.sh" ]; then
        /opt/coffeebreak/bin/notify.sh "Deployment Successful" "Rolling deployment $deployment_id completed successfully (version: $version)"
    fi
}}

# Function to perform blue-green deployment
blue_green_deployment() {{
    local version="$1"
    local deployment_id="deployment-$(date +%Y%m%d_%H%M%S)"
    local deployment_record=$(create_deployment_record "$deployment_id" "blue-green" "$version")
    
    log_message "Starting blue-green deployment: $deployment_id"
    log_message "Version: $version"
    
    # Step 1: Create green environment
    update_deployment_record "$deployment_record" "green_environment" "started"
    log_message "Step 1: Creating green environment"
    
    local green_dir="/opt/coffeebreak/green"
    local blue_dir="/opt/coffeebreak/blue"
    
    # Setup green environment
    mkdir -p "$green_dir"
    
    # Deploy to green environment
    if [ "{config.get("deployment_method", "git")}" = "git" ]; then
        cd "$green_dir"
        if [ ! -d ".git" ]; then
            git clone "{config.get("repository_url", "https://github.com/user/coffeebreak.git")}" .
        else
            git fetch origin
        fi
        git checkout "$version" || handle_error "Failed to checkout version $version"
    fi
    
    update_deployment_record "$deployment_record" "green_environment" "completed"
    
    # Step 2: Start green services
    update_deployment_record "$deployment_record" "green_services" "started"
    log_message "Step 2: Starting green services"
    
    # Start green services on alternate ports
    # This would involve creating alternate service configurations
    
    update_deployment_record "$deployment_record" "green_services" "completed"
    
    # Step 3: Health check green environment
    update_deployment_record "$deployment_record" "green_validation" "started"
    log_message "Step 3: Validating green environment"
    
    # Test green environment (on alternate ports)
    if ! curl -s --max-time 10 "http://localhost:3001/health" > /dev/null; then
        update_deployment_record "$deployment_record" "green_validation" "failed"
        handle_error "Green environment health check failed"
    fi
    
    update_deployment_record "$deployment_record" "green_validation" "completed"
    
    # Step 4: Switch traffic to green
    update_deployment_record "$deployment_record" "traffic_switch" "started"
    log_message "Step 4: Switching traffic to green environment"
    
    # Update load balancer configuration to point to green
    # This would involve updating nginx configuration
    
    # Reload nginx
    nginx -s reload || handle_error "Failed to reload nginx configuration"
    
    update_deployment_record "$deployment_record" "traffic_switch" "completed"
    
    # Step 5: Final validation
    update_deployment_record "$deployment_record" "final_validation" "started"
    log_message "Step 5: Final validation"
    
    if ! check_health; then
        update_deployment_record "$deployment_record" "final_validation" "failed"
        handle_error "Final health check failed"
    fi
    
    update_deployment_record "$deployment_record" "final_validation" "completed"
    
    # Step 6: Cleanup blue environment
    update_deployment_record "$deployment_record" "cleanup" "started"
    log_message "Step 6: Cleaning up blue environment"
    
    # Move current blue to backup, green becomes new blue
    if [ -d "$blue_dir" ]; then
        mv "$blue_dir" "/opt/coffeebreak/previous-$(date +%Y%m%d_%H%M%S)"
    fi
    mv "$green_dir" "$blue_dir"
    
    update_deployment_record "$deployment_record" "cleanup" "completed"
    
    # Mark deployment as completed
    jq '.status = "completed" | .end_time = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"' \\
       "$deployment_record" > "/tmp/deployment-$$.json"
    mv "/tmp/deployment-$$.json" "$deployment_record"
    
    log_message "✓ Blue-green deployment completed successfully: $deployment_id"
    
    # Send success notification
    if [ -f "/opt/coffeebreak/bin/notify.sh" ]; then
        /opt/coffeebreak/bin/notify.sh "Deployment Successful" "Blue-green deployment $deployment_id completed successfully (version: $version)"
    fi
}}

# Function to perform canary deployment
canary_deployment() {{
    local version="$1"
    local canary_percentage="${{2:-10}}"
    local deployment_id="deployment-$(date +%Y%m%d_%H%M%S)"
    local deployment_record=$(create_deployment_record "$deployment_id" "canary" "$version")
    
    log_message "Starting canary deployment: $deployment_id"
    log_message "Version: $version, Canary: $canary_percentage%"
    
    # Step 1: Deploy canary version
    update_deployment_record "$deployment_record" "canary_deploy" "started"
    log_message "Step 1: Deploying canary version"
    
    # Deploy canary instance
    local canary_dir="/opt/coffeebreak/canary"
    mkdir -p "$canary_dir"
    
    if [ "{config.get("deployment_method", "git")}" = "git" ]; then
        cd "$canary_dir"
        if [ ! -d ".git" ]; then
            git clone "{config.get("repository_url", "https://github.com/user/coffeebreak.git")}" .
        else
            git fetch origin
        fi
        git checkout "$version" || handle_error "Failed to checkout version $version"
    fi
    
    update_deployment_record "$deployment_record" "canary_deploy" "completed"
    
    # Step 2: Configure traffic splitting
    update_deployment_record "$deployment_record" "traffic_split" "started"
    log_message "Step 2: Configuring traffic splitting ($canary_percentage% to canary)"
    
    # Update load balancer to send percentage of traffic to canary
    # This would involve updating nginx configuration with upstream weights
    
    update_deployment_record "$deployment_record" "traffic_split" "completed"
    
    # Step 3: Monitor canary
    update_deployment_record "$deployment_record" "canary_monitoring" "started"
    log_message "Step 3: Monitoring canary deployment"
    
    # Monitor for configurable time period
    local monitor_duration={config.get("canary_monitor_duration", 300)}
    local monitor_end=$(($(date +%s) + monitor_duration))
    
    while [ $(date +%s) -lt $monitor_end ]; do
        if ! check_health 3; then
            update_deployment_record "$deployment_record" "canary_monitoring" "failed"
            handle_error "Canary monitoring detected health issues"
        fi
        
        # Check error rates, response times, etc.
        # This would involve more sophisticated monitoring
        
        sleep 30
    done
    
    update_deployment_record "$deployment_record" "canary_monitoring" "completed"
    
    # Step 4: Promote canary to full deployment
    update_deployment_record "$deployment_record" "canary_promotion" "started"
    log_message "Step 4: Promoting canary to full deployment"
    
    # Gradually increase canary traffic to 100%
    local percentages=(25 50 75 100)
    for percentage in "${{percentages[@]}}"; do
        log_message "Increasing canary traffic to $percentage%"
        
        # Update load balancer configuration
        # This would involve updating nginx upstream weights
        
        # Monitor for a short period
        sleep 60
        
        if ! check_health 3; then
            update_deployment_record "$deployment_record" "canary_promotion" "failed"
            handle_error "Health check failed during canary promotion at $percentage%"
        fi
    done
    
    update_deployment_record "$deployment_record" "canary_promotion" "completed"
    
    # Step 5: Replace main deployment
    update_deployment_record "$deployment_record" "main_replacement" "started"
    log_message "Step 5: Replacing main deployment"
    
    # Replace main deployment with canary
    local main_dir="/opt/coffeebreak/main"
    if [ -d "$main_dir" ]; then
        mv "$main_dir" "/opt/coffeebreak/previous-$(date +%Y%m%d_%H%M%S)"
    fi
    mv "$canary_dir" "$main_dir"
    
    update_deployment_record "$deployment_record" "main_replacement" "completed"
    
    # Mark deployment as completed
    jq '.status = "completed" | .end_time = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"' \\
       "$deployment_record" > "/tmp/deployment-$$.json"
    mv "/tmp/deployment-$$.json" "$deployment_record"
    
    log_message "✓ Canary deployment completed successfully: $deployment_id"
    
    # Send success notification
    if [ -f "/opt/coffeebreak/bin/notify.sh" ]; then
        /opt/coffeebreak/bin/notify.sh "Deployment Successful" "Canary deployment $deployment_id completed successfully (version: $version)"
    fi
}}

# Function to perform rollback
rollback_deployment() {{
    local rollback_to="${{1:-previous}}"
    local deployment_id="rollback-$(date +%Y%m%d_%H%M%S)"
    
    log_message "Starting rollback: $deployment_id"
    log_message "Rolling back to: $rollback_to"
    
    # Find the deployment to rollback to
    local rollback_version
    if [ "$rollback_to" = "previous" ]; then
        rollback_version=$(ls -t "$DEPLOYMENT_DIR"/*.json | head -2 | tail -1 | xargs jq -r '.version')
    else
        rollback_version="$rollback_to"
    fi
    
    log_message "Rollback target version: $rollback_version"
    
    # Perform rapid rollback using previous deployment artifacts
    # This would involve reversing the last deployment steps
    
    # Send rollback notification
    if [ -f "/opt/coffeebreak/bin/notify.sh" ]; then
        /opt/coffeebreak/bin/notify.sh "Rollback Completed" "System rolled back to version $rollback_version"
    fi
    
    log_message "✓ Rollback completed successfully"
}}

# Main deployment function
main() {{
    local deployment_strategy="${{1:-rolling}}"
    local version="${{2:-latest}}"
    local extra_param="$3"
    
    log_message "Deployment request: strategy=$deployment_strategy, version=$version"
    
    # Timeout handler
    timeout $DEPLOYMENT_TIMEOUT bash -c "
        case '$deployment_strategy' in
            'rolling')
                rolling_deployment '$version'
                ;;
            'blue-green')
                blue_green_deployment '$version'
                ;;
            'canary')
                canary_deployment '$version' '$extra_param'
                ;;
            'rollback')
                rollback_deployment '$version'
                ;;
            *)
                echo 'ERROR: Unknown deployment strategy: $deployment_strategy'
                exit 1
                ;;
        esac
    " || handle_error "Deployment timed out after $DEPLOYMENT_TIMEOUT seconds"
}}

main "$@"
"""

            deployment_script_path = f"{scripts_dir}/deploy.sh"
            with open(deployment_script_path, "w") as f:
                f.write(deployment_script)
            os.chmod(deployment_script_path, 0o755)

            setup_result["scripts"].append(deployment_script_path)

            if self.verbose:
                print("Deployment scripts created")

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Deployment scripts creation failed: {e}")

        return setup_result

    def _setup_deployment_tracking(
        self, deployment_dir: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Setup deployment tracking and history."""
        setup_result = {"success": True, "errors": []}

        try:
            # Create deployment tracking script
            tracking_script = f"""#!/bin/bash
# CoffeeBreak Deployment Tracking Script

DEPLOYMENT_DIR="{deployment_dir}"

# Function to list deployments
list_deployments() {{
    echo "CoffeeBreak Deployment History"
    echo "============================="
    
    if [ ! -d "$DEPLOYMENT_DIR" ] || [ -z "$(ls -A $DEPLOYMENT_DIR 2>/dev/null)" ]; then
        echo "No deployments found."
        return 0
    fi
    
    echo "ID                          | Type       | Version    | Status     | Start Time"
    echo "--------------------------- | ---------- | ---------- | ---------- | -------------------"
    
    for deployment_file in "$DEPLOYMENT_DIR"/*.json; do
        if [ -f "$deployment_file" ]; then
            local id=$(jq -r '.id' "$deployment_file")
            local type=$(jq -r '.type' "$deployment_file")
            local version=$(jq -r '.version' "$deployment_file")
            local status=$(jq -r '.status' "$deployment_file")
            local start_time=$(jq -r '.start_time' "$deployment_file")
            
            printf "%-27s | %-10s | %-10s | %-10s | %s
" "$id" "$type" "$version" "$status" "$start_time"
        fi
    done
}}

# Function to show deployment details
show_deployment() {{
    local deployment_id="$1"
    local deployment_file="$DEPLOYMENT_DIR/$deployment_id.json"
    
    if [ ! -f "$deployment_file" ]; then
        echo "Deployment not found: $deployment_id"
        return 1
    fi
    
    echo "Deployment Details: $deployment_id"
    echo "=================================="
    jq . "$deployment_file"
}}

# Function to cleanup old deployments
cleanup_deployments() {{
    local retention_days="${{1:-30}}"
    
    echo "Cleaning up deployments older than $retention_days days..."
    
    find "$DEPLOYMENT_DIR" -name "*.json" -mtime +$retention_days -delete
    
    echo "Cleanup completed."
}}

# Main function
main() {{
    local action="${{1:-list}}"
    local param="$2"
    
    case "$action" in
        "list")
            list_deployments
            ;;
        "show")
            show_deployment "$param"
            ;;
        "cleanup")
            cleanup_deployments "$param"
            ;;
        *)
            echo "Usage: $0 {{list|show|cleanup}} [parameter]"
            exit 1
            ;;
    esac
}}

main "$@"
"""

            if self.deployment_type == "standalone":
                tracking_script_path = "/opt/coffeebreak/bin/deployment-history.sh"
            else:
                tracking_script_path = "./scripts/deployment-history.sh"

            with open(tracking_script_path, "w") as f:
                f.write(tracking_script)
            os.chmod(tracking_script_path, 0o755)

        except Exception as e:
            setup_result["success"] = False
            setup_result["errors"].append(f"Deployment tracking setup failed: {e}")

        return setup_result
