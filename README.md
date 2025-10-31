# AI Generated Tools

A collection of practical utilities primarily generated with AI assistance to solve specific development needs.

## Usage Instructions

### Installing Dependencies
Install all dependencies:
```bash
pip install -r requirements.txt
```

### Running Tools
```bash
python <tool_name>.py
```

## Tools List

### 🗺️ Memory Map Visualizer
**File**: `memory_map_visualizer.py`

A tool for visualizing memory layout mapping, especially useful for firmware development.

**Features**:
- Display multiple memory regions simultaneously
- Automatically avoid overlapping region conflicts
- Generate clear memory layout charts

![Memory Map Visualization](docs/images/memory_map_visualizer.png)

**Usage**:
```bash
python memory_map_visualizer.py
```
Uses `data.csv` by default and generates a PNG file.

**Command Line Options**

- `--file/-f <filename>`: Specify input CSV file (default: `data.csv`)
- `--debug/-d`: Print debug information including filtered CSV content

```bash
python memory_map_visualizer.py -f custom_data.csv -d
```

**CSV Format**

- The CSV file should contain the following columns: `group`, `name`, `address`, `size`
- **Comments**: Use `#` for inline comments
- **Space Alignment**: Spaces are automatically removed for better readability

**AI Contribution**: GitHub Copilot + ChatGPT (~75% AI generated)

---

### 🧭 Command Board (GUI Launcher)
Location: `command_board/`

Quick multi-repository & folder action launcher (Git logs, Git Bash, helper scripts, folder open) driven by a JSON config.

Core points:
- Data-driven tabs/groups/subgroups
- Multiple actions per row (log / bash / helper / open)
- Logging to `action.log` anchored in its directory
- Default: does NOT auto-close; use `-c` / `--auto-close` to close after a successful action
- CLI support: list / run / dry-run
- Config validation: GUI Test button or `--test-config` flag

Run examples:
```powershell
python command_board\main.py -l
python command_board\main.py -r git/vera/Kernel/helper -d
python command_board\main.py -c
python command_board\main.py --test-config
```

`--test-config` / Test button report includes:
- Total commands & actions
- Missing paths (with label)
- Missing executables
Exit code: 0 if all OK, 4 if any issue.

Config snippet:
```jsonc
{
	"groups": [ { "name": "git", "subgroups": [ /* ... */ ] } ],
	"settings": { "logFile": "action.log", "closeOnAction": false }
}
```

Add actions by appending objects to a command's `actions` array. Use `"type": "git-bash"` for Git Bash, otherwise specify `executable` + `argsTemplate`.

---

## Adding New Tools Guide

### File Naming Convention
- Use descriptive filenames like `tool_function.py`
- Avoid spaces, use underscores for separation

### Basic Structure
```python
#!/usr/bin/env python3
"""
Tool Name - Brief Description
Generated with AI assistance (specify which AI tools used)
"""

# Dependencies (list required packages)
# pip install package1 package2

# Your code here
```

---

**Note**: These tools are primarily generated with AI assistance, please adjust usage according to actual needs.