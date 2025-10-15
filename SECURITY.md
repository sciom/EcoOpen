# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to the project maintainers. You should receive a response within 48 hours.

### What to Include

Please include the following information in your report:

- Type of vulnerability
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability, including how an attacker might exploit it

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Release**: Depends on severity (critical issues within 7 days)

## Security Best Practices

### For Users

1. **Environment Variables**: Never commit `.env` files containing secrets
2. **API Keys**: Rotate API keys regularly
3. **Network Security**: Use HTTPS in production
4. **MongoDB**: Secure your MongoDB instance with authentication
5. **File Uploads**: Be aware of file size limits (default: 50MB)
6. **CORS**: Configure `CORS_ORIGINS` appropriately for your deployment

### For Developers

1. **Input Validation**: Always validate and sanitize user inputs
2. **Secrets Management**: Use environment variables for sensitive data
3. **Dependencies**: Keep dependencies updated
4. **Code Review**: All PRs require review before merging
5. **Static Analysis**: Use linters and type checkers
6. **Testing**: Write tests for security-critical code

## Known Security Considerations

### File Upload Handling
- Files are sanitized to prevent path traversal attacks
- File size limits are enforced
- Only PDF files are accepted
- Filenames are validated and sanitized

### API Security
- Input validation on all endpoints
- File size limits enforced
- Error messages don't expose sensitive information

### Database Security
- MongoDB connection should use authentication in production
- GridFS used for file storage with metadata validation

## Security Updates

Security updates will be released as patch versions and announced through:
- GitHub Security Advisories
- Release notes
- Project README

## Attribution

We appreciate responsible disclosure and will credit security researchers who report vulnerabilities (with their permission).
