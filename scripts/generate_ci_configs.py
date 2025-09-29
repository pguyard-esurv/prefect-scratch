#!/usr/bin/env python3
"""
CI/CD Configuration Generator

Generates CI/CD pipeline configurations for different platforms
(GitHub Actions, GitLab CI, Jenkins) based on the test automation pipeline.

Requirements: 9.5
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class CIConfigGenerator:
    """Generates CI/CD configurations for various platforms"""

    def __init__(self, config_file: str = None):
        self.config_file = config_file or "core/test/automation_pipeline_config.json"
        self.pipeline_config = self._load_pipeline_config()

    def _load_pipeline_config(self) -> dict[str, Any]:
        """Load pipeline configuration"""
        try:
            with open(self.config_file) as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load pipeline config: {e}")
            return {}

    def generate_github_actions(self, output_file: str = None) -> str:
        """Generate GitHub Actions workflow"""

        config = self.pipeline_config.get("ci_cd_integration", {}).get(
            "github_actions", {}
        )
        test_categories = self.pipeline_config.get("test_categories", {})

        workflow_name = config.get("workflow_name", "Container Testing Pipeline")
        schedule_cron = config.get("schedule_cron", "0 2 * * *")

        # Build test matrix
        test_matrix = []
        for category, cat_config in test_categories.items():
            if cat_config.get("enabled", True):
                test_matrix.append(
                    {
                        "name": category,
                        "markers": cat_config.get("markers", [category]),
                        "timeout": cat_config.get("timeout_seconds", 300),
                        "critical": cat_config.get("critical", False),
                    }
                )

        workflow = f"""name: {workflow_name}

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '{schedule_cron}'
  workflow_dispatch:
    inputs:
      test_mode:
        description: 'Test execution mode'
        required: false
        default: 'quick'
        type: choice
        options:
        - quick
        - full
        - chaos
        - performance

env:
  PYTHONPATH: ${{{{ github.workspace }}}}
  POSTGRES_PASSWORD: postgres
  POSTGRES_DB: test_db

jobs:
  setup:
    runs-on: ubuntu-latest
    outputs:
      test-matrix: ${{{{ steps.set-matrix.outputs.matrix }}}}
    steps:
    - name: Set test matrix
      id: set-matrix
      run: |
        echo 'matrix={json.dumps(test_matrix)}' >> $GITHUB_OUTPUT

  unit-tests:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ['3.11', '3.12']

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{{{ matrix.python-version }}}}
      uses: actions/setup-python@v4
      with:
        python-version: ${{{{ matrix.python-version }}}}

    - name: Cache dependencies
      uses: actions/cache@v3
      with:
        path: ~/.cache/pip
        key: ${{{{ runner.os }}}}-pip-${{{{ hashFiles('**/requirements.txt') }}}}
        restore-keys: |
          ${{{{ runner.os }}}}-pip-

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-xdist pytest-timeout pytest-asyncio

    - name: Run unit tests
      run: |
        python -m pytest core/test/ -m "unit" -v \\
          --cov=core --cov-report=xml --cov-report=html \\
          --junit-xml=unit-test-results.xml \\
          --timeout=120 -n auto

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unit-tests
        name: codecov-unit-${{{{ matrix.python-version }}}}

    - name: Upload test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: unit-test-results-${{{{ matrix.python-version }}}}
        path: |
          unit-test-results.xml
          htmlcov/

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests

    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-xdist pytest-timeout pytest-asyncio

    - name: Wait for PostgreSQL
      run: |
        until pg_isready -h localhost -p 5432; do
          echo "Waiting for PostgreSQL..."
          sleep 2
        done

    - name: Run integration tests
      run: |
        python -m pytest core/test/ -m "integration" -v \\
          --junit-xml=integration-test-results.xml \\
          --timeout=300
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db

    - name: Upload test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: integration-test-results
        path: integration-test-results.xml

  container-tests:
    runs-on: ubuntu-latest
    needs: integration-tests

    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-timeout pytest-asyncio docker

    - name: Run container tests
      run: |
        python -m pytest core/test/ -m "container" -v \\
          --junit-xml=container-test-results.xml \\
          --timeout=600
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db

    - name: Upload test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: container-test-results
        path: container-test-results.xml

  chaos-tests:
    runs-on: ubuntu-latest
    needs: container-tests
    if: github.event_name == 'schedule' || github.event.inputs.test_mode == 'chaos' || github.event.inputs.test_mode == 'full'

    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-timeout pytest-asyncio

    - name: Run chaos tests
      run: |
        python core/test/run_automation_pipeline.py --mode chaos --report
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db

    - name: Upload chaos test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: chaos-test-results
        path: test_reports/

  full-pipeline:
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests, container-tests]
    if: github.ref == 'refs/heads/main' || github.event.inputs.test_mode == 'full'

    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-xdist pytest-timeout pytest-asyncio

    - name: Run full automation pipeline
      run: |
        python core/test/run_automation_pipeline.py --mode full --report --report-formats json html summary
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db

    - name: Upload pipeline results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: full-pipeline-results
        path: |
          test_reports/
          test_results/

    - name: Publish test report
      uses: peaceiris/actions-gh-pages@v3
      if: github.ref == 'refs/heads/main'
      with:
        github_token: ${{{{ secrets.GITHUB_TOKEN }}}}
        publish_dir: ./test_reports
        destination_dir: test-reports

  performance-tests:
    runs-on: ubuntu-latest
    needs: container-tests
    if: github.event_name == 'schedule' || github.event.inputs.test_mode == 'performance' || github.event.inputs.test_mode == 'full'

    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-timeout pytest-asyncio

    - name: Run performance tests
      run: |
        python core/test/run_automation_pipeline.py --mode performance --report
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db

    - name: Upload performance results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: performance-test-results
        path: test_reports/

  security-scan:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        scan-type: 'fs'
        scan-ref: '.'
        format: 'sarif'
        output: 'trivy-results.sarif'

    - name: Upload Trivy scan results
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: 'trivy-results.sarif'

  notify:
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests, container-tests, chaos-tests, full-pipeline, performance-tests]
    if: always() && (failure() || cancelled())

    steps:
    - name: Notify on failure
      uses: 8398a7/action-slack@v3
      with:
        status: failure
        text: 'Container Testing Pipeline failed!'
      env:
        SLACK_WEBHOOK_URL: ${{{{ secrets.SLACK_WEBHOOK_URL }}}}
