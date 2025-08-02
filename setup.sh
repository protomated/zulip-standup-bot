#!/bin/bash
set -euo pipefail

# Zulip Standup Bot Setup Script
# This script helps you set up the Zulip Standup Bot for development or production

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PYTHON_MIN_VERSION="3.8"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
ENV_FILE="$PROJECT_DIR/.env"

# Functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_command() {
    if command -v "$1" >/dev/null 2>&1; then
        log_success "$1 is installed"
        return 0
    else
        log_error "$1 is not installed"
        return 1
    fi
}

check_python_version() {
    if command -v python3 >/dev/null 2>&1; then
        local version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        if python3 -c "import sys; exit(0 if sys.version_info >= (3,8) else 1)"; then
            log_success "Python $version is compatible"
            return 0
        else
            log_error "Python $version is too old. Minimum required: $PYTHON_MIN_VERSION"
            return 1
        fi
    else
        log_error "Python 3 is not installed"
        return 1
    fi
}

install_system_dependencies() {
    log_info "Installing system dependencies..."

    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt-get >/dev/null 2>&1; then
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv python3-dev libpq-dev build-essential
        elif command -v yum >/dev/null 2>&1; then
            sudo yum install -y python3 python3-pip python3-devel postgresql-devel gcc
        elif command -v dnf >/dev/null 2>&1; then
            sudo dnf install -y python3 python3-pip python3-devel postgresql-devel gcc
        else
            log_warning "Unknown Linux distribution. Please install Python 3.8+, pip, and development tools manually."
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew >/dev/null 2>&1; then
            brew install python@3.11 postgresql
        else
            log_warning "Homebrew not found. Please install Python 3.8+ manually."
        fi
    else
        log_warning "Unknown operating system. Please install Python 3.8+ manually."
    fi
}

setup_virtual_environment() {
    log_info "Setting up Python virtual environment..."

    if [[ -d "$VENV_DIR" ]]; then
        log_warning "Virtual environment already exists. Removing and recreating..."
        rm -rf "$VENV_DIR"
    fi

    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"

    log_info "Upgrading pip..."
    pip install --upgrade pip

    log_success "Virtual environment created at $VENV_DIR"
}

install_python_dependencies() {
    log_info "Installing Python dependencies..."

    source "$VENV_DIR/bin/activate"

    # Install main requirements
    pip install -r requirements.txt

    # Install the local zulip_bots package in development mode
    cd zulip_bots && pip install -e . && cd ..

    # Install the bot package in development mode
    pip install -e .

    log_success "Python dependencies installed"
}

setup_environment_file() {
    log_info "Setting up environment configuration..."

    if [[ -f "$ENV_FILE" ]]; then
        log_warning ".env file already exists. Backing up to .env.backup"
        cp "$ENV_FILE" "$ENV_FILE.backup"
    fi

    cp .env.example "$ENV_FILE"

    log_success "Environment file created at $ENV_FILE"
    log_warning "Please edit $ENV_FILE with your actual configuration values"
}

create_directories() {
    log_info "Creating necessary directories..."

    mkdir -p "$PROJECT_DIR/data"
    mkdir -p "$PROJECT_DIR/logs"
    mkdir -p "$PROJECT_DIR/backups"

    log_success "Directories created"
}

setup_database() {
    log_info "Setting up database..."

    source "$VENV_DIR/bin/activate"

    # Initialize database using a simple Python script
    python -c "
import sys
import os

# Add the zulip_bots directory to Python path
sys.path.insert(0, os.path.join(os.getcwd(), 'zulip_bots'))

try:
    from zulip_bots.bots.standup import database
    database.init_db()
    print('✅ Database initialized successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    print('Trying alternative import method...')
    try:
        # Alternative: directly import from file
        import importlib.util
        spec = importlib.util.spec_from_file_location('database', 'zulip_bots/zulip_bots/bots/standup/database.py')
        database_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(database_module)
        database_module.init_db()
        print('✅ Database initialized successfully (alternative method)')
    except Exception as e2:
        print(f'❌ Database initialization failed: {e2}')
        exit(1)
except Exception as e:
    print(f'❌ Database initialization failed: {e}')
    exit(1)
"

    log_success "Database setup complete"
}

run_tests() {
    log_info "Running tests to verify installation..."

    source "$VENV_DIR/bin/activate"

    # Run basic tests
    if python -m pytest zulip_bots/zulip_bots/bots/standup/test_standup.py -v; then
        log_success "All tests passed"
    else
        log_warning "Some tests failed. The installation may still work, but please check the logs."
    fi
}

show_usage_instructions() {
    log_success "🎉 Setup complete!"
    echo
    echo "Next steps:"
    echo "1. Edit $ENV_FILE with your Zulip bot credentials"
    echo "2. Activate the virtual environment: source venv/bin/activate"
    echo "3. Run the bot: python run_standup_bot.py"
    echo
    echo "For Docker deployment:"
    echo "1. docker-compose up -d"
    echo
    echo "For more information, see README.md"
}

# Main setup function
main() {
    echo "🤖 Zulip Standup Bot Setup"
    echo "========================="
    echo

    # Parse command line arguments
    SETUP_TYPE="development"
    SKIP_TESTS=false
    INSTALL_DOCKER=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --production)
                SETUP_TYPE="production"
                shift
                ;;
            --skip-tests)
                SKIP_TESTS=true
                shift
                ;;
            --with-docker)
                INSTALL_DOCKER=true
                shift
                ;;
            --help)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  --production    Setup for production environment"
                echo "  --skip-tests    Skip running tests"
                echo "  --with-docker   Install Docker and Docker Compose"
                echo "  --help          Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    log_info "Setup type: $SETUP_TYPE"
    echo

    # Check prerequisites
    log_info "Checking prerequisites..."

    local prerequisites_ok=true

    if ! check_python_version; then
        prerequisites_ok=false
    fi

    if ! check_command "git"; then
        prerequisites_ok=false
    fi

    if [[ "$prerequisites_ok" == false ]]; then
        log_error "Prerequisites not met. Installing system dependencies..."
        install_system_dependencies

        # Check again
        if ! check_python_version; then
            log_error "Python installation failed. Please install Python 3.8+ manually and try again."
            exit 1
        fi
    fi

    # Setup steps
    setup_virtual_environment
    install_python_dependencies
    setup_environment_file
    create_directories

    # Database setup (only if environment is configured)
    if [[ -f "$ENV_FILE" ]]; then
        setup_database
    else
        log_warning "Skipping database setup. Configure .env file first."
    fi

    # Run tests unless skipped
    if [[ "$SKIP_TESTS" == false ]]; then
        run_tests
    fi

    # Docker setup if requested
    if [[ "$INSTALL_DOCKER" == true ]]; then
        log_info "Installing Docker..."
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            curl -fsSL https://get.docker.com -o get-docker.sh
            sudo sh get-docker.sh
            sudo usermod -aG docker $USER
            log_success "Docker installed. Please log out and back in to use Docker without sudo."
        else
            log_warning "Please install Docker manually for your operating system."
        fi
    fi

    show_usage_instructions
}

# Run main function
main "$@"
