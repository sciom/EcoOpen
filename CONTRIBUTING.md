# Contributing to EcoOpen LLM

Thank you for your interest in contributing to EcoOpen LLM! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR-USERNAME/EcoOpen_LLM.git`
3. Create a new branch: `git checkout -b feature/your-feature-name`
4. Set up your development environment (see below)

## Development Environment Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- MongoDB 6+
- Git

### Python Setup
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### Frontend Setup
```bash
cd frontend
npm install
cd ..
```

### Configuration
```bash
cp .env.example .env
# Edit .env with your configuration
```

## Code Quality Standards

### Python Code Style
- Follow PEP 8 guidelines
- Use Black for formatting: `black app/ tests/`
- Use isort for import sorting: `isort app/ tests/`
- Maximum line length: 120 characters
- Use type hints where possible

### Linting
```bash
# Run flake8
flake8 app/ tests/

# Run mypy for type checking
mypy app/
```

### Testing
All new features and bug fixes should include tests.

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_validation.py

# Run tests matching a pattern
pytest -k "test_validate"
```

## Commit Guidelines

### Commit Message Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Example:
```
feat(api): add rate limiting to analyze endpoint

Add rate limiting middleware to prevent API abuse. Limit is set to
100 requests per hour per IP address.

Closes #123
```

## Pull Request Process

1. **Update documentation**: Ensure README.md and other docs are updated if needed
2. **Add tests**: All new features must have tests
3. **Run tests locally**: Ensure all tests pass before submitting
4. **Update CHANGELOG**: Add your changes to the unreleased section
5. **Create PR**: Submit a pull request with a clear description of changes

### PR Checklist
- [ ] Code follows project style guidelines
- [ ] Tests added/updated and passing
- [ ] Documentation updated
- [ ] Commit messages follow guidelines
- [ ] No merge conflicts
- [ ] CI/CD pipeline passes

## Code Review Process

1. At least one maintainer review is required
2. All CI checks must pass
3. Address reviewer feedback promptly
4. Once approved, a maintainer will merge your PR

## Reporting Issues

### Bug Reports
Include:
- Clear description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)
- Error messages and logs

### Feature Requests
Include:
- Clear description of the feature
- Use case and motivation
- Proposed implementation (optional)

## Security Issues

**DO NOT** open public issues for security vulnerabilities. Instead, email the maintainers directly.

## Questions?

Feel free to open a discussion or reach out to the maintainers.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
