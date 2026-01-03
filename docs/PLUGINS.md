# migsafe Plugin System

## Introduction

migsafe supports a plugin system for creating custom analysis rules. This allows extending migsafe functionality without modifying the core code.

## Benefits

- ✅ **Extensibility**: Create your own analysis rules
- ✅ **Flexibility**: Customize rules to your needs
- ✅ **Reusability**: Use plugins across different projects
- ✅ **Isolation**: Plugins don't affect migsafe core code

## Creating a Plugin

### Basic Plugin

A plugin is a class that inherits from `Plugin` and implements the necessary methods:

```python
# my_plugin.py
from migsafe.plugins import Plugin
from migsafe.rules.base import Rule
from migsafe.models import MigrationOp, Issue, IssueSeverity, IssueType

class MyCustomRule(Rule):
    """Custom rule for checking."""
    
    name = "my_custom_rule"
    
    def check(self, operation: MigrationOp) -> list[Issue]:
        issues = []
        
        # Your checking logic
        if operation.type == "add_column":
            if operation.column == "password":
                issues.append(Issue(
                    severity=IssueSeverity.WARNING,
                    type=IssueType.UNKNOWN,
                    message="Adding 'password' column requires special attention",
                    operation_index=0
                ))
        
        return issues

class MyPlugin(Plugin):
    """My custom plugin."""
    
    @property
    def name(self) -> str:
        return "my-plugin"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Plugin with custom rules"
    
    @property
    def author(self) -> str:
        return "John Doe"
    
    def get_rules(self) -> list[Rule]:
        return [MyCustomRule()]
```

### Plugin Registration

#### Method 1: Entry Points (Recommended)

In `setup.py` or `pyproject.toml`:

```python
# setup.py
from setuptools import setup

setup(
    name="my-package",
    version="1.0.0",
    # ... other parameters ...
    entry_points={
        'migsafe.plugins': [
            'my-plugin = my_plugin:MyPlugin',
        ],
    },
)
```

```toml
# pyproject.toml
[project.entry-points."migsafe.plugins"]
my-plugin = "my_plugin:MyPlugin"
```

#### Method 2: Loading from Directory

Place the plugin file in a directory and specify the path:

```bash
migsafe analyze --plugins-dir ./plugins
```

## Using Plugins

### Loading from Directory

```bash
# Specify directory with plugins
migsafe analyze --plugins-dir ./plugins

# You can specify multiple directories via configuration file
```

### Configuration via File

In `migsafe.json` or `migsafe.toml`:

```json
{
  "plugins": {
    "directories": ["./plugins", "./custom-plugins"]
  }
}
```

```toml
[migsafe.plugins]
directories = ["./plugins", "./custom-plugins"]
```

### Plugin Management

#### List Loaded Plugins

```bash
migsafe plugins list
```

Output:
```
📦 Loaded plugins: 2

  • my-plugin v1.0.0
    Plugin with custom rules
    Author: John Doe
    Rules: 1
      - my_custom_rule

  • another-plugin v2.0.0
    Another plugin
    Rules: 3
```

#### Plugin Information

```bash
migsafe plugins info my-plugin
```

Output:
```
📦 Plugin: my-plugin
   Version: 1.0.0
   Description: Plugin with custom rules
   Author: John Doe

   Rules: 1
   1. my_custom_rule
```

## Plugin Examples

### Example 1: Simple Plugin

```python
# examples/plugins/simple_plugin.py
from migsafe.plugins import Plugin
from migsafe.rules.base import Rule
from migsafe.models import MigrationOp, Issue, IssueSeverity, IssueType

class NoDropTableRule(Rule):
    """Prohibits table deletion."""
    
    name = "no_drop_table"
    
    def check(self, operation: MigrationOp) -> list[Issue]:
        if operation.type == "drop_table":
            return [Issue(
                severity=IssueSeverity.CRITICAL,
                type=IssueType.UNKNOWN,
                message=f"Dropping table '{operation.table}' is prohibited",
                operation_index=0
            )]
        return []

class SimplePlugin(Plugin):
    @property
    def name(self) -> str:
        return "simple-plugin"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    def get_rules(self) -> list[Rule]:
        return [NoDropTableRule()]
```

