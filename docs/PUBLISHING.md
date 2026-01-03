# Publishing migsafe to PyPI

This document describes the process of publishing the migsafe package to PyPI.

## Prerequisites

1. **PyPI Account**: Register at [pypi.org](https://pypi.org/account/register/)
2. **TestPyPI Account**: Register at [test.pypi.org](https://test.pypi.org/account/register/)
3. **API Tokens**: Create API tokens for both services in your account settings
4. **Installed Tools**:
   ```bash
   pip install build twine
   ```

## Preparation for Publishing

### 1. Version Update

Before publishing, update the version in the following files:

- `pyproject.toml` - `[project]` section → `version`
- `migsafe/__init__.py` - `__version__` variable
- `CHANGELOG.md` - add an entry for the new version

### 2. Metadata Verification

Make sure all metadata in `pyproject.toml` is correct:

```bash
# Check metadata
python -m build --sdist
python -m build --wheel
```

### 3. Local Verification

```bash
# Run all tests
make test

# Run all linters
make lint

# Verify that the package builds correctly
python -m build
```

## Publishing to TestPyPI

**Important:** Always publish to TestPyPI first for verification!

### 1. Build Package

```bash
# Clean old builds
rm -rf dist/ build/ *.egg-info

# Build package
python -m build
```

### 2. Check Package

```bash
# Check with twine
twine check dist/*
```

### 3. Upload to TestPyPI

```bash
# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Enter your TestPyPI credentials
# Username: __token__
# Password: <your TestPyPI API token>
```

### 4. Verify Installation from TestPyPI

```bash
# Create a new virtual environment
python -m venv test_env
source test_env/bin/activate  # Linux/Mac
# or
test_env\Scripts\activate  # Windows

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ migsafe

# Verify installation
migsafe --version
migsafe analyze --help
```

## Publishing to PyPI

After successful verification on TestPyPI:

### 1. Create Version Tag

```bash
# Create tag for new version
git tag -a v0.4.0 -m "Release version 0.4.0"
git push origin v0.4.0
```

### 2. Upload to PyPI

```bash
# Make sure package is rebuilt
python -m build

# Upload to PyPI
twine upload dist/*

# Enter your PyPI credentials
# Username: __token__
# Password: <your PyPI API token>
```

### 3. Verify on PyPI

After uploading, verify:

1. Open [pypi.org/project/migsafe](https://pypi.org/project/migsafe)
2. Make sure the version is displayed correctly
3. Check that all metadata is displayed properly
4. Verify installation:
   ```bash
   pip install migsafe
   migsafe --version
   ```

## Automation via GitHub Actions

You can use GitHub Actions for automatic publishing when creating a tag.

### Create workflow file `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [created]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install build dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine
      
      - name: Build package
        run: python -m build
      
      - name: Check package
        run: twine check dist/*
      
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

### Setting up Secrets in GitHub

1. Go to Settings → Secrets and variables → Actions
2. Add secret `PYPI_API_TOKEN` with your PyPI API token

## Pre-Publishing Checklist

- [ ] Version updated in all files
- [ ] CHANGELOG.md updated
- [ ] All tests pass
- [ ] All linters pass
- [ ] Package builds successfully
- [ ] TestPyPI verification passed
- [ ] Installation from TestPyPI works
- [ ] Version tag created in Git
- [ ] All changes committed and pushed

## Version Rollback

If you need to rollback a version on PyPI:

1. **You cannot delete a version**, but you can hide it:
   - Go to the project page on PyPI
   - In the "Release history" section, click "Hide" for the desired version

2. **Release a new version** with fixes

## Useful Links

- [PyPI Documentation](https://packaging.python.org/en/latest/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [Python Packaging User Guide](https://packaging.python.org/guides/distributing-packages-using-setuptools/)

## Support

If you encounter issues during publishing:

1. Check upload logs
2. Make sure the version is unique (you cannot upload the same version twice)
3. Verify that all dependencies are specified correctly
4. Refer to PyPI documentation
