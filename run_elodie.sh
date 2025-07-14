#!/bin/bash

# Elodie wrapper script
# This script handles virtual environment setup and activation

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
ELODIE_SCRIPT="$SCRIPT_DIR/elodie.py"

# Function to check if venv exists and create if needed
setup_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        echo "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi
}

# Function to install missing requirements
install_requirements() {
    if [ -f "$REQUIREMENTS_FILE" ]; then
        echo "Installing/updating requirements..."
        pip install -r "$REQUIREMENTS_FILE"
    else
        echo "Warning: requirements.txt not found"
    fi
}

# Function to activate virtual environment
activate_venv() {
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
    else
        echo "Error: Virtual environment activation script not found"
        exit 1
    fi
}

# Function to convert relative paths to absolute paths
convert_paths() {
    local convert_next=false
    
    for arg in "$@"; do
        # Check if current argument is a path option that requires conversion
        if [[ "$arg" == "--destination" || "$arg" == "--source" || "$arg" == "--file" ]]; then
            printf '%s\n' "$arg"
            convert_next=true
        elif [ "$convert_next" = true ]; then
            # Convert relative path to absolute
            if [[ "$arg" != /* ]]; then
                # It's a relative path, convert to absolute
                if [ -e "$arg" ]; then
                    # Path exists, get real path
                    printf '%s\n' "$(cd "$(dirname "$arg")" 2>/dev/null && pwd)/$(basename "$arg")" 2>/dev/null || printf '%s\n' "$(pwd)/$arg"
                else
                    # Path doesn't exist yet, construct absolute path
                    printf '%s\n' "$(pwd)/$arg"
                fi
            else
                printf '%s\n' "$arg"
            fi
            convert_next=false
        else
            printf '%s\n' "$arg"
        fi
    done
}

# Main execution
main() {
    # Setup virtual environment if needed
    setup_venv
    
    # Activate virtual environment
    activate_venv
    
    # Install/update requirements
    install_requirements
    
    # Run elodie with original arguments (no path conversion)
    if [ -f "$ELODIE_SCRIPT" ]; then
        echo "Running: $VENV_DIR/bin/python $ELODIE_SCRIPT $@"
        "$VENV_DIR/bin/python" "$ELODIE_SCRIPT" "$@"
        exit_code=$?
    else
        echo "Error: elodie.py not found"
        exit_code=1
    fi
    
    # Deactivate virtual environment
    deactivate
    
    # Exit with the same code as elodie
    exit $exit_code
}

# Run main function with all arguments
main "$@"