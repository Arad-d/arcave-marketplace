# AGENTS.md

Guidelines for AI coding agents working on this repository.

## Project Overview

This is a Python CLI marketing/shopping application with SQLite database.
- Single-file application: `main.py`
- Database: SQLite (`marketing_app.db`)
- Python version: 3.x

## Build/Lint/Test Commands

### Running the Application
```bash
# Run the main application
python main.py

# Or with explicit python3
python3 main.py
```

### Testing (Recommended Setup)
```bash
# Install pytest (if not already installed)
pip install pytest

# Run all tests
pytest

# Run a single test file
pytest test_main.py

# Run a single test function
pytest test_main.py::test_function_name

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=. --cov-report=term-missing
```

### Linting and Formatting (Recommended)
```bash
# Install tools
pip install ruff black

# Lint code
ruff check .
ruff check main.py

# Auto-fix linting issues
ruff check --fix .

# Format code
black main.py
black .

# Check formatting without making changes
black --check main.py
```

### Type Checking (Optional)
```bash
pip install mypy
mypy main.py
```

## Code Style Guidelines

### General Principles
- Follow PEP 8 style guide
- Use meaningful variable and function names
- Keep functions focused and small (single responsibility)
- Add docstrings to all functions

### Imports
- Use standard library imports first
- Group imports: stdlib, third-party, local
- Avoid wildcard imports (`from module import *`)
- Example:
  ```python
  import sqlite3
  from typing import Optional, List
  ```

### Naming Conventions
- Functions: `snake_case` (e.g., `shop_owner_login`)
- Variables: `snake_case` (e.g., `commodity_id`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DATABASE_NAME`)
- Classes: `PascalCase` (e.g., `ShopOwner`)
- Database tables: `snake_case` (plural, e.g., `shop_owners`)

### Type Hints
- Add type hints to function signatures
- Use `Optional` for nullable parameters
- Example:
  ```python
  def get_customer(customer_id: int) -> Optional[dict]:
      ...
  ```

### Error Handling
- Use try/except blocks for database operations
- Never expose raw error messages to users
- Log errors appropriately
- Example:
  ```python
  try:
      cursor.execute(query, params)
      conn.commit()
  except sqlite3.Error as e:
      print("An error occurred. Please try again.")
      # Log error for debugging
  ```

### Security Guidelines
- **CRITICAL**: Never store passwords in plain text (current issue)
- Use parameterized queries to prevent SQL injection (already done ✓)
- Validate all user inputs
- Sanitize data before display
- Recommended: Use `bcrypt` or `hashlib` for password hashing

### Database Guidelines
- Always close connections properly (use context managers)
- Use transactions for multiple related operations
- Create indexes on frequently queried columns
- Example:
  ```python
  with sqlite3.connect('marketing_app.db') as conn:
      cursor = conn.cursor()
      # operations
  ```

### Function Documentation
```python
def function_name(param: type) -> return_type:
    """Brief description of function.
    
    Args:
        param: Description of parameter
        
    Returns:
        Description of return value
    """
    pass
```

## File Structure

```
.
├── main.py              # Main application entry point
├── marketing_app.db     # SQLite database (auto-generated)
├── .idea/               # IntelliJ/PyCharm configuration
└── AGENTS.md           # This file
```

## Development Workflow

1. Make changes to `main.py`
2. Run tests: `pytest`
3. Check linting: `ruff check .`
4. Format code: `black .`
5. Test manually: `python main.py`

## Known Issues to Address

1. **Security**: Passwords stored in plain text
2. **Error Handling**: Limited error handling for edge cases
3. **Input Validation**: No validation on user inputs
4. **Testing**: No automated tests exist
5. **Documentation**: Functions lack docstrings

## IDE Configuration

Project uses IntelliJ/PyCharm (`.idea/` directory present). Import settings are preserved.

## Dependencies

Currently no external dependencies (stdlib only).
Recommended additions:
- `pytest` - Testing framework
- `ruff` - Linting and formatting
- `black` - Code formatting
- `bcrypt` - Password hashing

---

*This file helps AI agents understand the codebase and follow consistent patterns.*
