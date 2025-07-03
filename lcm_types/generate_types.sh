#!/bin/bash

# Script to generate LCM types for Python and C++
# This ensures generated files are placed in the correct directories for distribution

set -e  # Exit on any error

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Generating LCM types..."
echo "Script directory: $SCRIPT_DIR"
echo "Project root: $PROJECT_ROOT"

# Generate Python types
echo "Generating Python types..."
lcm-gen --python --ppath "$PROJECT_ROOT/python/lcmware/types" "$SCRIPT_DIR"/*.lcm

# Generate C++ types  
echo "Generating C++ types..."
lcm-gen --cpp --cpp-hpath "$PROJECT_ROOT/cpp/lcmware/types" "$SCRIPT_DIR"/*.lcm

echo "Generating Java types..."
lcm-gen --java --jpath "$PROJECT_ROOT/java/lcmware/types" "$SCRIPT_DIR"/*.lcm

echo "Type generation complete!"
echo "Python types generated in: $PROJECT_ROOT/python/lcmware/types"
echo "C++ types generated in: $PROJECT_ROOT/cpp/lcmware/types"
echo "Java types generated in: $PROJECT_ROOT/java/"