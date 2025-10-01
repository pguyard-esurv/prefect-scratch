# Prefect RPA Solution

A collection of RPA (Robotic Process Automation) workflows built with Prefect.

## Flows

- **RPA1**: File processing and data transformation
- **RPA2**: Data validation and reporting
- **RPA3**: Concurrent data processing demo

## Getting Started

1. Install dependencies:
```bash
make install-dev
```

2. Set up development environment:
```bash
make setup-dev
```

3. Run flows:
```bash
make run-rpa1
make run-rpa2
make run-rpa3
```

## Docker Support

Each flow can be run in a Docker container. See `docker-compose.yml` for details.