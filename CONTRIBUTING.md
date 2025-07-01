# Contributing to Zulip Standup Bot

Thank you for your interest in contributing to the Zulip Standup Bot! This document outlines the process for contributing to this project.

## 🤝 How to Contribute

### Ways to Contribute

- **Bug Reports**: Report bugs or unexpected behavior
- **Feature Requests**: Suggest new features or improvements
- **Code Contributions**: Submit bug fixes or new features
- **Documentation**: Improve documentation and examples
- **Testing**: Help test the bot in different environments

### Before You Start

1. Check existing [issues](https://github.com/your-org/zulip-standup-bot/issues) to see if your bug/feature is already being discussed
2. For major changes, create an issue first to discuss the approach
3. Fork the repository and create a feature branch

## 🛠️ Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- A Zulip development environment (or access to a Zulip instance)

### Local Development

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/zulip-standup-bot.git
   cd zulip-standup-bot
   ```

2. **Create Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

4. **Setup Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your development settings
   ```

5. **Run Tests**
   ```bash
   python -m pytest
   ```

### Docker Development

```bash
# Build and run development environment
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Run tests in container
docker-compose -f docker-compose.dev.yml exec standup-bot python -m pytest
```

## 📋 Development Guidelines

### Code Style

This project follows these coding standards:

- **Black** for code formatting: `python -m black .`
- **isort** for import sorting: `python -m isort .`
- **mypy** for type checking: `python -m mypy .`
- **flake8** for linting: `python -m flake8 .`

### Pre-commit Setup

Install pre-commit hooks to automatically format code:

```bash
pip install pre-commit
pre-commit install
```

### Code Structure

- **Bot Logic**: Main bot functionality in `zulip_bots/zulip_bots/bots/standup/standup.py`
- **Database**: Database operations in `zulip_bots/zulip_bots/bots/standup/database.py`
- **Configuration**: Settings management in `zulip_bots/zulip_bots/bots/standup/config.py`
- **AI Integration**: AI summary features in `zulip_bots/zulip_bots/bots/standup/ai_summary.py`
- **Tests**: Test files in `zulip_bots/zulip_bots/bots/standup/test_*.py`

### Writing Tests

- Write tests for all new functionality
- Maintain or improve test coverage
- Use descriptive test names
- Mock external dependencies (Zulip API, OpenAI, database)

Example test structure:
```python
import pytest
from unittest.mock import Mock, patch
from zulip_bots.bots.standup.standup import StandupBotHandler

class TestStandupBot:
    def test_setup_command_creates_channel(self):
        # Arrange
        bot_handler = Mock()
        standup_bot = StandupBotHandler()
        
        # Act
        standup_bot.handle_message(message, bot_handler)
        
        # Assert
        assert expected_behavior
```

### Database Changes

- Use migration scripts for schema changes
- Ensure backward compatibility
- Test with both PostgreSQL and SQLite
- Document any new database requirements

### Documentation

- Update README.md for new features
- Add docstrings for new functions and classes
- Include examples for new commands
- Update configuration documentation

## 🔧 Testing

### Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest zulip_bots/zulip_bots/bots/standup/test_standup.py

# Run with coverage
python -m pytest --cov=zulip_bots.bots.standup

# Run with verbose output
python -m pytest -v
```

### Test Categories

- **Unit Tests**: Test individual functions and methods
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows
- **Database Tests**: Test database operations

### Test Environment

Create a `.env.test` file for test configuration:
```bash
ZULIP_EMAIL=test-bot@example.com
ZULIP_API_KEY=test_key
ZULIP_SITE=https://test.zulipchat.com
DATABASE_URL=sqlite:///test.db
LOG_LEVEL=DEBUG
```

## 📤 Submitting Changes

### Pull Request Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Write your code
   - Add tests
   - Update documentation
   - Ensure all tests pass

3. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

4. **Push Branch**
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Create Pull Request**
   - Use a clear, descriptive title
   - Include a detailed description
   - Reference any related issues
   - Add screenshots if applicable

### Commit Message Format

Follow conventional commit format:

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `style:` Code style changes
- `refactor:` Code refactoring
- `test:` Test additions or changes
- `chore:` Maintenance tasks

Examples:
```
feat: add timezone support for reminders
fix: resolve database connection timeout
docs: update installation instructions
test: add tests for AI summary generation
```

### Pull Request Checklist

- [ ] Code follows project style guidelines
- [ ] Tests pass locally
- [ ] New functionality includes tests
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
- [ ] Commit messages are clear and descriptive

## 🐛 Bug Reports

### Before Reporting

1. Check if the bug is already reported
2. Test with the latest version
3. Try to reproduce the issue consistently

### Bug Report Template

```markdown
**Bug Description**
A clear description of what the bug is.

**Steps to Reproduce**
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected Behavior**
What you expected to happen.

**Actual Behavior**
What actually happened.

**Environment**
- OS: [e.g. Ubuntu 20.04]
- Python version: [e.g. 3.9]
- Bot version: [e.g. 1.2.0]
- Zulip version: [e.g. 5.0]

**Additional Context**
Add any other context about the problem here.

**Logs**
```
Include relevant log outputs
```
```

## ✨ Feature Requests

### Feature Request Template

```markdown
**Feature Description**
A clear description of what you want to happen.

**Problem Statement**
What problem does this solve?

**Proposed Solution**
Describe the solution you'd like.

**Alternatives Considered**
Describe any alternative solutions you've considered.

**Additional Context**
Add any other context or screenshots about the feature request.
```

## 🚀 Release Process

### Versioning

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

- [ ] Update version in `setup.py`
- [ ] Update CHANGELOG.md
- [ ] Create release tag
- [ ] Update Docker images
- [ ] Announce release

## 📞 Getting Help

- **Issues**: [GitHub Issues](https://github.com/your-org/zulip-standup-bot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/zulip-standup-bot/discussions)
- **Documentation**: [Project Wiki](https://github.com/your-org/zulip-standup-bot/wiki)

## 📄 License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).

## 🙏 Recognition

Contributors will be recognized in:
- README.md contributors section
- Release notes
- Project documentation

Thank you for contributing to the Zulip Standup Bot! 🎉
