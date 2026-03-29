# Security Implementation

## Overview
This document summarizes the security measures implemented in the Embrace AI Product Lab system to protect against common threats and ensure secure operation.

## 1. Sensitive Data Encryption

### Master Key System
- **Master Key Location**: `~/.ai-product-lab/master.key` (600 permissions)
- **Environment Variable**: `AI_MASTER_KEY` (base64 encoded 32-byte key)
- **Encryption Algorithm**: AES-256-CBC with PKCS7 padding

### Encrypted Environment Variables
Sensitive environment variables are automatically encrypted/decrypted using the `secure_config` module:

- `DEEPSEEK_API_KEY_ENC`
- `FEISHU_APP_SECRET_ENC` 
- `FEISHU_ENCRYPT_KEY_ENC`
- `FEISHU_VERIFICATION_TOKEN_ENC`
- `NGROK_AUTHTOKEN_ENC`
- `MOONSHOT_API_KEY_ENC`

### Usage in Code
```python
from app.secure_config import get_secret

# Automatically decrypts if _ENC suffix exists
api_key = get_secret("DEEPSEEK_API_KEY")
```

### Migration Tool
```bash
# Generate new master key
python -c "from app.secure_config import init_master_key; init_master_key()"

# Encrypt existing .env file
python -c "from app.secure_config import migrate_env_file; migrate_env_file('.env', '.env.encrypted')"
```

## 2. Feishu Webhook Security

### Signature Verification
All Feishu webhook requests (`/feishu/webhook*`) are validated using:
1. **Timestamp validation** (prevent replay attacks)
2. **Nonce validation** (prevent replay attacks)
3. **HMAC-SHA256 signature** verification using Feishu Verification Token or Encrypt Key

### Encryption Support
- Supports both encrypted and unencrypted Feishu payloads
- Automatic decryption using Feishu Encrypt Key
- Graceful fallback for unencrypted messages

### Security Rejection
- Invalid signatures return HTTP 403
- URL verification (`challenge`) bypasses signature check

## 3. Rate Limiting

### Implementation
- Uses `slowapi` with in-memory storage (extendable to Redis)
- IP-based rate limiting via `get_remote_address`

### Rate Limits
| Endpoint | Limit | Purpose |
|----------|-------|---------|
| `/feishu/webhook*` | 30/minute | Prevent webhook spam |
| `/opencode/tasks` (POST) | 10/minute | Limit task creation |
| `/opencode/tasks/{id}/abort` | 10/minute | Limit abort operations |
| `/opencode/tasks/{id}/stream` | 30/minute | Limit SSE connections |
| Task management (GET) | 60/minute | Prevent data scraping |
| Configuration endpoints | 30/minute | Limit info disclosure |

### Exempt Endpoints
- `/` (root) - No limit
- `/health` - No limit

## 4. Input Validation & Sanitization

### Feishu Payload Validation
- Schema validation for v1/v2 Feishu formats
- JSON parsing with error handling
- Content length limits for message processing

### Task Input Validation
- Message length limits enforced
- Task ID validation (format, existence)

## 5. Security Monitoring & Logging

### Security Events Logged
- Failed signature verification attempts
- Rate limit violations
- Decryption failures
- Authentication failures (if enabled)

### Log Locations
- Application logs (stdout)
- Security-specific events tagged with `[Security]`

## 6. Network Security

### CORS Configuration
- Restricted origins via `ALLOWED_ORIGINS` environment variable
- Default: `http://localhost:3000,http://127.0.0.1:3000`

### TLS/HTTPS
- **Required for production**: Use reverse proxy (nginx, Caddy) with TLS
- **Tunnel security**: Use ngrok with auth token or Cloudflare Tunnel

## 7. API Key Security

### Current Protection
- API keys encrypted at rest
- Keys loaded into memory only when needed
- No logging of key values

### Recommended Additional Measures
1. **Key rotation**: Regular rotation of Feishu and LLM API keys
2. **Scope limitation**: Use least-privilege keys where possible
3. **Monitoring**: Alert on unusual usage patterns

## 8. Pending Security Enhancements

### High Priority
- [ ] **Basic Authentication** for admin endpoints (X-API-Key header)
- [ ] **Request validation middleware** for all inputs
- [ ] **Security headers** (HSTS, CSP, X-Content-Type-Options)

### Medium Priority
- [ ] **Redis-backed rate limiting** for distributed deployment
- [ ] **Audit logging** to separate security log file
- [ ] **IP allowlisting** for admin endpoints

### Low Priority
- [ ] **JWT authentication** for user-facing features
- [ ] **Database encryption** for task storage
- [ ] **Dependency vulnerability scanning**

## 9. Incident Response

### Security Breach Checklist
1. **Immediate actions**:
   - Rotate all API keys (Feishu, LLM providers, ngrok)
   - Revoke and regenerate master key
   - Review access logs for suspicious activity
2. **Containment**:
   - Update firewall rules
   - Temporarily disable public endpoints
   - Enable enhanced logging
3. **Recovery**:
   - Deploy updated security patches
   - Restore from verified backups
   - Conduct security audit

## 10. Maintenance Procedures

### Regular Security Tasks
| Task | Frequency | Responsibility |
|------|-----------|----------------|
| Rotate master key | Quarterly | System Admin |
| Review access logs | Weekly | Security Team |
| Update dependencies | Monthly | DevOps |
| Security audit | Bi-annually | External Auditor |

### Emergency Contact
- **Primary**: System Administrator
- **Backup**: Security Team Lead
- **Vendor Contacts**: Feishu Support, LLM Provider Support

---

## Quick Start for New Deployment

1. **Generate master key**:
   ```bash
   python -c "from app.secure_config import init_master_key; init_master_key()"
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your values
   python -c "from app.secure_config import migrate_env_file; migrate_env_file('.env', '.env.encrypted')"
   mv .env.encrypted .env
   ```

3. **Configure Feishu**:
   - Enable encryption in Feishu developer console
   - Use the generated Encrypt Key and Verification Token
   - Configure webhook URL with HTTPS

4. **Deploy with TLS**:
   ```bash
   # Use reverse proxy with Let's Encrypt
   # Or use ngrok with auth token
   ```

5. **Monitor security**:
   ```bash
   # Check logs for security events
   tail -f logs/security.log
   ```

---

*Last Updated: $(date)*
*Security Version: 1.0*