"""

        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(workflow)
            print(f"GitHub Actions workflow written to: {output_path}")

        return workflow

    def generate_gitlab_ci(self, output_file: str = None) -> str:
        """Generate GitLab CI configuration"""

        self.pipeline_config.get("ci_cd_integration", {}).get("gitlab_ci", {})

        gitlab_ci = """stages:
  - validate
  - test
  - chaos
  - performance
  - report
  - deploy

variables:
  POSTGRES_DB: test_db
  POSTGRES_USER: postgres
  POSTGRES_PASSWORD: postgres
  POSTGRES_HOST_AUTH_METHOD: trust
  PYTHONPATH: $CI_PROJECT_DIR

.test_template: &test_template
  image: python:3.11
  services:
    - postgres:13
  before_script:
    - python -m pip install --upgrade pip
    - pip install -r requirements.txt
    - pip install pytest pytest-cov pytest-xdist pytest-timeout pytest-asyncio
  variables:
    DATABASE_URL: postgresql://postgres:postgres@postgres:5432/test_db

validate:
  stage: validate
  image: python:3.11
  script:
    - python -m pip install --upgrade pip
    - pip install -r requirements.txt
    - python -c "from core.config import ConfigManager; print('Configuration validation passed')"
    - python -c "from core.test.test_automation_pipeline import AutomationPipeline; print('Pipeline imports successful')"
  only:
    - merge_requests
    - main
    - develop

unit_tests:
  <<: *test_template
  stage: test
  script:
    - python -m pytest core/test/ -m "unit" -v --cov=core --cov-report=xml --cov-report=html --junit-xml=unit-results.xml --timeout=120 -n auto
  artifacts:
    reports:
      junit: unit-results.xml
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
    paths:
      - htmlcov/
    expire_in: 1 week
  coverage: '/TOTAL.+ ([0-9]{1,3}%)/'

integration_tests:
  <<: *test_template
  stage: test
  script:
    - python -m pytest core/test/ -m "integration" -v --junit-xml=integration-results.xml --timeout=300
  artifacts:
    reports:
      junit: integration-results.xml
    expire_in: 1 week
  needs: ["unit_tests"]

