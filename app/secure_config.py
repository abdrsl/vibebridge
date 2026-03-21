"""
Secure configuration management with optional encryption for sensitive values.

Usage:
1. Set a master key via environment variable: AI_MASTER_KEY or in ~/.ai-product-lab/master.key
2. Encrypt sensitive values using the encrypt_value() function
3. Store encrypted values in .env with prefix ENC_
4. Use get_secret() to automatically decrypt values

Example:
    Before: DEEPSEEK_API_KEY=sk-abc123
    After:  DEEPSEEK_API_KEY_ENC=ENC:gAAAAABm... (encrypted)

    In code: api_key = get_secret("DEEPSEEK_API_KEY")
"""

import os
import base64
import json
from typing import Optional, Any
from pathlib import Path
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import hashlib

# Constants
MASTER_KEY_ENV_VAR = "AI_MASTER_KEY"
MASTER_KEY_FILE = Path.home() / ".ai-product-lab" / "master.key"
ENCRYPTED_PREFIX = "ENC:"
DEFAULT_SENSITIVE_KEYS = [
    "DEEPSEEK_API_KEY",
    "MOONSHOT_API_KEY",
    "FEISHU_APP_SECRET",
    "FEISHU_ENCRYPT_KEY",
    "FEISHU_VERIFICATION_TOKEN",
    "NGROK_AUTHTOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "OPENROUTER_API_KEY",
    "LITELLM_MASTER_KEY",
    "POSTGRES_PASSWORD",
    "REDIS_PASSWORD",
    "QDRANT_API_KEY",
]


class SecureConfigError(Exception):
    """Secure configuration error."""

    pass


def _get_master_key() -> bytes:
    """Get master key from environment variable or file."""
    # Try environment variable first
    master_key = os.getenv(MASTER_KEY_ENV_VAR)
    if master_key:
        # Ensure it's 32 bytes for AES-256
        key_hash = hashlib.sha256(master_key.encode()).digest()
        return key_hash

    # Try key file
    if MASTER_KEY_FILE.exists():
        try:
            key_data = MASTER_KEY_FILE.read_bytes()
            # File can contain raw bytes or base64 encoded string
            if len(key_data) == 32:
                return key_data
            else:
                # Try to decode as base64
                try:
                    decoded = base64.b64decode(key_data)
                    if len(decoded) == 32:
                        return decoded
                    else:
                        # Hash to 32 bytes
                        return hashlib.sha256(decoded).digest()[:32]
                except:
                    # Hash the raw bytes
                    return hashlib.sha256(key_data).digest()[:32]
        except Exception as e:
            raise SecureConfigError(f"Failed to read master key file: {e}")

    # No master key found - in development, we can fall back to a default
    # but warn loudly. In production, this should fail.
    if os.getenv("APP_ENV") == "dev":
        print(f"⚠️  WARNING: No master key found. Using default development key.")
        print(f"   Set {MASTER_KEY_ENV_VAR} or create {MASTER_KEY_FILE}")
        # Generate deterministic key from string for development
        dev_key = "dev-master-key-insecure-change-in-production"
        return hashlib.sha256(dev_key.encode()).digest()

    raise SecureConfigError(
        f"Master key required. Set {MASTER_KEY_ENV_VAR} environment variable "
        f"or create {MASTER_KEY_FILE} with 32-byte key."
    )


def _create_cipher(key: bytes, iv: bytes) -> AES:
    """Create AES cipher in CBC mode."""
    return AES.new(key, AES.MODE_CBC, iv)


def encrypt_value(plaintext: str) -> str:
    """
    Encrypt a plaintext string.

    Returns:
        Base64 encoded string with format: ENC:<base64(iv + ciphertext)>
    """
    if not plaintext:
        return ""

    master_key = _get_master_key()
    iv = get_random_bytes(16)
    cipher = _create_cipher(master_key, iv)

    # Encrypt with PKCS7 padding
    padded_data = pad(plaintext.encode("utf-8"), AES.block_size)
    ciphertext = cipher.encrypt(padded_data)

    # Combine IV and ciphertext
    encrypted = iv + ciphertext
    encoded = base64.b64encode(encrypted).decode("utf-8")

    return f"{ENCRYPTED_PREFIX}{encoded}"


def decrypt_value(encrypted_str: str) -> str:
    """
    Decrypt an encrypted string.

    Args:
        encrypted_str: String with format ENC:<base64(iv + ciphertext)>

    Returns:
        Decrypted plaintext string
    """
    if not encrypted_str:
        return ""

    if not encrypted_str.startswith(ENCRYPTED_PREFIX):
        # Not encrypted, return as-is (for backwards compatibility)
        return encrypted_str

    encoded = encrypted_str[len(ENCRYPTED_PREFIX) :]

    try:
        encrypted = base64.b64decode(encoded)
    except Exception as e:
        raise SecureConfigError(f"Invalid base64 encoding: {e}")

    if len(encrypted) < 16:
        raise SecureConfigError("Encrypted data too short")

    iv = encrypted[:16]
    ciphertext = encrypted[16:]

    master_key = _get_master_key()
    cipher = _create_cipher(master_key, iv)

    try:
        decrypted = cipher.decrypt(ciphertext)
        plaintext = unpad(decrypted, AES.block_size)
        return plaintext.decode("utf-8")
    except Exception as e:
        raise SecureConfigError(f"Decryption failed: {e}")


