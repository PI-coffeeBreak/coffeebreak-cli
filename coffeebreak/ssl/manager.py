"""SSL certificate management for production deployments."""

import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from ..utils.errors import SSLError


class SSLManager:
    """Manages SSL certificates for production deployments."""
    
    def __init__(self, verbose: bool = False):
        """Initialize SSL manager."""
        self.verbose = verbose
    
    def validate_certificate(self, cert_path: str, key_path: str, domain: str) -> Dict[str, Any]:
        """
        Validate SSL certificate.
        
        Args:
            cert_path: Path to certificate file
            key_path: Path to private key file
            domain: Domain to validate against
            
        Returns:
            Dict[str, Any]: Validation results
        """
        try:
            validation = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'cert_info': {},
                'expires_in_days': None
            }
            
            # Check if files exist
            if not os.path.exists(cert_path):
                validation['valid'] = False
                validation['errors'].append(f"Certificate file not found: {cert_path}")
                return validation
            
            if not os.path.exists(key_path):
                validation['valid'] = False
                validation['errors'].append(f"Private key file not found: {key_path}")
                return validation
            
            # Load certificate
            with open(cert_path, 'rb') as f:
                cert_data = f.read()
            
            try:
                cert = x509.load_pem_x509_certificate(cert_data)
            except Exception as e:
                validation['valid'] = False
                validation['errors'].append(f"Invalid certificate format: {e}")
                return validation
            
            # Extract certificate information
            subject = cert.subject
            issuer = cert.issuer
            
            validation['cert_info'] = {
                'subject': subject.rfc4514_string(),
                'issuer': issuer.rfc4514_string(),
                'serial_number': str(cert.serial_number),
                'not_valid_before': cert.not_valid_before.isoformat(),
                'not_valid_after': cert.not_valid_after.isoformat(),
                'signature_algorithm': cert.signature_algorithm_oid._name
            }
            
            # Check expiration
            now = datetime.now()
            expires_in = cert.not_valid_after - now
            validation['expires_in_days'] = expires_in.days
            
            if expires_in.days < 0:
                validation['valid'] = False
                validation['errors'].append("Certificate has expired")
            elif expires_in.days < 30:
                validation['warnings'].append(f"Certificate expires in {expires_in.days} days")
            
            # Check domain validation
            domain_valid = False
            
            # Check subject common name
            cn_attr = None
            for attribute in subject:
                if attribute.oid == NameOID.COMMON_NAME:
                    cn_attr = attribute.value
                    break
            
            if cn_attr and (cn_attr == domain or cn_attr == f"*.{domain}"):
                domain_valid = True
            
            # Check Subject Alternative Names (SAN)
            if not domain_valid:
                try:
                    san_ext = cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                    san_domains = [name.value for name in san_ext.value]
                    
                    if domain in san_domains or f"*.{domain}" in san_domains:
                        domain_valid = True
                    
                    validation['cert_info']['san_domains'] = san_domains
                    
                except x509.ExtensionNotFound:
                    pass
            
            if not domain_valid:
                validation['valid'] = False
                validation['errors'].append(f"Certificate is not valid for domain: {domain}")
            
            # Validate private key
            try:
                with open(key_path, 'rb') as f:
                    key_data = f.read()
                
                try:
                    private_key = serialization.load_pem_private_key(key_data, password=None)
                except Exception as e:
                    validation['valid'] = False
                    validation['errors'].append(f"Invalid private key format: {e}")
                    return validation
                
                # Check if private key matches certificate
                public_key = cert.public_key()
                private_public_key = private_key.public_key()
                
                # Compare public key numbers for RSA keys
                if isinstance(public_key, rsa.RSAPublicKey) and isinstance(private_public_key, rsa.RSAPublicKey):
                    if (public_key.public_numbers().n != private_public_key.public_numbers().n or
                        public_key.public_numbers().e != private_public_key.public_numbers().e):
                        validation['valid'] = False
                        validation['errors'].append("Private key does not match certificate")
                
            except Exception as e:
                validation['valid'] = False
                validation['errors'].append(f"Error validating private key: {e}")
            
            return validation
            
        except Exception as e:
            raise SSLError(f"Failed to validate certificate: {e}")
    
    def generate_self_signed_certificate(self, 
                                       domain: str, 
                                       output_dir: str,
                                       key_size: int = 2048,
                                       validity_days: int = 365) -> Dict[str, str]:
        """
        Generate self-signed certificate for development/testing.
        
        Args:
            domain: Domain name for the certificate
            output_dir: Directory to save certificate files
            key_size: RSA key size
            validity_days: Certificate validity period in days
            
        Returns:
            Dict[str, str]: Paths to generated files
        """
        try:
            if self.verbose:
                print(f"Generating self-signed certificate for {domain}")
            
            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size
            )
            
            # Generate certificate
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "CoffeeBreak"),
                x509.NameAttribute(NameOID.COMMON_NAME, domain),
            ])
            
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.utcnow()
            ).not_valid_after(
                datetime.utcnow() + timedelta(days=validity_days)
            ).add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName(domain),
                ]),
                critical=False,
            ).sign(private_key, hashes.SHA256())
            
            # Save private key
            key_path = output_path / "privkey.pem"
            with open(key_path, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            os.chmod(key_path, 0o600)
            
            # Save certificate
            cert_path = output_path / "fullchain.pem"
            with open(cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            
            # Create chain file (same as cert for self-signed)
            chain_path = output_path / "chain.pem"
            shutil.copy2(cert_path, chain_path)
            
            if self.verbose:
                print(f"Self-signed certificate generated for {domain}")
                print(f"Certificate: {cert_path}")
                print(f"Private key: {key_path}")
            
            return {
                'cert_path': str(cert_path),
                'key_path': str(key_path),
                'chain_path': str(chain_path),
                'domain': domain,
                'type': 'self-signed',
                'validity_days': validity_days
            }
            
        except Exception as e:
            raise SSLError(f"Failed to generate self-signed certificate: {e}")
    
    def check_certificate_expiration(self, cert_path: str) -> Dict[str, Any]:
        """
        Check certificate expiration status.
        
        Args:
            cert_path: Path to certificate file
            
        Returns:
            Dict[str, Any]: Expiration information
        """
        try:
            if not os.path.exists(cert_path):
                raise SSLError(f"Certificate file not found: {cert_path}")
            
            # Load certificate
            with open(cert_path, 'rb') as f:
                cert_data = f.read()
            
            cert = x509.load_pem_x509_certificate(cert_data)
            
            now = datetime.now()
            expires_at = cert.not_valid_after
            expires_in = expires_at - now
            
            status = "valid"
            if expires_in.days < 0:
                status = "expired"
            elif expires_in.days < 30:
                status = "expiring_soon"
            
            return {
                'status': status,
                'expires_at': expires_at.isoformat(),
                'expires_in_days': expires_in.days,
                'expired': expires_in.days < 0,
                'expiring_soon': 0 <= expires_in.days < 30
            }
            
        except Exception as e:
            raise SSLError(f"Failed to check certificate expiration: {e}")
    
    def backup_certificates(self, 
                           cert_dir: str, 
                           backup_dir: str,
                           domain: str) -> str:
        """
        Create backup of SSL certificates.
        
        Args:
            cert_dir: Directory containing certificates
            backup_dir: Directory to store backup
            domain: Domain name
            
        Returns:
            str: Path to backup file
        """
        try:
            if self.verbose:
                print(f"Backing up SSL certificates for {domain}")
            
            # Create backup directory
            backup_path = Path(backup_dir)
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_path / f"ssl_backup_{domain}_{timestamp}.tar.gz"
            
            # Create tar archive
            import tarfile
            with tarfile.open(backup_file, 'w:gz') as tar:
                tar.add(cert_dir, arcname=f"ssl_{domain}")
            
            # Set secure permissions
            os.chmod(backup_file, 0o600)
            
            if self.verbose:
                print(f"SSL certificates backed up to: {backup_file}")
            
            return str(backup_file)
            
        except Exception as e:
            raise SSLError(f"Failed to backup certificates: {e}")
    
    def install_certificate(self, 
                           cert_data: str,
                           key_data: str,
                           chain_data: Optional[str],
                           domain: str,
                           install_dir: str) -> Dict[str, str]:
        """
        Install SSL certificate files.
        
        Args:
            cert_data: Certificate content
            key_data: Private key content
            chain_data: Chain certificate content (optional)
            domain: Domain name
            install_dir: Installation directory
            
        Returns:
            Dict[str, str]: Paths to installed files
        """
        try:
            if self.verbose:
                print(f"Installing SSL certificate for {domain}")
            
            # Create installation directory
            install_path = Path(install_dir) / domain
            install_path.mkdir(parents=True, exist_ok=True)
            
            # Install certificate
            cert_path = install_path / "fullchain.pem"
            with open(cert_path, 'w') as f:
                f.write(cert_data)
            os.chmod(cert_path, 0o644)
            
            # Install private key
            key_path = install_path / "privkey.pem"
            with open(key_path, 'w') as f:
                f.write(key_data)
            os.chmod(key_path, 0o600)
            
            # Install chain certificate
            chain_path = install_path / "chain.pem"
            if chain_data:
                with open(chain_path, 'w') as f:
                    f.write(chain_data)
            else:
                # Use certificate as chain if no separate chain provided
                shutil.copy2(cert_path, chain_path)
            os.chmod(chain_path, 0o644)
            
            if self.verbose:
                print(f"SSL certificate installed for {domain}")
                print(f"Certificate: {cert_path}")
                print(f"Private key: {key_path}")
                print(f"Chain: {chain_path}")
            
            return {
                'cert_path': str(cert_path),
                'key_path': str(key_path),
                'chain_path': str(chain_path),
                'domain': domain
            }
            
        except Exception as e:
            raise SSLError(f"Failed to install certificate: {e}")
    
    def get_certificate_info(self, cert_path: str) -> Dict[str, Any]:
        """
        Get detailed certificate information.
        
        Args:
            cert_path: Path to certificate file
            
        Returns:
            Dict[str, Any]: Certificate information
        """
        try:
            if not os.path.exists(cert_path):
                raise SSLError(f"Certificate file not found: {cert_path}")
            
            # Load certificate
            with open(cert_path, 'rb') as f:
                cert_data = f.read()
            
            cert = x509.load_pem_x509_certificate(cert_data)
            
            # Extract basic information
            subject = cert.subject
            issuer = cert.issuer
            
            info = {
                'subject': {},
                'issuer': {},
                'serial_number': str(cert.serial_number),
                'not_valid_before': cert.not_valid_before.isoformat(),
                'not_valid_after': cert.not_valid_after.isoformat(),
                'signature_algorithm': cert.signature_algorithm_oid._name,
                'public_key_algorithm': cert.public_key().__class__.__name__,
                'extensions': []
            }
            
            # Parse subject
            for attribute in subject:
                name = attribute.oid._name
                info['subject'][name] = attribute.value
            
            # Parse issuer
            for attribute in issuer:
                name = attribute.oid._name
                info['issuer'][name] = attribute.value
            
            # Parse extensions
            for extension in cert.extensions:
                ext_info = {
                    'oid': extension.oid._name,
                    'critical': extension.critical
                }
                
                # Handle specific extensions
                if extension.oid == x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME:
                    ext_info['value'] = [name.value for name in extension.value]
                elif extension.oid == x509.oid.ExtensionOID.KEY_USAGE:
                    ext_info['value'] = {
                        'digital_signature': extension.value.digital_signature,
                        'key_encipherment': extension.value.key_encipherment,
                        'key_agreement': getattr(extension.value, 'key_agreement', False)
                    }
                else:
                    ext_info['value'] = str(extension.value)
                
                info['extensions'].append(ext_info)
            
            # Calculate expiration status
            now = datetime.now()
            expires_in = cert.not_valid_after - now
            info['expires_in_days'] = expires_in.days
            info['expired'] = expires_in.days < 0
            info['expiring_soon'] = 0 <= expires_in.days < 30
            
            return info
            
        except Exception as e:
            raise SSLError(f"Failed to get certificate info: {e}")