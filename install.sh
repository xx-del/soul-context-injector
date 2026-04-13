#!/bin/bash
# Soul Context Injector - Installation Script
# Version: v5.2.1

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

PLUGIN_NAME="soul-context-injector"
PLUGIN_VERSION="5.2.1"
PLUGIN_DIR="$HOME/.hermes/plugins/$PLUGIN_NAME"

print_header() {
    echo -e "${CYAN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║   Soul Context Injector v${PLUGIN_VERSION}            ║${NC}"
    echo -e "${CYAN}║   Installation Script                      ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════╝${NC}"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

check_requirements() {
    print_info "Checking system requirements..."
    
    # Check Python
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        print_success "Python $PYTHON_VERSION found"
    else
        print_error "Python 3 not found. Please install Python 3.8+"
        exit 1
    fi
    
    # Check pip
    if command -v pip &> /dev/null || command -v pip3 &> /dev/null; then
        print_success "pip found"
    else
        print_error "pip not found. Please install pip"
        exit 1
    fi
}

install_dependencies() {
    print_info "Installing dependencies..."
    
    if pip install httpx pyyaml 2>/dev/null || pip3 install httpx pyyaml 2>/dev/null; then
        print_success "Dependencies installed successfully"
    else
        print_error "Failed to install dependencies"
        exit 1
    fi
}

verify_installation() {
    print_info "Verifying installation..."
    
    # Check plugin directory
    if [ -d "$PLUGIN_DIR" ]; then
        print_success "Plugin directory exists"
    else
        print_error "Plugin directory not found: $PLUGIN_DIR"
        exit 1
    fi
    
    # Check required files
    local required_files=(
        "__init__.py"
        "plugin.yaml"
        "analyzer.py"
        "interceptor.py"
        "context_builder.py"
        "state.py"
        "constants.py"
        "workflow_cache.py"
    )
    
    local missing_files=()
    for file in "${required_files[@]}"; do
        if [ ! -f "$PLUGIN_DIR/$file" ]; then
            missing_files+=("$file")
        fi
    done
    
    if [ ${#missing_files[@]} -eq 0 ]; then
        print_success "All required files present"
    else
        print_warning "Missing files: ${missing_files[*]}"
    fi
    
    # Check directories
    if [ -d "$PLUGIN_DIR/rules" ]; then
        print_success "Rules directory exists"
    else
        print_warning "Rules directory not found"
    fi
    
    if [ -d "$PLUGIN_DIR/prompts" ]; then
        print_success "Prompts directory exists"
    else
        print_warning "Prompts directory not found"
    fi
    
    # Verify Python dependencies
    if python3 -c "import httpx; import yaml" 2>/dev/null; then
        print_success "Python dependencies verified"
    else
        print_error "Python dependencies not properly installed"
        exit 1
    fi
}

install_from_git() {
    print_info "Installing from Git repository..."
    
    if [ -d ".git" ]; then
        print_success "Git repository detected"
        check_requirements
        install_dependencies
        verify_installation
    else
        print_error "Not a Git repository. Use --archive for archive installation."
        exit 1
    fi
}

install_from_archive() {
    print_info "Installing from archive..."
    
    check_requirements
    install_dependencies
    verify_installation
}

show_next_steps() {
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════${NC}"
    echo -e "${GREEN}Installation Complete!${NC}"
    echo -e "${CYAN}════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Review README.md for plugin overview"
    echo "  2. Read USAGE.md for usage instructions"
    echo "  3. Customize rules in rules/ directory"
    echo "  4. Configure prompts in prompts/ directory"
    echo ""
    echo -e "${YELLOW}Plugin Location:${NC}"
    echo "  $PLUGIN_DIR"
    echo ""
    echo -e "${YELLOW}Configuration File:${NC}"
    echo "  $PLUGIN_DIR/plugin.yaml"
    echo ""
}

show_help() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  --git       Install from Git repository"
    echo "  --archive   Install from extracted archive"
    echo "  --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --git      # After cloning from Git"
    echo "  $0 --archive  # After extracting tar.gz/zip"
}

# Main
main() {
    print_header
    
    case "${1:-}" in
        --git)
            install_from_git
            ;;
        --archive)
            install_from_archive
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            print_error "No installation method specified"
            show_help
            exit 1
            ;;
    esac
    
    show_next_steps
}

main "$@"
