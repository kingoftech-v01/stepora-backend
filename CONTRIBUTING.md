# Contributing to DreamPlanner

First off, thank you for considering contributing to DreamPlanner! It's people like you that make DreamPlanner such a great tool for helping people achieve their dreams.

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates. When you create a bug report, include as many details as possible:

**Bug Report Template**:
- **Description**: Clear description of the bug
- **Steps to Reproduce**: Step-by-step instructions
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Environment**: OS, Python version, Django version
- **Screenshots**: If applicable
- **Error Logs**: Full error messages

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, include:

- **Clear title and description**
- **Use case**: Why this feature would be useful
- **Proposed solution**: How you envision this working
- **Alternatives**: Other solutions you've considered
- **Additional context**: Mockups, examples, etc.

### Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Make your changes** following our coding standards
3. **Add tests** if you've added code
4. **Update documentation** if needed
5. **Ensure tests pass** (`make test`)
6. **Create a Pull Request**

## Development Setup

### Backend (Django)

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/dreamplanner.git
cd dreamplanner

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements/development.txt

# Setup environment
cp .env.example .env
# Edit .env with your credentials

# Run migrations
python manage.py migrate

# Run tests
pytest

# Start development server
python manage.py runserver
```

### Using Docker (Recommended)

```bash
make build
make up
make migrate
make test
```

## Coding Standards

### Python/Django Backend

#### Style Guide
- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use [Black](https://black.readthedocs.io/) for code formatting
- Use [isort](https://pycqa.github.io/isort/) for import sorting
- Use [flake8](https://flake8.pycqa.org/) for linting

#### Code Quality
```bash
# Format code
black apps core integrations

# Sort imports
isort apps core integrations

# Lint
flake8 apps core integrations

# Or use our Makefile
make format
make lint
```

#### Django Best Practices
- Use class-based views (ViewSets for DRF)
- Always add migrations for model changes
- Use Django ORM (no raw SQL unless absolutely necessary)
- Add docstrings to all classes and methods
- Use meaningful variable names
- Keep views thin, move logic to services
- Always use transactions for multi-model operations

#### Example
```python
class DreamViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user dreams.

    Provides CRUD operations plus AI-powered features like
    plan generation and dream analysis.
    """
    permission_classes = [IsAuthenticated, IsOwner]
    serializer_class = DreamSerializer

    def get_queryset(self):
        """Return dreams for current user only."""
        return Dream.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def generate_plan(self, request, pk=None):
        """Generate AI-powered plan for dream."""
        dream = self.get_object()
        service = OpenAIService()
        plan = service.generate_plan(dream, request.user)
        # ... rest of implementation
```

## Testing

### Backend Testing

**Required**:
- Write tests for all new features
- Maintain 84% code coverage
- Test happy path AND error cases
- Use fixtures for test data

**Test Structure**:
```python
class TestDreamModel:
    """Test Dream model."""

    def test_create_dream(self, db, user):
        """Test creating a dream."""
        dream = Dream.objects.create(
            user=user,
            title='Learn Django',
            description='Master Django framework'
        )
        assert dream.title == 'Learn Django'
        assert dream.user == user
```

**Running Tests**:
```bash
# All tests
make test

# With coverage
make test-cov

# Specific app
pytest apps/users/tests.py

# Specific test
pytest apps/users/tests.py::TestUserModel::test_create_user -v
```

## Commit Messages

### Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, no logic change)
- **refactor**: Code refactoring
- **test**: Adding or updating tests
- **chore**: Maintenance tasks

### Examples
```
feat(dreams): add 2-minute start micro-actions

Implement AI-generated micro-actions to help users
overcome procrastination by starting with very small tasks.

Closes #123
```

```
fix(notifications): respect DND hours

Fixed bug where notifications were sent during
Do Not Disturb hours.

Fixes #456
```

### Rules
- Use present tense ("add feature" not "added feature")
- Use imperative mood ("move cursor to..." not "moves cursor to...")
- Limit first line to 72 characters
- Reference issues and PRs when applicable
- Add breaking changes in footer with `BREAKING CHANGE:`

## Pull Request Process

### Before Submitting

1. **Update your branch** with latest main
   ```bash
   git fetch origin
   git rebase origin/main
   ```

2. **Run all tests** and ensure they pass
   ```bash
   make test
   ```

3. **Run linters** and fix issues
   ```bash
   make lint
   make format
   ```

4. **Update documentation** if needed
   - README.md
   - API documentation
   - Inline code comments

5. **Update CHANGELOG.md** (if applicable)

### PR Template

Use our [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md) which includes:
- Description of changes
- Type of change (bugfix, feature, etc.)
- Testing done
- Checklist of completed items

### Review Process

1. **Automated checks** must pass (tests, linting)
2. **At least one approval** from maintainers required
3. **All comments** must be addressed
4. **No merge conflicts** with main branch
5. **Squash commits** before merging (maintainers will do this)

## Project Structure

```
dreamplanner/
├── apps/                   # Django applications
│   ├── users/              # User management
│   ├── dreams/             # Dreams, Goals, Tasks
│   ├── conversations/      # AI chat
│   ├── notifications/      # Push notifications
│   └── calendar/           # Calendar views
├── core/                   # Core utilities
├── integrations/           # External services
├── config/                 # Django settings
└── docs/                   # Documentation
```

## Branching Strategy

### Main Branches
- `main` - Production-ready code
- `develop` - Development branch (if using Git Flow)

### Feature Branches
- `feature/feature-name` - New features
- `bugfix/bug-name` - Bug fixes
- `hotfix/critical-bug` - Critical production bugs
- `docs/documentation-update` - Documentation only

### Example Workflow
```bash
# Create feature branch
git checkout -b feature/add-vision-boards

# Make changes and commit
git add .
git commit -m "feat(dreams): add vision board generation"

# Push to your fork
git push origin feature/add-vision-boards

# Create Pull Request on GitHub
```

## Documentation

### Code Documentation
- Add docstrings to all public classes and methods
- Use Google-style docstrings for Python
- Explain "why" not just "what"

### API Documentation
- Update OpenAPI/Swagger specs
- Include request/response examples
- Document error responses
- List required permissions

### User Documentation
- Update README.md for user-facing features
- Add examples and use cases
- Keep documentation in sync with code

## Getting Help

### Resources
- 📖 [Documentation](docs/)
- 💬 [GitHub Discussions](https://github.com/yourusername/dreamplanner/discussions)
- 🐛 [Issue Tracker](https://github.com/yourusername/dreamplanner/issues)

### Contact
- Open an issue for bugs or features
- Start a discussion for questions
- Email: support@dreamplanner.app (for security issues)

## Recognition

Contributors will be recognized in:
- README.md contributors section
- Release notes
- Annual contributor spotlight

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to DreamPlanner! 🌟

**Happy Coding!** 💻✨
