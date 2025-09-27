# Prefect RPA Solution

A modern, modular RPA (Robotic Process Automation) solution built with Prefect 3, featuring clean architecture, comprehensive testing, and production-ready workflows.

## 🚀 Features

- **Modular Design**: Separate workflow modules for different RPA tasks
- **Comprehensive Testing**: Unit tests for core business logic and integration tests for Prefect workflows
- **Clean Architecture**: Separation of concerns with testable, maintainable code
- **Production Ready**: Built with best practices for reliability and monitoring

## 📁 Project Structure

```
├── core/                    # Core functionality and shared tasks
│   ├── config.py           # Configuration settings
│   ├── tasks.py            # Prefect task definitions
│   └── test/               # Unit tests for core functionality
│       ├── test_config.py  # Configuration tests
│       └── test_tasks.py   # Task function tests
├── docs/                   # Documentation
│   ├── TESTING_STRATEGY.md # Comprehensive testing documentation
│   ├── MOCKING_STRATEGY.md # Mocking strategies for Prefect workflows
│   └── CONFIGURATION_SYSTEM.md # Environment and configuration management
├── flows/                  # RPA workflow modules
│   ├── rpa1/              # File processing workflows
│   │   ├── workflow.py    # RPA1 workflow definition
│   │   ├── data/          # RPA1 input data
│   │   │   └── sales_data.csv
│   │   ├── output/        # RPA1 generated reports
│   │   │   └── sales_report_*.json
│   │   └── test/          # RPA1 tests (unit + integration)
│   │       ├── test_workflow.py      # Unit tests
│   │       └── test_integration.py   # Integration tests
│   ├── rpa2/              # Data validation workflows
│   │   ├── workflow.py    # RPA2 workflow definition
│   │   ├── data/          # RPA2 input data
│   │   │   └── validation_data.json
│   │   ├── output/        # RPA2 generated reports
│   │   │   └── validation_report_*.json
│   │   └── test/          # RPA2 tests (unit + integration)
│   │       └── test_workflow.py      # Unit tests
│   └── rpa3/              # Concurrent processing workflows
│       ├── workflow.py    # RPA3 workflow definition
│       ├── data/          # RPA3 input data
│       │   └── customer_orders.csv
│       ├── output/        # RPA3 generated reports
│       │   └── fulfillment_report_*.json
│       └── test/          # RPA3 tests (unit + integration)
│           └── test_workflow.py      # Unit tests
├── conftest.py             # Pytest configuration and fixtures
└── main.py                # Main entry point
```

## 🛠️ Quick Start

### Prerequisites

- Python 3.9+
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd prefect_scratch
   ```

2. **Install dependencies**:
   ```bash
   make install-dev
   ```

3. **Activate virtual environment** (optional):
   ```bash
   make activate
   ```

### Running Workflows

```bash
# Run all RPA workflows
make run

# Run specific workflows
make run-rpa1    # File processing workflow
make run-rpa2    # Data validation workflow

# Run individual workflows directly
python main.py rpa1
python main.py rpa2
python main.py all
```

## 🧪 Testing

This project follows Prefect's recommended testing best practices with comprehensive coverage:

### Test Types

#### Unit Tests
Test individual components with real data and minimal mocking:

```bash
# Run all unit tests
make test-unit

# Run specific test modules
uv run pytest core/test/ -v
uv run pytest flows/rpa1/test/ -v
uv run pytest flows/rpa2/test/ -v
```

#### Integration Tests
Test complete workflows with Prefect's test harness:

```bash
# Run integration tests
make test-integration
```

#### Coverage Reports
Generate detailed coverage reports:

```bash
# Run tests with coverage
make test-coverage
```

### Test Strategy
- **Prefect Test Harness**: Uses `prefect_test_harness()` for proper test isolation
- **Logger Management**: Uses `disable_run_logger()` instead of mocking
- **Real Data Testing**: Tests use actual file I/O and data processing
- **Modular Testing**: Each component has focused test coverage
- **Integration Testing**: End-to-end workflow testing with real Prefect execution
- **Coverage Tracking**: 96% code coverage with detailed reporting

### Test Structure
- **Unit Tests**: `core/test/`, `flows/*/test/test_workflow.py` - Test individual functions
- **Integration Tests**: `flows/*/test/test_integration.py` - Test complete workflows
- **Test Fixtures**: `conftest.py` - Prefect test harness configuration
- **Coverage Reports**: `htmlcov/` - HTML coverage reports

📖 **For detailed testing information, see [TESTING_STRATEGY.md](docs/TESTING_STRATEGY.md)**  
📖 **For mocking strategies, see [MOCKING_STRATEGY.md](docs/MOCKING_STRATEGY.md)**  
📖 **For configuration management, see [CONFIGURATION_SYSTEM.md](docs/CONFIGURATION_SYSTEM.md)**

## 🔧 Development

### Available Commands

```bash
make help              # Show all available commands
make install-dev       # Install development dependencies
make test              # Run all tests
make test-unit         # Run unit tests only
make test-integration  # Run integration tests only
make test-coverage     # Run tests with coverage report
make test-watch        # Run tests in watch mode
make lint              # Run code linting
make format            # Format code
make clean             # Clean temporary files
make activate          # Show virtual environment activation instructions
```

### Code Quality

- **Linting**: Ruff for fast, modern Python linting
- **Formatting**: Consistent code style across the project
- **Type Hints**: Full type annotation support
- **Documentation**: Comprehensive docstrings and comments

## 📊 Workflows

### RPA1: File Processing
- **Purpose**: Process CSV sales data files
- **Features**: Data extraction, transformation, summary calculation, report generation
- **Output**: JSON sales reports with detailed analytics

### RPA2: Data Validation
- **Purpose**: Validate user data and generate validation reports
- **Features**: User data validation, error reporting, validation analytics
- **Output**: JSON validation reports with issue details

## 🏗️ Architecture

### Core Principles
1. **Testability**: All business logic is easily testable
2. **Modularity**: Clear separation between different RPA workflows
3. **Maintainability**: Clean, well-documented code
4. **Reliability**: Comprehensive error handling and logging

### Design Patterns
- **Task-Based Architecture**: Prefect tasks encapsulate business logic
- **Pure Function Testing**: Tasks tested as pure functions with minimal mocking
- **Configuration Management**: Centralized configuration with environment support
- **Error Handling**: Robust error handling with cleanup procedures

## 📈 Monitoring & Logging

- **Prefect Logging**: Integrated with Prefect's logging system
- **Task Monitoring**: Built-in task execution monitoring
- **Error Tracking**: Comprehensive error reporting and handling
- **Performance Metrics**: Task execution timing and success rates

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass: `make test`
6. Run linting: `make lint`
7. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For questions, issues, or contributions, please open an issue on the repository.