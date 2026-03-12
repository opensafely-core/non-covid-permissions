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

# Install and upgrade requirements into venv without removing extraneous packages
devenv: _dotenv
    uv pip install --upgrade -r requirements.txt

    # Create private directories for monitoring input and output data
    mkdir -p input_files output_files

format *args:
    uv run ruff format --diff --quiet "$@"

lint *args:
    uv run ruff check "$@" .

lint-actions:
    docker run --rm -v $(pwd):/repo:ro --workdir /repo rhysd/actionlint:1.7.8 -color

# Fix formatting, import sort ordering, and justfile
fix: devenv
    -uv run ruff check --fix .
    -uv run ruff format .
    -just --fmt --unstable

# Run the various dev checks but does not change any files
check: devenv
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
