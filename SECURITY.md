# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of DreamPlanner very seriously. If you discover a security vulnerability, please report it to us responsibly.

### How to Report

1. **Do not** create a public issue on GitHub
2. Send an email to **security@dreamplanner.app** with:
   - Detailed description of the vulnerability
   - Steps to reproduce the issue
   - Potential impact
   - Suggested fixes (if possible)

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 7 days
- **Resolution**: Depending on severity (critical: 7 days, high: 14 days, medium: 30 days)

### Scope

The following vulnerabilities are within our scope:

- SQL Injection
- Cross-Site Scripting (XSS)
- Cross-Site Request Forgery (CSRF)
- Broken Authentication/Authorization
- Sensitive Data Exposure
- Security Misconfiguration
- Components with Known Vulnerabilities

### Out of Scope

- Denial of Service (DoS) attacks
- Spam or social engineering
- Issues on systems we do not control

## Implemented Security Measures

### Authentication
- Tokens with short expiration
- Secure refresh tokens

### Authorization
- Ownership verification on all resources
- Role-based permissions
- Rate limiting per user and IP

### Data Protection
- Encryption in transit (HTTPS/TLS)
- User input sanitization
- Validation with Zod schemas
- Configured CORS protection

### Infrastructure
- Security headers (Helmet.js)
- CSRF protection
- Logging and monitoring with Sentry

## Best Practices for Contributors

1. Never commit secrets or credentials
2. Use environment variables
3. Validate all user input
4. Use parameterized queries (Prisma/Django ORM)
5. Follow the principle of least privilege

## Acknowledgments

We thank all security researchers who help us improve DreamPlanner.
