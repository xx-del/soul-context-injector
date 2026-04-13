# Soul Context Injector - Installation Guide

Version: v5.2.1

## Quick Install

### Method 1: From Git Repository

```bash
git clone <repository-url> ~/.hermes/plugins/soul-context-injector
cd ~/.hermes/plugins/soul-context-injector
./install.sh --git
```

### Method 2: From Archive

```bash
tar -xzf soul-context-injector-v5.2.1.tar.gz -C ~/.hermes/plugins/
cd ~/.hermes/plugins/soul-context-injector
./install.sh --archive
```

## System Requirements

- Python 3.8+
- pip (Python package manager)
- Git (for --git installation method)

## Dependencies

The plugin requires the following Python packages:

- httpx >= 0.24.0
- pyyaml >= 6.0

## Configuration

After installation, configure the plugin by editing `plugin.yaml`:

```yaml
# Main configuration file
name: soul-context-injector
version: "5.2.1"
enabled: true
```

### Custom Rules

Place custom rules in the `rules/` directory:

- `l0.md` - L0 basic rules
- `l1.md` - L1 simple query rules
- `l2.md` - L2 moderate complexity rules
- `l3.md` - L3 complex rules
- `l4.md` - L4 advanced rules
- `skill_rules.md` - Skill usage rules
- `trigger_conditions.md` - Trigger conditions

### Custom Prompts

Place custom prompts in the `prompts/` directory:

- `ollama_prompt.md` - Main prompt template

## Verify Installation

Run the following commands to verify installation:

```bash
# Check plugin files
ls ~/.hermes/plugins/soul-context-injector/

# Verify dependencies
python3 -c "import httpx; import yaml; print('Dependencies OK')"

# Check plugin structure
ls ~/.hermes/plugins/soul-context-injector/rules/
ls ~/.hermes/plugins/soul-context-injector/prompts/
```

## Troubleshooting

### Dependency Installation Failed

```bash
pip install --upgrade pip
pip install httpx pyyaml
```

### Permission Denied

```bash
chmod +x ~/.hermes/plugins/soul-context-injector/install.sh
```

### Plugin Not Loading

1. Check `plugin.yaml` syntax
2. Verify Python version: `python3 --version`
3. Check logs for errors

## Next Steps

After installation:

1. Review `README.md` for plugin overview
2. Read `USAGE.md` for usage instructions
3. Customize rules in `rules/` directory
4. Configure prompts in `prompts/` directory

## Support

For issues and feature requests, please open an issue in the repository.
