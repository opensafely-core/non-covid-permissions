set dotenv-load := true
set positional-arguments := true

# List available commands
default:
    @"{{ just_executable() }}" --list

# Create a valid .env if none exists
_dotenv:
    #!/usr/bin/env bash
    set -euo pipefail

    if [[ ! -f .env ]]; then
      echo "No '.env' file found; creating a default '.env' from 'dotenv-sample'"
      cp dotenv-sample .env
    fi

# prompt the user to run just devenv to set up their local environment properly.
_checkenv:
    #!/usr/bin/env bash
    set -euo pipefail

    if [[ ! -f .env ]]; then
        echo "No '.env' file found; run 'just devenv' to create one"
        exit 1
    fi

# Install dev requirements into venv without removing extraneous packages
devenv: _dotenv
    uv sync --inexact

# Upgrade a single package to the latest version as of the cutoff in pyproject.toml
upgrade-package package: && uvmirror devenv
    uv lock --upgrade-package {{ package }}

# Upgrade all packages to the latest versions as of the cutoff in pyproject.toml
upgrade-all: && uvmirror devenv
    uv lock --upgrade

# update the uv mirror requirements file
uvmirror file="requirements.uvmirror.txt":
    rm -f {{ file }}
    uv export --format requirements-txt --frozen --no-hashes --all-groups --all-extras > {{ file }}

# Move the cutoff date in pyproject.toml to N days ago (default: 7) at midnight UTC
bump-uv-cutoff days="7":
    #!/usr/bin/env -S uvx --with tomlkit python3.13
    # Note we specify the python version here and we don't care if it's different to
    # the .python-version; we need 3.11+ for the datetime code used.

    import datetime
    import tomlkit

    with open("pyproject.toml", "rb") as f:
        content = tomlkit.load(f)

    new_datetime = (
        datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=int("{{ days }}"))
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    new_timestamp = new_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
    if existing_timestamp := content["tool"]["uv"].get("exclude-newer"):
        if new_datetime < datetime.datetime.fromisoformat(existing_timestamp):
            print(
                f"Existing cutoff {existing_timestamp} is more recent than {new_timestamp}, not updating."
            )
            exit(0)
    content["tool"]["uv"]["exclude-newer"] = new_timestamp

    with open("pyproject.toml", "w") as f:
        tomlkit.dump(content, f)

# This is the default input command to update-dependencies action
# https://github.com/bennettoxford/update-dependencies-action

# Bump the timestamp cutoff to midnight UTC 7 days ago and upgrade all dependencies
update-dependencies: bump-uv-cutoff upgrade-all

format *args:
    uv run ruff format --diff --quiet "$@"

lint *args:
    uv run ruff check "$@" .

lint-actions:
    docker run --rm -v $(pwd):/repo:ro --workdir /repo rhysd/actionlint:1.7.8 -color

# TMP: install requirements
requirements:
    uv pip install -r requirements.txt

# Run the various dev checks but does not change any files
check: requirements
    #!/usr/bin/env bash
    set -euo pipefail

    failed=0

    check() {
      echo -e "\e[1m=> ${1}\e[0m"
      rc=0
      # Run it
      eval $1 || rc=$?
      # Increment the counter on failure
      if [[ $rc != 0 ]]; then
        failed=$((failed + 1))
        # Add spacing to separate the error output from the next check
        echo -e "\n"
      fi
    }

    # check "just check-lockfile"
    check "just format"
    check "just lint"
    check "just lint-actions"
    # test -d docker/ && check "just docker/lint"

    if [[ $failed > 0 ]]; then
      echo -en "\e[1;31m"
      echo "   $failed checks failed"
      echo -e "\e[0m"
      exit 1
    fi

# Fix formatting, import sort ordering, and justfile
fix: requirements
    -uv run ruff check --fix .
    -uv run ruff format .
    -just --fmt --unstable

# Get jobserver dump
dump:
    scp Providence-o@dokku4.ebmdatalab.net:/var/lib/dokku/data/storage/job-server/jobserver.dump jobserver.dump
    # scp dokku4:/var/lib/dokku/data/storage/job-server/jobserver.dump jobserver.dump