def get_secret(key_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a secret value, automatically decrypting if encrypted.

    Checks for encrypted version first (key_name + "_ENC"), then falls back
    to plain version. Returns None if neither exists.
    """
    # Try encrypted version first
    enc_key = f"{key_name}_ENC"
    enc_value = os.getenv(enc_key)

    if enc_value:
        try:
            return decrypt_value(enc_value)
        except SecureConfigError as e:
            print(f"⚠️  Failed to decrypt {key_name}: {e}")
            # Fall back to plain version

    # Try plain version
    plain_value = os.getenv(key_name)
    if plain_value:
        # Warn if sensitive key is stored in plaintext
        if key_name in DEFAULT_SENSITIVE_KEYS and os.getenv("APP_ENV") != "test":
            print(
                f"⚠️  WARNING: {key_name} is stored in plaintext. Consider encrypting it."
            )
        return plain_value

    return default


def get_config(key_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get configuration value (non-sensitive). Same as os.getenv but with logging.
    """
    value = os.getenv(key_name, default)
    return value


def migrate_env_file(input_path: str = ".env", output_path: str = ".env.encrypted"):
    """
    Migrate .env file to use encrypted values for sensitive keys.

    Creates a new file with encrypted values for sensitive keys.
    Original keys are commented out and new _ENC keys are added.
    """
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    lines = input_file.read_text().splitlines()
    output_lines = []

    for line in lines:
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            output_lines.append(line)
            continue

        # Parse key=value
        if "=" not in line:
            output_lines.append(line)
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        # Remove quotes if present
        if value.startswith(('"', "'")) and value.endswith(('"', "'")):
            value = value[1:-1]

        # Check if this is a sensitive key
        if key in DEFAULT_SENSITIVE_KEYS and value:
            # Encrypt the value
            try:
                encrypted = encrypt_value(value)
                # Comment out original line
                output_lines.append(f"# {line}")
                # Add encrypted version
                output_lines.append(f"{key}_ENC={encrypted}")
                print(f"✓ Encrypted {key}")
            except Exception as e:
                print(f"✗ Failed to encrypt {key}: {e}")
                output_lines.append(line)
        else:
            output_lines.append(line)

    # Write output file
    output_file = Path(output_path)
    output_file.write_text("\n".join(output_lines))
    print(f"\n✅ Created encrypted environment file: {output_path}")
    print(f"   Review the file and replace your original .env if ready.")
    print(f"   Don't forget to set your master key!")
    print(f"   Export: export {MASTER_KEY_ENV_VAR}=$(cat ~/.ai-product-lab/master.key)")


def init_master_key(key_path: Optional[str] = None) -> str:
    """
    Initialize a new random master key.

    Args:
        key_path: Path to save the key (default: ~/.ai-product-lab/master.key)

    Returns:
        Base64 encoded key (for display only)
    """
    if key_path:
        key_file = Path(key_path)
    else:
        key_file = MASTER_KEY_FILE

    # Create parent directory if needed
    key_file.parent.mkdir(parents=True, exist_ok=True)

    # Generate random 32-byte key
    random_key = get_random_bytes(32)

    # Save as base64
    encoded_key = base64.b64encode(random_key).decode("utf-8")
    key_file.write_text(encoded_key)

    # Set restrictive permissions (owner read/write only)
    key_file.chmod(0o600)

    print(f"✅ Generated new master key at: {key_file}")
    print(f"   Key (base64): {encoded_key}")
    print(f"\n   To use immediately: export {MASTER_KEY_ENV_VAR}='{encoded_key}'")
    print(f"   Or ensure the key file is at: {MASTER_KEY_FILE}")

    return encoded_key


# Convenience functions for common secrets
def get_deepseek_key() -> Optional[str]:
    return get_secret("DEEPSEEK_API_KEY")


def get_feishu_app_secret() -> Optional[str]:
    return get_secret("FEISHU_APP_SECRET")


def get_feishu_encrypt_key() -> Optional[str]:
    return get_secret("FEISHU_ENCRYPT_KEY")


def get_feishu_verification_token() -> Optional[str]:
    return get_secret("FEISHU_VERIFICATION_TOKEN")


def get_ngrok_token() -> Optional[str]:
    return get_secret("NGROK_AUTHTOKEN")
