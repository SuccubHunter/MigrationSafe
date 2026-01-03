# migsafe Plugin Examples

This directory contains examples of creating custom plugins for migsafe.

## Usage

### Method 1: Loading from Directory

Specify the path to the plugins directory in the configuration file:

```json
{
  "plugins": {
    "directories": ["./examples/plugins"]
  }
}
```

Or use the CLI option:

```bash
migsafe analyze --plugins-dir ./examples/plugins
```

### Method 2: Loading via Entry Points

Add the plugin to `pyproject.toml` or `setup.py`:

```toml
[project.entry-points."migsafe.plugins"]
my-plugin = "examples.plugins.custom_plugin:MyCustomPlugin"
```

### Method 3: Loading from Module

Specify the module in the configuration:

```json
{
  "plugins": {
    "enabled": ["examples.plugins.custom_plugin:MyCustomPlugin"]
  }
}
```

## Creating Your Own Plugin

1. Create a class inheriting from `Plugin`
2. Implement required methods: `name`, `version`, `get_rules()`
3. Create rules inheriting from `Rule`
4. Register the plugin using one of the methods above

Example:

```python
from migsafe.plugins import Plugin
from migsafe.rules.base import Rule
from migsafe.models import MigrationOp, Issue, IssueSeverity, IssueType

class MyRule(Rule):
    name = "my_rule"
    
    def check(self, operation, index, operations):
        issues = []
        # Your validation logic
        return issues

class MyPlugin(Plugin):
    @property
    def name(self) -> str:
        return "my-plugin"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    def get_rules(self):
        return [MyRule()]
```

## Plugin Verification

Use the command to view loaded plugins:

```bash
migsafe plugins list
```

To get information about a specific plugin:

```bash
migsafe plugins info my-custom-plugin
```

