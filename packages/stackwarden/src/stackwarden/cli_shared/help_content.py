"""Help content for the StackWarden CLI."""

from __future__ import annotations

# Command maps are imported lazily to avoid circular imports
def _get_commands_help() -> str:
    from stackwarden.cli import CLI_HIGH_RISK_COMMAND_MAP, CLI_LOW_RISK_COMMAND_MAP

    lines = ["Command groups (low-risk: listing, read, export):\n"]
    for group, cmds in CLI_LOW_RISK_COMMAND_MAP.items():
        lines.append(f"  {group}: {', '.join(cmds)}\n")
    lines.append("\nCommand groups (high-risk: build, prune, migrate):\n")
    for group, cmds in CLI_HIGH_RISK_COMMAND_MAP.items():
        lines.append(f"  {group}: {', '.join(cmds)}\n")
    return "".join(lines)

HELP_EPILOG = """
Examples:
  stackwarden doctor
  stackwarden list profiles
  stackwarden list stacks
  stackwarden plan --profile <id> --stack <id>
  stackwarden ensure --profile <id> --stack <id>

Documentation: docs/reference.md
"""

HELP_QUICKSTART = """
Quick Start
-----------

  # Verify your environment
  stackwarden doctor

  # See what's available
  stackwarden list profiles
  stackwarden list stacks

  # Plan a build (dry run)
  stackwarden plan --profile <profile_id> --stack <stack_id>

  # Build the image
  stackwarden ensure --profile <profile_id> --stack <stack_id>

  # Or use the interactive wizard
  stackwarden wizard
"""

HELP_ENV = """
Environment Variables
--------------------

  STACKWARDEN_DATA_DIR     Override data root (profiles, stacks, layers, rules)
  STACKWARDEN_COMPAT_STRICT  Set to 1/true for strict compatibility mode
  STACKWARDEN_TUPLE_LAYER_MODE  off | shadow | warn | enforce (default)
  NGC_API_KEY             Required for pulling NGC base images
  EDITOR                  Editor for stackwarden profiles edit / stacks edit / layers edit
"""

HELP_TROUBLESHOOTING = """
Troubleshooting
---------------

  1. Run stackwarden doctor to verify Docker, Buildx, and GPU visibility.
  2. Ensure Docker daemon is running and you have permission to use it.
  3. For GPU profiles: install NVIDIA Container Toolkit and nvidia-smi.
  4. Check logs in ~/.local/share/stackwarden/logs/ (or STACKWARDEN_DATA_DIR/logs).
  5. Use --verbose for debug output on any command.
"""

HELP_FULL = """
StackWarden — Hardware-aware ML container build manager.

Quick Start
-----------
  stackwarden doctor
  stackwarden list profiles
  stackwarden list stacks
  stackwarden plan --profile <id> --stack <id>
  stackwarden ensure --profile <id> --stack <id>

Topics
------
  stackwarden help quickstart   Copy-paste examples
  stackwarden help env          Environment variables
  stackwarden help commands     Command groups (low-risk vs high-risk)
  stackwarden help troubleshooting  Common issues and fixes

Command Help
------------
  stackwarden <command> --help  Detailed help for any command

Documentation
-------------
  docs/reference.md
"""


def get_help_for_topic(topic: str | None) -> str | None:
    """Return help content for a topic, or None if not found."""
    if not topic:
        return HELP_FULL
    t = topic.lower().strip()
    if t in ("quickstart", "quick", "start"):
        return HELP_QUICKSTART
    if t in ("env", "environment", "variables"):
        return HELP_ENV
    if t in ("troubleshoot", "troubleshooting", "fix", "issues"):
        return HELP_TROUBLESHOOTING
    if t in ("commands", "command"):
        return _get_commands_help()
    return None