### Example 2: Configurable Plugin

```python
# examples/plugins/configurable_plugin.py
from migsafe.plugins import Plugin
from migsafe.rules.base import Rule
from migsafe.models import MigrationOp, Issue, IssueSeverity, IssueType

class ConfigurableRule(Rule):
    """Rule with configuration."""
    
    name = "configurable_rule"
    
    def __init__(self, forbidden_tables: list[str] = None):
        self.forbidden_tables = forbidden_tables or []
    
    def check(self, operation: MigrationOp) -> list[Issue]:
        issues = []
        
        if operation.type == "drop_table":
            if operation.table in self.forbidden_tables:
                issues.append(Issue(
                    severity=IssueSeverity.CRITICAL,
                    type=IssueType.UNKNOWN,
                    message=f"Dropping table '{operation.table}' is prohibited",
                    operation_index=0
                ))
        
        return issues

class ConfigurablePlugin(Plugin):
    def __init__(self, config: dict = None):
        self.config = config or {}
    
    @property
    def name(self) -> str:
        return "configurable-plugin"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    def get_rules(self) -> list[Rule]:
        forbidden_tables = self.config.get("forbidden_tables", [])
        return [ConfigurableRule(forbidden_tables=forbidden_tables)]
```

Configuration in `migsafe.json`:

```json
{
  "plugins": {
    "configurable-plugin": {
      "forbidden_tables": ["users", "orders"]
    }
  }
}
```

### Example 3: Advanced Plugin

```python
# examples/plugins/advanced_plugin.py
from migsafe.plugins import Plugin, PluginContext
from migsafe.rules.base import Rule
from migsafe.models import MigrationOp, Issue, IssueSeverity, IssueType

class AdvancedRule(Rule):
    """Advanced rule using context."""
    
    name = "advanced_rule"
    
    def __init__(self, context: PluginContext = None):
        self.context = context
    
    def check(self, operation: MigrationOp) -> list[Issue]:
        issues = []
        
        # Use context to access other rules
        if self.context:
            # Your logic using context
            pass
        
        return issues

class AdvancedPlugin(Plugin):
    def __init__(self, config: dict = None):
        self.config = config or {}
    
    @property
    def name(self) -> str:
        return "advanced-plugin"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    def get_rules(self) -> list[Rule]:
        return [AdvancedRule()]
    
    def initialize(self, context: PluginContext):
        """Initialize plugin with context."""
        # Your initialization logic
        pass
```

## Plugin Structure

### Required Methods

- `name` (property) - plugin name (unique)
- `version` (property) - plugin version
- `get_rules()` - returns list of plugin rules

### Optional Methods

- `description` (property) - plugin description
- `author` (property) - plugin author
- `initialize(context)` - initialize plugin with context

## Testing Plugins

### Unit Tests

```python
# test_my_plugin.py
import pytest
from my_plugin import MyPlugin, MyCustomRule
from migsafe.models import MigrationOp

def test_my_plugin():
    plugin = MyPlugin()
    assert plugin.name == "my-plugin"
    assert plugin.version == "1.0.0"
    
    rules = plugin.get_rules()
    assert len(rules) == 1
    assert isinstance(rules[0], MyCustomRule)

def test_my_custom_rule():
    rule = MyCustomRule()
    operation = MigrationOp(type="add_column", column="password")
    
    issues = rule.check(operation)
    assert len(issues) == 1
    assert issues[0].severity == IssueSeverity.WARNING
```

## Recommendations

1. **Naming**: Use unique names for plugins
2. **Versioning**: Follow Semantic Versioning
3. **Documentation**: Document rules and their purpose
4. **Testing**: Write tests for your plugins
5. **Configuration**: Use configuration for flexibility

## Limitations

⚠️ **Important:**

- Plugins are loaded during analysis execution
- Errors in plugins can interrupt analysis (use error handling)
- Plugins have access to the same data as built-in rules

## Additional Information

- [Main Documentation](../README.md)
- [Plugin Examples](../examples/plugins/)
- [Plugin API Documentation](../migsafe/plugins/base.py)
