# Contributing to PlanMod

## Development Setup

1. Fork the repository
2. Clone your fork
3. Set up development environment:
   ```bash
   poetry install
   poetry shell
   ```

4. Install pre-commit hooks (optional):
   ```bash
   pre-commit install
   ```

## Code Style

- Follow PEP 8
- Use `black` for formatting (line length: 100)
- Use `mypy` for type checking
- Use `ruff` for linting

```bash
# Format code
black src/ tests/

# Type check
mypy src/

# Lint
ruff check src/ tests/
```

## Testing

- Write tests for new features
- Run tests before committing:
  ```bash
  pytest
  ```
- Aim for >80% code coverage

## Project Structure

```
src/
  ingestion/     - DXF parsing and rendering
  vlm_client/    - VLM API integration
  scene/         - Scene graph data structures
  components/    - Component database and replacement
  geometry/      - Mass/CG and projection
  export/        - DXF export
  cli/           - Command-line interface
```

## Adding New Features

1. Create a feature branch
2. Implement feature with tests
3. Update documentation (README, progress.md)
4. Submit pull request

## VLM Integration

When adding support for new VLM providers:

1. Add provider-specific method in `src/vlm_client/client.py`
2. Update `_call_vlm_api` to route to new provider
3. Test with sample images
4. Document API requirements in README

## Component Database

To add new component types:

1. Edit `src/components/database.py`
2. Add component specs with material properties
3. Update `_initialize_default_data()` if needed
4. Add tests in `tests/test_component_database.py`

## AWS Infrastructure

When modifying Terraform configs:

1. Test changes in a development AWS account
2. Update `infra/terraform/README.md` if needed
3. Document any new variables or outputs

