#!/usr/bin/env bash

python=$1
pypi_index=$2
shift 2

[[ -z $python ]] && python=python3
[[ -z $pypi_index ]] && pypi_index=https://pypi.vnpy.com

# Check if uv is installed, otherwise install it
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    $python -m pip install uv
fi

# Create virtual environment
uv venv --python $python

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip and wheel within the virtual environment (optional with uv, but good practice)
uv pip install --upgrade pip wheel --index-url $pypi_index

# Get and build ta-lib
function install-ta-lib()
{
    export HOMEBREW_NO_AUTO_UPDATE=true
    brew install ta-lib
}
function ta-lib-exists()
{
    ta-lib-config --libs > /dev/null
}
ta-lib-exists || install-ta-lib

# install ta-lib dependencies explicitly
uv pip install numpy==2.2.3 --index-url $pypi_index
uv pip install ta-lib==0.6.4 --index-url $pypi_index

# Install VeighNa
uv pip install . --index-url $pypi_index