container_tests:
  <<: *test_template
  stage: test
  image: docker:20.10.16
  services:
    - docker:20.10.16-dind
    - postgres:13
  before_script:
    - apk add --no-cache python3 py3-pip
    - python3 -m pip install --upgrade pip
    - pip install -r requirements.txt
    - pip install pytest pytest-timeout pytest-asyncio docker
  script:
    - python3 -m pytest core/test/ -m "container" -v --junit-xml=container-results.xml --timeout=600
  artifacts:
    reports:
      junit: container-results.xml
    expire_in: 1 week
  needs: ["integration_tests"]

distributed_tests:
  <<: *test_template
  stage: test
  script:
    - python -m pytest core/test/ -m "distributed" -v --junit-xml=distributed-results.xml --timeout=900
  artifacts:
    reports:
      junit: distributed-results.xml
    expire_in: 1 week
  needs: ["container_tests"]

chaos_tests:
  <<: *test_template
  stage: chaos
  script:
    - python core/test/run_automation_pipeline.py --mode chaos --report --report-formats json summary
  artifacts:
    paths:
      - test_reports/
    expire_in: 1 month
  needs: ["distributed_tests"]
  allow_failure: true
  only:
    - schedules
    - main
    - develop

performance_tests:
  <<: *test_template
  stage: performance
  script:
    - python core/test/run_automation_pipeline.py --mode performance --report --report-formats json summary
  artifacts:
    paths:
      - test_reports/
    expire_in: 1 month
  needs: ["distributed_tests"]
  allow_failure: true
  only:
    - schedules
    - main

end_to_end_tests:
  <<: *test_template
  stage: test
  script:
    - python -m pytest core/test/test_end_to_end_validation.py -v --junit-xml=e2e-results.xml --timeout=1800
  artifacts:
    reports:
      junit: e2e-results.xml
    expire_in: 1 week
  needs: ["container_tests"]
  only:
    - main
    - develop

full_pipeline:
  <<: *test_template
  stage: report
  script:
    - python core/test/run_automation_pipeline.py --mode full --report --report-formats json html summary
    - python core/test/run_automation_pipeline.py --analyze-trends --days-back 30
  artifacts:
    paths:
      - test_reports/
      - test_results/
    expire_in: 1 month
  needs: ["unit_tests", "integration_tests", "container_tests", "distributed_tests"]
  only:
    - main
    - develop

security_scan:
  stage: validate
  image:
    name: aquasec/trivy:latest
    entrypoint: [""]
  script:
    - trivy fs --format json --output trivy-report.json .
    - trivy fs --format table .
  artifacts:
    paths:
      - trivy-report.json
    expire_in: 1 week
  allow_failure: true

