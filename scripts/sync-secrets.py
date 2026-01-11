#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Sync GitHub secrets across multiple repositories.

Usage:
    uv run scripts/sync_secrets.py list
    uv run scripts/sync_secrets.py list CLAUDE_CODE_OAUTH_TOKEN
    uv run scripts/sync_secrets.py sync CLAUDE_CODE_OAUTH_TOKEN
    uv run scripts/sync_secrets.py sync --all
    uv run scripts/sync_secrets.py sync CLAUDE_CODE_OAUTH_TOKEN --dry-run
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from collections.abc import Sequence

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "secrets.yaml"


@dataclass
class KeychainConfig:
    """Configuration for keychain lookup."""

    service: str
    json_path: str | None = None  # e.g., "claudeAiOauth.accessToken"


@dataclass
class SecretDef:
    """Definition of a secret."""

    name: str
    description: str = ""
    keychain: KeychainConfig | None = None


@dataclass
class RepoDef:
    """Definition of a repository."""

    name: str
    secrets: list[str]


@dataclass
class Config:
    """Configuration loaded from secrets.yaml."""

    secrets: dict[str, SecretDef]
    repos: dict[str, RepoDef]

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> Config:
        """Load configuration from YAML file."""
        with path.open() as f:
            data = yaml.safe_load(f)

        secrets = {}
        for name, info in data.get("secrets", {}).items():
            keychain = None
            if info and "keychain" in info:
                kc = info["keychain"]
                keychain = KeychainConfig(
                    service=kc.get("service", ""),
                    json_path=kc.get("json_path"),
                )
            secrets[name] = SecretDef(
                name=name,
                description=info.get("description", "") if info else "",
                keychain=keychain,
            )

        repos = {}
        for name, info in data.get("repos", {}).items():
            repos[name] = RepoDef(
                name=name,
                secrets=info.get("secrets", []),
            )

        return cls(secrets=secrets, repos=repos)


def get_from_keychain(config: KeychainConfig) -> str | None:
    """Get a secret value from macOS Keychain.

    Returns the value if found, None otherwise.
    """
    if sys.platform != "darwin":
        return None

    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s", config.service,
                "-a", os.environ.get("USER", ""),
                "-w",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        value = result.stdout.strip()

        # If json_path is specified, extract the nested value
        if config.json_path and value:
            data = json.loads(value)
            for key in config.json_path.split("."):
                data = data[key]
            return str(data)

        return value
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
        return None


def run_gh(args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a gh CLI command."""
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=check,
    )


def secret_exists(repo: str, name: str) -> bool:
    """Check if a secret exists in a repository."""
    result = run_gh(["secret", "list", "--repo", repo], check=False)
    if result.returncode != 0:
        return False
    # Each line is: NAME\tUpdated ...\n
    for line in result.stdout.splitlines():
        if line.split("\t")[0] == name:
            return True
    return False


def set_secret(repo: str, name: str, value: str, *, dry_run: bool = False) -> bool:
    """Set a secret in a repository."""
    if dry_run:
        print(f"  [dry-run] Would set {name} in {repo}")
        return True

    result = run_gh(
        ["secret", "set", name, "--repo", repo, "--body", value],
        check=False,
    )
    if result.returncode != 0:
        print(f"  ✗ Failed to set {name} in {repo}: {result.stderr.strip()}")
        return False
    print(f"  ✓ Set {name} in {repo}")
    return True


def cmd_list(args: argparse.Namespace) -> int:
    """List status of secrets across repositories."""
    config = Config.load()

    # Filter to specific secret if provided
    secret_names = [args.secret] if args.secret else list(config.secrets.keys())

    for secret_name in secret_names:
        if secret_name not in config.secrets:
            print(f"Unknown secret: {secret_name}")
            return 1

        secret_def = config.secrets[secret_name]
        print(f"\n{secret_name}")
        if secret_def.description:
            print(f"  {secret_def.description}")
        print()

        # Find repos that need this secret
        repos_needing = [
            repo for repo in config.repos.values() if secret_name in repo.secrets
        ]

        for repo in repos_needing:
            exists = secret_exists(repo.name, secret_name)
            status = "✓" if exists else "✗ missing"
            print(f"  {status} {repo.name}")

    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    """Sync secrets to repositories."""
    config = Config.load()

    # Determine which secrets to sync
    if args.all:
        secret_names = list(config.secrets.keys())
    elif args.secret:
        secret_names = [args.secret]
    else:
        print("Error: Specify a secret name or use --all")
        return 1

    for secret_name in secret_names:
        if secret_name not in config.secrets:
            print(f"Unknown secret: {secret_name}")
            return 1

    # Get each secret value (skip if dry-run)
    secret_values: dict[str, str] = {}
    if not args.dry_run:
        for secret_name in secret_names:
            secret_def = config.secrets[secret_name]
            value = None

            # Try keychain first
            if secret_def.keychain:
                value = get_from_keychain(secret_def.keychain)
                if value:
                    print(f"  ✓ Got {secret_name} from keychain")

            # Fall back to prompting
            if not value:
                if sys.stdin.isatty():
                    value = getpass.getpass(f"Enter value for {secret_name}: ")
                else:
                    value = sys.stdin.readline().strip()

            if not value:
                print(f"Error: Empty value for {secret_name}")
                return 1
            secret_values[secret_name] = value

    # Sync each secret to repos that need it
    for secret_name in secret_names:
        print(f"\nSyncing {secret_name}...")

        repos_needing = [
            repo for repo in config.repos.values() if secret_name in repo.secrets
        ]

        for repo in repos_needing:
            exists = secret_exists(repo.name, secret_name)
            if exists:
                print(f"  ✓ {repo.name} (already set)")
            elif args.dry_run:
                print(f"  [dry-run] Would set {secret_name} in {repo.name}")
            else:
                set_secret(repo.name, secret_name, secret_values[secret_name])

    print("\nDone.")
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync GitHub secrets across repositories"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list command
    list_parser = subparsers.add_parser("list", help="List secret status")
    list_parser.add_argument("secret", nargs="?", help="Secret name (optional)")

    # sync command
    sync_parser = subparsers.add_parser("sync", help="Sync secrets")
    sync_parser.add_argument("secret", nargs="?", help="Secret name")
    sync_parser.add_argument("--all", action="store_true", help="Sync all secrets")
    sync_parser.add_argument(
        "--dry-run", action="store_true", help="Preview without making changes"
    )

    args = parser.parse_args()

    if args.command == "list":
        return cmd_list(args)
    elif args.command == "sync":
        return cmd_sync(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
