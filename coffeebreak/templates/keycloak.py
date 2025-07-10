"""Keycloak configuration templates."""


def get_dockerfile_content() -> str:
    """Get Keycloak Dockerfile content."""
    return """# 🔹 Step 1: Build Keycloak with custom settings
FROM quay.io/keycloak/keycloak:26.1.4 AS builder

# Enable health and metrics support
ENV KC_HEALTH_ENABLED=true
ENV KC_METRICS_ENABLED=true
ENV KC_DB=postgres
ENV PROXY_ADDRESS_FORWARDING=true
ENV KC_HTTP_ENABLED=true
ENV KC_HTTPS=true
ENV KC_PROXY_HEADERS=forwarded

WORKDIR /opt/keycloak

# Copy custom themes into the Keycloak themes directory
COPY ./themes/ /opt/keycloak/themes/

# Copy custom providers into the Keycloak providers directory
COPY ./providers/ /opt/keycloak/providers/

# Generate a self-signed certificate for HTTPS (Development use only!)
RUN keytool -genkeypair -storepass password -storetype PKCS12 \\
    -keyalg RSA -keysize 2048 \\
    -dname "CN=server" \\
    -alias server \\
    -ext "SAN:c=DNS:localhost,IP:127.0.0.1" \\
    -keystore conf/server.keystore

# Build Keycloak with the applied configurations
RUN /opt/keycloak/bin/kc.sh build

# Ensure the /exports directory exists and contains the necessary files
RUN mkdir -p /opt/keycloak/data/import && echo "Ensure this directory contains the necessary files"

# 🔹 Step 2: Create the final image
FROM quay.io/keycloak/keycloak:26.1.4

# Copy the built Keycloak instance with themes
COPY --from=builder /opt/keycloak/ /opt/keycloak/

# Copy themes again to ensure they are available in the final image
COPY ./themes/ /opt/keycloak/themes/

COPY ./exports/ /opt/keycloak/data/import/

# Set database environment variables (Docker Compose will override them)
ENV KC_DB=postgres
ENV KC_DB_URL=jdbc:postgresql://keycloak-db:5432/keycloak
ENV KC_DB_USERNAME=keycloak
ENV KC_DB_PASSWORD=keycloakpassword
ENV KC_HEALTH_ENABLED=true
ENV KC_METRICS_ENABLED=true

# Set Keycloak hostname (ensure this matches your domain if using HTTPS)
ENV KC_HOSTNAME=localhost

ENV KEYCLOAK_IMPORT=/opt/keycloak/data/import

# Expose Keycloak's default port
EXPOSE 8443
EXPOSE 9000

# Start Keycloak in PRODUCTION mode with development theme caching disabled
ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start", "--optimized", "--proxy-headers", "forwarded", "--import-realm"]
"""


def get_realm_config() -> dict:
    """Get Keycloak realm configuration."""
    return {
        "id": "coffeebreak",
        "realm": "coffeebreak",
        "enabled": True,
        "sslRequired": "external",
        "registrationAllowed": False,
        "loginWithEmailAllowed": True,
        "duplicateEmailsAllowed": False,
        "resetPasswordAllowed": True,
        "editUsernameAllowed": False,
        "bruteForceProtected": True,
        "clients": [
            {
                "id": "fastapi-client",
                "clientId": "fastapi-client",
                "enabled": True,
                "clientAuthenticatorType": "client-secret",
                "secret": "your-client-secret-here",
                "redirectUris": ["*"],
                "webOrigins": ["*"],
                "protocol": "openid-connect",
                "attributes": {
                    "saml.assertion.signature": "false",
                    "saml.force.post.binding": "false",
                    "saml.multivalued.roles": "false",
                    "saml.encrypt": "false",
                    "saml.server.signature": "false",
                    "saml.server.signature.keyinfo.ext": "false",
                    "exclude.session.state.from.auth.response": "false",
                    "saml_force_name_id_format": "false",
                    "saml.client.signature": "false",
                    "tls.client.certificate.bound.access.tokens": "false",
                    "saml.authnstatement": "false",
                    "display.on.consent.screen": "false",
                    "saml.onetimeuse.condition": "false",
                },
            },
            {
                "id": "coffeebreak-client",
                "clientId": "coffeebreak-client",
                "enabled": True,
                "publicClient": True,
                "redirectUris": ["*"],
                "webOrigins": ["*"],
                "protocol": "openid-connect",
            },
        ],
        "users": [
            {
                "id": "admin",
                "username": "admin",
                "enabled": True,
                "email": "admin@coffeebreak.local",
                "emailVerified": True,
                "credentials": [
                    {"type": "password", "value": "admin123", "temporary": False}
                ],
            }
        ],
    }


def get_theme_files() -> dict:
    """Get Keycloak theme files as a dictionary of filename -> content."""
    return {
        "theme.properties": """parent=base
import=common/keycloak

styles=css/styles.css
scripts=js/script.js

meta=viewport==width=device-width,initial-scale=1

kcHtmlClass=login-pf
kcLoginClass=login-pf-page
kcBodyClass=login-pf-page
""",
        "resources/css/styles.css": """/* CoffeeBreak Custom Login Theme */
.login-pf-page {
    background: linear-gradient(135deg, #8B4513, #D2691E);
}

.login-pf-page .login-pf-brand img {
    max-height: 60px;
}

.card-pf {
    background: rgba(255, 255, 255, 0.95);
    border-radius: 10px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.btn-primary {
    background-color: #8B4513;
    border-color: #8B4513;
}

.btn-primary:hover {
    background-color: #A0522D;
    border-color: #A0522D;
}
""",
        "resources/js/script.js": """// CoffeeBreak Custom Login Scripts
console.log("CoffeeBreak Keycloak Theme Loaded");
""",
    }
