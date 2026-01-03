# Git History Analysis Examples

This directory contains examples of using Git history analysis functionality for migrations.

## Files

- `basic_analysis.py` - basic migration history analysis
- `trend_analysis.py` - migration trends and patterns analysis

## Requirements

- Git repository with migration history
- Python package `GitPython`
- Access to commit history

## Basic Analysis

```bash
# In the Git repository root
python basic_analysis.py
```

## Trend Analysis

```bash
# Analyze trends for the last month
python trend_analysis.py
```

## Configuration

Before running the examples, configure the following parameters in the files:

- `REPO_PATH` - path to Git repository (default: current directory)

## Additional Information

- [History Analysis Guide](../../docs/GIT_HISTORY.md)
- [Main Documentation](../../README.md)

