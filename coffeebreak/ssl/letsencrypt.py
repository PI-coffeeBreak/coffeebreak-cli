"""Let's Encrypt integration for automated SSL certificates."""

import os
import subprocess
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..utils.errors import SSLError
from .manager import SSLManager


class LetsEncryptManager:
    """Manages Let's Encrypt SSL certificates."""
    
    def __init__(self, 
                 email: str,
                 staging: bool = False,
                 verbose: bool = False):
        """
        Initialize Let's Encrypt manager.
        
        Args:
            email: Email address for Let's Encrypt registration
            staging: Use Let's Encrypt staging environment
            verbose: Enable verbose output
        """
        self.email = email
        self.staging = staging
        self.verbose = verbose
        self.ssl_manager = SSLManager(verbose=verbose)
        
        # Let's Encrypt directories
        self.config_dir = "/etc/letsencrypt"
        self.work_dir = "/var/lib/letsencrypt"
        self.logs_dir = "/var/log/letsencrypt"
    
    def check_certbot_available(self) -> bool:
        """Check if certbot is available."""
        try:
            result = subprocess.run(['certbot', '--version'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def install_certbot(self) -> bool:
        """Install certbot if not available."""
        try:
            if self.verbose:
                print("Installing certbot...")
            
            # Detect package manager and install
            if subprocess.run(['which', 'apt-get'], capture_output=True).returncode == 0:
                # Debian/Ubuntu
                commands = [
                    ['apt-get', 'update'],
                    ['apt-get', 'install', '-y', 'certbot']
                ]
            elif subprocess.run(['which', 'yum'], capture_output=True).returncode == 0:
                # CentOS/RHEL
                commands = [
                    ['yum', 'install', '-y', 'epel-release'],
                    ['yum', 'install', '-y', 'certbot']
                ]
            elif subprocess.run(['which', 'dnf'], capture_output=True).returncode == 0:
                # Fedora
                commands = [
                    ['dnf', 'install', '-y', 'certbot']
                ]
            else:
                raise SSLError("Unsupported package manager. Please install certbot manually.")
            
            for command in commands:
                result = subprocess.run(command, capture_output=True, text=True)
                if result.returncode != 0:
                    raise SSLError(f"Failed to install certbot: {result.stderr}")
            
            if self.verbose:
                print("Certbot installed successfully")
            
            return True
            
        except Exception as e:
            raise SSLError(f"Failed to install certbot: {e}")
    
    def obtain_certificate(self, 
                          domain: str,
                          challenge_method: str = "standalone",
                          webroot_path: Optional[str] = None,
                          dry_run: bool = False) -> Dict[str, Any]:
        """
        Obtain SSL certificate from Let's Encrypt.
        
        Args:
            domain: Domain name for certificate
            challenge_method: Challenge method (standalone, webroot, dns)
            webroot_path: Webroot path for webroot challenge
            dry_run: Perform dry run without obtaining certificate
            
        Returns:
            Dict[str, Any]: Certificate information
        """
        try:
            if self.verbose:
                print(f"Obtaining Let's Encrypt certificate for {domain}")
            
            # Ensure certbot is available
            if not self.check_certbot_available():
                self.install_certbot()
            
            # Build certbot command
            cmd = [
                'certbot', 'certonly',
                '--email', self.email,
                '--agree-tos',
                '--non-interactive',
                '--domains', domain
            ]
            
            # Add staging flag if requested
            if self.staging:
                cmd.append('--staging')
            
            # Add dry run flag if requested
            if dry_run:
                cmd.append('--dry-run')
            
            # Add challenge method
            if challenge_method == "standalone":
                cmd.append('--standalone')
            elif challenge_method == "webroot":
                if not webroot_path:
                    raise SSLError("Webroot path required for webroot challenge")
                cmd.extend(['--webroot', '--webroot-path', webroot_path])
            elif challenge_method == "dns":
                cmd.append('--manual')
                cmd.append('--preferred-challenges=dns')
            else:
                raise SSLError(f"Unsupported challenge method: {challenge_method}")
            
            # Execute certbot
            if self.verbose:
                print(f"Running: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                if dry_run:
                    return {
                        'success': True,
                        'dry_run': True,
                        'domain': domain,
                        'message': 'Dry run successful - certificate validation passed'
                    }
                
                # Get certificate paths
                cert_dir = f"{self.config_dir}/live/{domain}"
                
                return {
                    'success': True,
                    'domain': domain,
                    'cert_path': f"{cert_dir}/fullchain.pem",
                    'key_path': f"{cert_dir}/privkey.pem",
                    'chain_path': f"{cert_dir}/chain.pem",
                    'challenge_method': challenge_method,
                    'staging': self.staging,
                    'obtained_at': datetime.now().isoformat()
                }
            else:
                raise SSLError(f"Certbot failed: {result.stderr}")
            
        except Exception as e:
            if isinstance(e, SSLError):
                raise
            else:
                raise SSLError(f"Failed to obtain certificate: {e}")
    
    def renew_certificate(self, domain: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
        """
        Renew Let's Encrypt certificate(s).
        
        Args:
            domain: Specific domain to renew (None for all)
            dry_run: Perform dry run without renewing
            
        Returns:
            Dict[str, Any]: Renewal results
        """
        try:
            if self.verbose:
                if domain:
                    print(f"Renewing Let's Encrypt certificate for {domain}")
                else:
                    print("Renewing all Let's Encrypt certificates")
            
            # Build certbot command
            cmd = ['certbot', 'renew', '--non-interactive']
            
            if dry_run:
                cmd.append('--dry-run')
            
            if domain:
                cmd.extend(['--cert-name', domain])
            
            # Execute certbot
            if self.verbose:
                print(f"Running: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            return {
                'success': result.returncode == 0,
                'dry_run': dry_run,
                'domain': domain,
                'output': result.stdout,
                'error': result.stderr if result.returncode != 0 else None,
                'renewed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise SSLError(f"Failed to renew certificate: {e}")
    
    def list_certificates(self) -> List[Dict[str, Any]]:
        """
        List all Let's Encrypt certificates.
        
        Returns:
            List[Dict[str, Any]]: List of certificate information
        """
        try:
            cmd = ['certbot', 'certificates']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise SSLError(f"Failed to list certificates: {result.stderr}")
            
            certificates = []
            
            # Parse certbot output
            lines = result.stdout.split('\\n')
            current_cert = {}
            
            for line in lines:
                line = line.strip()
                if line.startswith('Certificate Name:'):
                    if current_cert:
                        certificates.append(current_cert)
                    current_cert = {'name': line.split(':', 1)[1].strip()}
                elif line.startswith('Domains:'):
                    current_cert['domains'] = [d.strip() for d in line.split(':', 1)[1].split()]
                elif line.startswith('Expiry Date:'):
                    expiry_str = line.split(':', 1)[1].strip()
                    current_cert['expiry_date'] = expiry_str
                elif line.startswith('Certificate Path:'):
                    current_cert['cert_path'] = line.split(':', 1)[1].strip()
                elif line.startswith('Private Key Path:'):
                    current_cert['key_path'] = line.split(':', 1)[1].strip()
            
            if current_cert:
                certificates.append(current_cert)
            
            # Add expiration analysis
            for cert in certificates:
                if 'cert_path' in cert and os.path.exists(cert['cert_path']):
                    try:
                        expiry_info = self.ssl_manager.check_certificate_expiration(cert['cert_path'])
                        cert.update(expiry_info)
                    except Exception:
                        pass
            
            return certificates
            
        except Exception as e:
            raise SSLError(f"Failed to list certificates: {e}")
    
    def revoke_certificate(self, domain: str, reason: str = "unspecified") -> bool:
        """
        Revoke Let's Encrypt certificate.
        
        Args:
            domain: Domain name
            reason: Revocation reason
            
        Returns:
            bool: True if revoked successfully
        """
        try:
            if self.verbose:
                print(f"Revoking Let's Encrypt certificate for {domain}")
            
            cmd = [
                'certbot', 'revoke',
                '--cert-name', domain,
                '--reason', reason,
                '--non-interactive'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                if self.verbose:
                    print(f"Certificate revoked for {domain}")
                return True
            else:
                raise SSLError(f"Failed to revoke certificate: {result.stderr}")
            
        except Exception as e:
            raise SSLError(f"Failed to revoke certificate: {e}")
    
    def setup_auto_renewal(self, renewal_frequency: str = "twice-daily") -> bool:
        """
        Set up automatic certificate renewal via cron.
        
        Args:
            renewal_frequency: Renewal frequency (twice-daily, daily, weekly)
            
        Returns:
            bool: True if setup successful
        """
        try:
            if self.verbose:
                print("Setting up automatic certificate renewal")
            
            # Define cron schedules
            schedules = {
                "twice-daily": "0 */12 * * *",
                "daily": "0 2 * * *",
                "weekly": "0 2 * * 0"
            }
            
            if renewal_frequency not in schedules:
                raise SSLError(f"Invalid renewal frequency: {renewal_frequency}")
            
            cron_schedule = schedules[renewal_frequency]
            
            # Create renewal command
            renewal_cmd = f"{cron_schedule} /usr/bin/certbot renew --quiet"
            
            # Get current crontab
            try:
                result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
                current_crontab = result.stdout if result.returncode == 0 else ""
            except subprocess.CalledProcessError:
                current_crontab = ""
            
            # Check if renewal is already configured
            if "certbot renew" in current_crontab:
                if self.verbose:
                    print("Certificate renewal already configured")
                return True
            
            # Add renewal to crontab
            new_crontab = current_crontab.rstrip() + "\\n" + renewal_cmd + "\\n"
            
            process = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, text=True)
            process.communicate(input=new_crontab)
            
            if process.returncode == 0:
                if self.verbose:
                    print(f"Automatic renewal configured ({renewal_frequency})")
                return True
            else:
                raise SSLError("Failed to update crontab")
            
        except Exception as e:
            raise SSLError(f"Failed to setup auto renewal: {e}")
    
    def test_renewal(self, domain: Optional[str] = None) -> bool:
        """
        Test certificate renewal process.
        
        Args:
            domain: Specific domain to test (None for all)
            
        Returns:
            bool: True if test successful
        """
        try:
            if self.verbose:
                print("Testing certificate renewal")
            
            result = self.renew_certificate(domain=domain, dry_run=True)
            
            if result['success']:
                if self.verbose:
                    print("Renewal test successful")
                return True
            else:
                if self.verbose:
                    print(f"Renewal test failed: {result.get('error', 'Unknown error')}")
                return False
            
        except Exception as e:
            if self.verbose:
                print(f"Renewal test failed: {e}")
            return False
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get Let's Encrypt account information.
        
        Returns:
            Dict[str, Any]: Account information
        """
        try:
            cmd = ['certbot', 'show_account']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Parse account info from output
                lines = result.stdout.split('\\n')
                account_info = {}
                
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        account_info[key.strip().lower().replace(' ', '_')] = value.strip()
                
                return account_info
            else:
                return {'error': result.stderr}
            
        except Exception as e:
            return {'error': str(e)}
    
    def cleanup_expired_certificates(self) -> Dict[str, Any]:
        """
        Clean up expired certificates.
        
        Returns:
            Dict[str, Any]: Cleanup results
        """
        try:
            if self.verbose:
                print("Cleaning up expired certificates")
            
            certificates = self.list_certificates()
            expired_certs = []
            
            for cert in certificates:
                if cert.get('expired', False):
                    expired_certs.append(cert['name'])
            
            cleanup_results = {
                'total_certificates': len(certificates),
                'expired_certificates': len(expired_certs),
                'cleaned_up': [],
                'errors': []
            }
            
            for cert_name in expired_certs:
                try:
                    cmd = ['certbot', 'delete', '--cert-name', cert_name, '--non-interactive']
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        cleanup_results['cleaned_up'].append(cert_name)
                        if self.verbose:
                            print(f"Cleaned up expired certificate: {cert_name}")
                    else:
                        error_msg = f"Failed to clean up {cert_name}: {result.stderr}"
                        cleanup_results['errors'].append(error_msg)
                        if self.verbose:
                            print(error_msg)
                
                except Exception as e:
                    error_msg = f"Error cleaning up {cert_name}: {e}"
                    cleanup_results['errors'].append(error_msg)
                    if self.verbose:
                        print(error_msg)
            
            return cleanup_results
            
        except Exception as e:
            raise SSLError(f"Failed to cleanup expired certificates: {e}")