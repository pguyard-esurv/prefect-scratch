#!/usr/bin/env python3
"""
Development Debugging Toolkit for Container Testing System

Provides comprehensive debugging access tools for logs, database inspection,
container internals, and development workflow optimization.

Requirements: 4.6, 4.7, 5.4
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import docker
import psycopg2
from psycopg2.extras import RealDictCursor


class ContainerDebugger:
    """Provides debugging access to container internals and logs"""

    def __init__(self):
        self.docker_client = docker.from_env()
        self.logger = logging.getLogger(__name__)

    def list_containers(self, filter_prefix: str = "rpa-") -> list[dict]:
        """List all containers with their status and basic info"""
        containers = []

        try:
            for container in self.docker_client.containers.list(all=True):
                if container.name.startswith(filter_prefix):
                    containers.append(
                        {
                            "name": container.name,
                            "status": container.status,
                            "image": (
                                container.image.tags[0]
                                if container.image.tags
                                else "unknown"
                            ),
                            "created": container.attrs["Created"],
                            "ports": container.ports,
                            "labels": container.labels,
                            "id": container.short_id,
                        }
                    )
        except Exception as e:
            self.logger.error(f"Error listing containers: {e}")

        return containers

    def get_container_logs(
        self, container_name: str, lines: int = 100, follow: bool = False
    ) -> str:
        """Get logs from a specific container"""
        try:
            container = self.docker_client.containers.get(container_name)

            if follow:
                # Stream logs in real-time
                for line in container.logs(stream=True, follow=True, tail=lines):
                    print(line.decode("utf-8").strip())
            else:
                logs = container.logs(tail=lines).decode("utf-8")
                return logs

        except docker.errors.NotFound:
            return f"Container {container_name} not found"
        except Exception as e:
            return f"Error getting logs: {e}"

    def exec_in_container(self, container_name: str, command: list[str]) -> dict:
        """Execute a command inside a container"""
        try:
            container = self.docker_client.containers.get(container_name)

            result = container.exec_run(command, stdout=True, stderr=True)

            return {
                "exit_code": result.exit_code,
                "output": result.output.decode("utf-8"),
                "command": " ".join(command),
            }

        except docker.errors.NotFound:
            return {"error": f"Container {container_name} not found"}
        except Exception as e:
            return {"error": f"Error executing command: {e}"}

    def get_container_stats(self, container_name: str) -> dict:
        """Get real-time stats for a container"""
        try:
            container = self.docker_client.containers.get(container_name)

            stats = container.stats(stream=False)

            # Calculate CPU percentage
            cpu_delta = (
                stats["cpu_stats"]["cpu_usage"]["total_usage"]
                - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            )
            system_delta = (
                stats["cpu_stats"]["system_cpu_usage"]
                - stats["precpu_stats"]["system_cpu_usage"]
            )

            cpu_percent = 0.0
            if system_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * 100.0

            # Calculate memory usage
            memory_usage = stats["memory_stats"]["usage"]
            memory_limit = stats["memory_stats"]["limit"]
            memory_percent = (memory_usage / memory_limit) * 100.0

            return {
                "container": container_name,
                "cpu_percent": round(cpu_percent, 2),
                "memory_usage_mb": round(memory_usage / 1024 / 1024, 2),
                "memory_limit_mb": round(memory_limit / 1024 / 1024, 2),
                "memory_percent": round(memory_percent, 2),
                "network_rx_bytes": stats["networks"]["rpa-bridge"]["rx_bytes"],
                "network_tx_bytes": stats["networks"]["rpa-bridge"]["tx_bytes"],
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            return {"error": f"Error getting stats: {e}"}

    def inspect_container(self, container_name: str) -> dict:
        """Get detailed container inspection information"""
        try:
            container = self.docker_client.containers.get(container_name)
            return container.attrs

        except docker.errors.NotFound:
            return {"error": f"Container {container_name} not found"}
        except Exception as e:
            return {"error": f"Error inspecting container: {e}"}


class DatabaseDebugger:
    """Provides debugging access to database connections and data"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.logger = logging.getLogger(__name__)

    def test_connection(self) -> dict:
        """Test database connection and return status"""
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor()

            # Test basic query
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]

            # Get database size
            cursor.execute(
                """
                SELECT pg_size_pretty(pg_database_size(current_database())) as size;
            """
            )
            db_size = cursor.fetchone()[0]

            # Get connection count
            cursor.execute(
                """
                SELECT count(*) FROM pg_stat_activity
                WHERE datname = current_database();
            """
            )
            connection_count = cursor.fetchone()[0]

            cursor.close()
            conn.close()

            return {
                "status": "connected",
                "version": version,
                "database_size": db_size,
                "active_connections": connection_count,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def get_table_info(self) -> list[dict]:
        """Get information about all tables in the database"""
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute(
                """
                SELECT
                    schemaname,
                    tablename,
                    tableowner,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_stat_get_tuples_returned(c.oid) as rows_read,
                    pg_stat_get_tuples_inserted(c.oid) as rows_inserted,
                    pg_stat_get_tuples_updated(c.oid) as rows_updated,
                    pg_stat_get_tuples_deleted(c.oid) as rows_deleted
                FROM pg_tables pt
                JOIN pg_class c ON c.relname = pt.tablename
                WHERE schemaname NOT IN ('information_schema', 'pg_catalog')
                ORDER BY schemaname, tablename;
            """
            )

            tables = cursor.fetchall()
            cursor.close()
            conn.close()

            return [dict(table) for table in tables]

        except Exception as e:
            self.logger.error(f"Error getting table info: {e}")
            return []

    def get_recent_activity(self, limit: int = 50) -> list[dict]:
        """Get recent database activity"""
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute(
                """
                SELECT
                    pid,
                    usename,
                    application_name,
                    client_addr,
                    backend_start,
                    query_start,
                    state,
                    LEFT(query, 100) as query_preview
                FROM pg_stat_activity
                WHERE datname = current_database()
                AND state IS NOT NULL
                ORDER BY query_start DESC NULLS LAST
                LIMIT %s;
            """,
                (limit,),
            )

            activities = cursor.fetchall()
            cursor.close()
            conn.close()

            return [dict(activity) for activity in activities]

        except Exception as e:
            self.logger.error(f"Error getting recent activity: {e}")
            return []

    def run_query(self, query: str, params: Optional[tuple] = None) -> dict:
        """Execute a custom query and return results"""
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            start_time = time.time()
            cursor.execute(query, params)
            execution_time = time.time() - start_time

            if cursor.description:
                results = cursor.fetchall()
                return {
                    "status": "success",
                    "rows": [dict(row) for row in results],
                    "row_count": len(results),
                    "execution_time_ms": round(execution_time * 1000, 2),
                    "query": query,
                }
            else:
                return {
                    "status": "success",
                    "message": "Query executed successfully (no results)",
                    "execution_time_ms": round(execution_time * 1000, 2),
                    "query": query,
                }

        except Exception as e:
            return {"status": "error", "error": str(e), "query": query}
        finally:
            if "cursor" in locals():
                cursor.close()
            if "conn" in locals():
                conn.close()


class LogAnalyzer:
    """Analyzes and aggregates logs from multiple sources"""

    def __init__(self, log_directory: str = "./logs"):
        self.log_directory = Path(log_directory)
        self.logger = logging.getLogger(__name__)

    def get_log_files(self) -> list[dict]:
        """Get list of all log files with metadata"""
        log_files = []

        try:
            for log_file in self.log_directory.rglob("*.log"):
                stat = log_file.stat()
                log_files.append(
                    {
                        "path": str(log_file),
                        "relative_path": str(log_file.relative_to(self.log_directory)),
                        "size_bytes": stat.st_size,
                        "size_mb": round(stat.st_size / 1024 / 1024, 2),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    }
                )
        except Exception as e:
            self.logger.error(f"Error getting log files: {e}")

        return sorted(log_files, key=lambda x: x["modified"], reverse=True)

    def tail_log(self, log_path: str, lines: int = 100) -> list[str]:
        """Get the last N lines from a log file"""
        try:
            full_path = self.log_directory / log_path

            if not full_path.exists():
                return [f"Log file {log_path} not found"]

            with open(full_path) as f:
                return f.readlines()[-lines:]

        except Exception as e:
            return [f"Error reading log file: {e}"]

    def search_logs(
        self,
        pattern: str,
        log_path: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """Search for a pattern in log files"""
        results = []

        try:
            if log_path:
                log_files = [self.log_directory / log_path]
            else:
                log_files = list(self.log_directory.rglob("*.log"))

            for log_file in log_files:
                if not log_file.exists():
                    continue

                with open(log_file) as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern.lower() in line.lower():
                            results.append(
                                {
                                    "file": str(
                                        log_file.relative_to(self.log_directory)
                                    ),
                                    "line_number": line_num,
                                    "content": line.strip(),
                                    "timestamp": self._extract_timestamp(line),
                                }
                            )

        except Exception as e:
            self.logger.error(f"Error searching logs: {e}")

        return results

    def _extract_timestamp(self, line: str) -> Optional[str]:
        """Extract timestamp from log line (basic implementation)"""
        import re

        # Common timestamp patterns
        patterns = [
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
        ]

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                return match.group()

        return None


class DevelopmentDashboard:
    """Provides a unified dashboard for development debugging"""

    def __init__(self):
        self.container_debugger = ContainerDebugger()
        self.log_analyzer = LogAnalyzer()

        # Database connections
        self.rpa_db = DatabaseDebugger(
            "postgresql://rpa_user:rpa_dev_password@localhost:5432/rpa_db"
        )

        self.logger = logging.getLogger(__name__)

    def generate_status_report(self) -> dict:
        """Generate a comprehensive status report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "containers": self.container_debugger.list_containers(),
            "database": {
                "rpa_db": self.rpa_db.test_connection(),
                "tables": self.rpa_db.get_table_info(),
                "recent_activity": self.rpa_db.get_recent_activity(10),
            },
            "logs": {
                "files": self.log_analyzer.get_log_files(),
                "recent_errors": self.log_analyzer.search_logs(
                    "error", since=datetime.now() - timedelta(hours=1)
                ),
            },
        }

        return report

    def monitor_containers(self, interval: int = 5, duration: int = 60):
        """Monitor container stats in real-time"""
        containers = [c["name"] for c in self.container_debugger.list_containers()]

        print(f"Monitoring {len(containers)} containers for {duration} seconds...")
        print("Press Ctrl+C to stop\n")

        start_time = time.time()

        try:
            while time.time() - start_time < duration:
                print(f"\n--- {datetime.now().strftime('%H:%M:%S')} ---")

                for container_name in containers:
                    stats = self.container_debugger.get_container_stats(container_name)

                    if "error" not in stats:
                        print(
                            f"{container_name:20} | "
                            f"CPU: {stats['cpu_percent']:6.1f}% | "
                            f"Memory: {stats['memory_usage_mb']:6.1f}MB "
                            f"({stats['memory_percent']:5.1f}%)"
                        )

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\nMonitoring stopped.")


def main():
    """Main CLI interface for the debugging toolkit"""
    parser = argparse.ArgumentParser(description="Development Debugging Toolkit")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Container commands
    container_parser = subparsers.add_parser("containers", help="Container debugging")
    container_parser.add_argument(
        "action", choices=["list", "logs", "stats", "exec", "inspect"]
    )
    container_parser.add_argument("--name", help="Container name")
    container_parser.add_argument(
        "--lines", type=int, default=100, help="Number of log lines"
    )
    container_parser.add_argument("--follow", action="store_true", help="Follow logs")
    container_parser.add_argument("--command", help="Command to execute")

    # Database commands
    db_parser = subparsers.add_parser("database", help="Database debugging")
    db_parser.add_argument("action", choices=["test", "tables", "activity", "query"])
    db_parser.add_argument("--query", help="SQL query to execute")
    db_parser.add_argument(
        "--db", default="rpa", choices=["rpa", "prefect"], help="Database to connect to"
    )

    # Log commands
    log_parser = subparsers.add_parser("logs", help="Log analysis")
    log_parser.add_argument("action", choices=["list", "tail", "search"])
    log_parser.add_argument("--file", help="Log file path")
    log_parser.add_argument("--lines", type=int, default=100, help="Number of lines")
    log_parser.add_argument("--pattern", help="Search pattern")

    # Dashboard commands
    dashboard_parser = subparsers.add_parser("dashboard", help="Development dashboard")
    dashboard_parser.add_argument("action", choices=["status", "monitor"])
    dashboard_parser.add_argument(
        "--interval", type=int, default=5, help="Monitor interval"
    )
    dashboard_parser.add_argument(
        "--duration", type=int, default=60, help="Monitor duration"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        if args.command == "containers":
            debugger = ContainerDebugger()

            if args.action == "list":
                containers = debugger.list_containers()
                print(json.dumps(containers, indent=2))

            elif args.action == "logs":
                if not args.name:
                    print("Error: --name required for logs command")
                    return

                logs = debugger.get_container_logs(args.name, args.lines, args.follow)
                if not args.follow:
                    print(logs)

            elif args.action == "stats":
                if not args.name:
                    print("Error: --name required for stats command")
                    return

                stats = debugger.get_container_stats(args.name)
                print(json.dumps(stats, indent=2))

            elif args.action == "exec":
                if not args.name or not args.command:
                    print("Error: --name and --command required for exec")
                    return

                result = debugger.exec_in_container(args.name, args.command.split())
                print(json.dumps(result, indent=2))

            elif args.action == "inspect":
                if not args.name:
                    print("Error: --name required for inspect command")
                    return

                info = debugger.inspect_container(args.name)
                print(json.dumps(info, indent=2))

        elif args.command == "database":
            if args.db == "rpa":
                db = DatabaseDebugger(
                    "postgresql://rpa_user:rpa_dev_password@localhost:5432/rpa_db"
                )
            else:
                db = DatabaseDebugger(
                    "postgresql://prefect_user:prefect_dev_password@localhost:5432/prefect_db"
                )

            if args.action == "test":
                result = db.test_connection()
                print(json.dumps(result, indent=2))

            elif args.action == "tables":
                tables = db.get_table_info()
                print(json.dumps(tables, indent=2))

            elif args.action == "activity":
                activity = db.get_recent_activity()
                print(json.dumps(activity, indent=2))

            elif args.action == "query":
                if not args.query:
                    print("Error: --query required for query command")
                    return

                result = db.run_query(args.query)
                print(json.dumps(result, indent=2))

        elif args.command == "logs":
            analyzer = LogAnalyzer()

            if args.action == "list":
                files = analyzer.get_log_files()
                print(json.dumps(files, indent=2))

            elif args.action == "tail":
                if not args.file:
                    print("Error: --file required for tail command")
                    return

                lines = analyzer.tail_log(args.file, args.lines)
                for line in lines:
                    print(line.rstrip())

            elif args.action == "search":
                if not args.pattern:
                    print("Error: --pattern required for search command")
                    return

                results = analyzer.search_logs(args.pattern, args.file)
                print(json.dumps(results, indent=2))

        elif args.command == "dashboard":
            dashboard = DevelopmentDashboard()

            if args.action == "status":
                report = dashboard.generate_status_report()
                print(json.dumps(report, indent=2))

            elif args.action == "monitor":
                dashboard.monitor_containers(args.interval, args.duration)

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