pages:
  stage: deploy
  script:
    - mkdir public
    - cp -r test_reports/* public/ 2>/dev/null || echo "No test reports to copy"
    - echo "Test reports deployed to GitLab Pages"
  artifacts:
    paths:
      - public
  only:
    - main
  needs: ["full_pipeline"]
"""

        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(gitlab_ci)
            print(f"GitLab CI configuration written to: {output_path}")

        return gitlab_ci

    def generate_jenkins_pipeline(self, output_file: str = None) -> str:
        """Generate Jenkins pipeline configuration"""

        jenkins_pipeline = """pipeline {
    agent any

    environment {
        POSTGRES_DB = 'test_db'
        POSTGRES_USER = 'postgres'
        POSTGRES_PASSWORD = 'postgres'
        PYTHONPATH = "${WORKSPACE}"
        DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/test_db'
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 2, unit: 'HOURS')
        timestamps()
    }

    triggers {
        cron('H 2 * * *')  // Daily at 2 AM
        pollSCM('H/15 * * * *')  // Poll every 15 minutes
    }

    stages {
        stage('Setup') {
            steps {
                echo 'Setting up test environment...'
                sh '''
                    python3 -m pip install --upgrade pip
                    pip install -r requirements.txt
                    pip install pytest pytest-cov pytest-xdist pytest-timeout pytest-asyncio
                '''
            }
        }

        stage('Validate') {
            steps {
                echo 'Validating configuration and imports...'
                sh '''
                    python3 -c "from core.config import ConfigManager; print('Configuration validation passed')"
                    python3 -c "from core.test.test_automation_pipeline import AutomationPipeline; print('Pipeline imports successful')"
                '''
            }
        }

        stage('Unit Tests') {
            steps {
                echo 'Running unit tests...'
                sh '''
                    python3 -m pytest core/test/ -m "unit" -v \\
                        --cov=core --cov-report=xml --cov-report=html \\
                        --junit-xml=unit-results.xml \\
                        --timeout=120 -n auto
                '''
            }
            post {
                always {
                    junit 'unit-results.xml'
                    publishCoverage adapters: [coberturaAdapter('coverage.xml')],
                                   sourceFileResolver: sourceFiles('STORE_LAST_BUILD')
                    publishHTML([
                        allowMissing: false,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'htmlcov',
                        reportFiles: 'index.html',
                        reportName: 'Coverage Report'
                    ])
                }
            }
        }

        stage('Integration Tests') {
            steps {
                echo 'Running integration tests...'
                sh '''
                    python3 -m pytest core/test/ -m "integration" -v \\
                        --junit-xml=integration-results.xml \\
                        --timeout=300
                '''
            }
            post {
                always {
                    junit 'integration-results.xml'
                }
            }
        }

        stage('Container Tests') {
            steps {
                echo 'Running container tests...'
                sh '''
                    python3 -m pytest core/test/ -m "container" -v \\
                        --junit-xml=container-results.xml \\
                        --timeout=600
                '''
            }
            post {
                always {
                    junit 'container-results.xml'
                }
            }
        }

        stage('Distributed Tests') {
            steps {
                echo 'Running distributed processing tests...'
                sh '''
                    python3 -m pytest core/test/ -m "distributed" -v \\
                        --junit-xml=distributed-results.xml \\
                        --timeout=900
                '''
            }
            post {
                always {
                    junit 'distributed-results.xml'
                }
            }
        }

        stage('End-to-End Tests') {
            when {
                anyOf {
                    branch 'main'
                    branch 'develop'
                }
            }
            steps {
                echo 'Running end-to-end validation tests...'
                sh '''
                    python3 -m pytest core/test/test_end_to_end_validation.py -v \\
                        --junit-xml=e2e-results.xml \\
                        --timeout=1800
                '''
            }
            post {
                always {
                    junit 'e2e-results.xml'
                }
            }
        }

        stage('Chaos Testing') {
            when {
                anyOf {
                    triggeredBy 'TimerTrigger'
                    branch 'main'
                }
            }
            steps {
                echo 'Running chaos testing scenarios...'
                script {
                    try {
                        sh '''
                            python3 core/test/run_automation_pipeline.py --mode chaos --report --report-formats json summary
                        '''
                    } catch (Exception e) {
                        currentBuild.result = 'UNSTABLE'
                        echo "Chaos tests failed: ${e.getMessage()}"
                    }
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'test_reports/**/*', allowEmptyArchive: true
                }
            }
        }

        stage('Performance Tests') {
            when {
                anyOf {
                    triggeredBy 'TimerTrigger'
                    branch 'main'
                }
            }
            steps {
                echo 'Running performance tests...'
                script {
                    try {
                        sh '''
                            python3 core/test/run_automation_pipeline.py --mode performance --report --report-formats json summary
                        '''
                    } catch (Exception e) {
                        currentBuild.result = 'UNSTABLE'
                        echo "Performance tests failed: ${e.getMessage()}"
                    }
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'test_reports/**/*', allowEmptyArchive: true
                }
            }
        }

        stage('Full Pipeline Report') {
            when {
                anyOf {
                    branch 'main'
                    branch 'develop'
                }
            }
            steps {
                echo 'Generating full pipeline report...'
                sh '''
                    python3 core/test/run_automation_pipeline.py --mode full --report --report-formats json html summary --output-dir=test_reports
                    python3 core/test/run_automation_pipeline.py --analyze-trends --days-back 30
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'test_reports/**/*', fingerprint: true
                    publishHTML([
                        allowMissing: false,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'test_reports',
                        reportFiles: '*.html',
                        reportName: 'Test Pipeline Report'
                    ])
                }
            }
        }

        stage('Security Scan') {
            steps {
                echo 'Running security scan...'
                script {
                    try {
                        sh '''
                            # Install trivy if not available
                            if ! command -v trivy &> /dev/null; then
                                echo "Trivy not installed, skipping security scan"
                                exit 0
                            fi

                            trivy fs --format json --output trivy-report.json .
                            trivy fs --format table .
                        '''
                    } catch (Exception e) {
                        currentBuild.result = 'UNSTABLE'
                        echo "Security scan failed: ${e.getMessage()}"
                    }
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'trivy-report.json', allowEmptyArchive: true
                }
            }
        }
    }

    post {
        always {
            echo 'Cleaning up workspace...'
            cleanWs()
        }

        success {
            echo 'Pipeline completed successfully!'
            script {
                if (env.BRANCH_NAME == 'main') {
                    emailext (
                        subject: "✅ Pipeline Success: ${env.JOB_NAME} - ${env.BUILD_NUMBER}",
                        body: "The container testing pipeline completed successfully.\\n\\nBuild: ${env.BUILD_URL}",
                        to: "${env.CHANGE_AUTHOR_EMAIL ?: 'team@example.com'}"
                    )
                }
            }
        }

        failure {
            echo 'Pipeline failed!'
            emailext (
                subject: "❌ Pipeline Failed: ${env.JOB_NAME} - ${env.BUILD_NUMBER}",
                body: "The container testing pipeline has failed.\\n\\nBuild: ${env.BUILD_URL}\\nConsole: ${env.BUILD_URL}console",
                to: "${env.CHANGE_AUTHOR_EMAIL ?: 'team@example.com'}"
            )
        }

        unstable {
            echo 'Pipeline completed with warnings!'
            emailext (
                subject: "⚠️ Pipeline Unstable: ${env.JOB_NAME} - ${env.BUILD_NUMBER}",
                body: "The container testing pipeline completed with warnings.\\n\\nBuild: ${env.BUILD_URL}",
                to: "${env.CHANGE_AUTHOR_EMAIL ?: 'team@example.com'}"
            )
        }
    }
}
"""

        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(jenkins_pipeline)
            print(f"Jenkins pipeline configuration written to: {output_path}")

        return jenkins_pipeline

    def generate_all_configs(self, output_dir: str = "./ci_configs"):
        """Generate all CI/CD configurations"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate GitHub Actions
        github_file = output_path / "github-actions.yml"
        self.generate_github_actions(str(github_file))

        # Generate GitLab CI
        gitlab_file = output_path / "gitlab-ci.yml"
        self.generate_gitlab_ci(str(gitlab_file))

        # Generate Jenkins
        jenkins_file = output_path / "Jenkinsfile"
        self.generate_jenkins_pipeline(str(jenkins_file))

        print(f"\\nAll CI/CD configurations generated in: {output_path}")
        print("Files created:")
        print(f"  - {github_file}")
        print(f"  - {gitlab_file}")
        print(f"  - {jenkins_file}")


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="Generate CI/CD configurations for container testing pipeline"
    )

    parser.add_argument(
        "platform",
        choices=["github", "gitlab", "jenkins", "all"],
        help="CI/CD platform to generate configuration for",
    )

    parser.add_argument(
        "--output", help="Output file path (for single platform) or directory (for all)"
    )

    parser.add_argument(
        "--config",
        default="core/test/automation_pipeline_config.json",
        help="Pipeline configuration file",
    )

    args = parser.parse_args()

    try:
        generator = CIConfigGenerator(args.config)

        if args.platform == "github":
            output_file = args.output or ".github/workflows/test-pipeline.yml"
            config = generator.generate_github_actions(output_file)
            if not args.output:
                print(config)

        elif args.platform == "gitlab":
            output_file = args.output or ".gitlab-ci.yml"
            config = generator.generate_gitlab_ci(output_file)
            if not args.output:
                print(config)

        elif args.platform == "jenkins":
            output_file = args.output or "Jenkinsfile"
            config = generator.generate_jenkins_pipeline(output_file)
            if not args.output:
                print(config)

        elif args.platform == "all":
            output_dir = args.output or "./ci_configs"
            generator.generate_all_configs(output_dir)

        print("\\n✅ CI/CD configuration generation completed successfully!")

    except Exception as e:
        print(f"❌ Error generating CI/CD configuration: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
