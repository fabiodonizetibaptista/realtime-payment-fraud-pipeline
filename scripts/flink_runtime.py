"""Shared runtime for reproducible Confluent Flink SQL operations.

Terraform State is the source of truth for the environment, Kafka cluster,
Compute Pool, cloud and region.

This module never prints Terraform State, credentials or CLI stderr.
"""

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


# Resolve the repository root from this file, not from the caller's CWD.
ROOT = Path(__file__).resolve().parents[1]


DELETE_WAIT_ATTEMPTS = 18   # 18 x 10 s = 3 min
DELETE_WAIT_SECONDS = 10


class FlinkRuntimeError(RuntimeError):
    """Safe error that does not expose command output or credentials."""


@dataclass(frozen=True)
class FlinkConfig:
    environment_id: str
    kafka_cluster_id: str
    compute_pool_id: str
    cloud: str
    region: str
    catalog_name: str | None = None
    database_name: str | None = None

    def common_flags(self):
        return [
            "--environment", self.environment_id,
            "--cloud", self.cloud,
            "--region", self.region,
        ]

    def query_flags(self):
        return [
            "--compute-pool", self.compute_pool_id,
            "--database", (self.database_name or self.kafka_cluster_id),
            *self.common_flags(),
        ]


def _safe_environment():
    """Preserve authentication environment without enabling debug logs."""
    env = dict(os.environ)
    env["TF_LOG"] = "OFF"
    env["TF_INPUT"] = "0"
    return env


def run_command(args, timeout=90, cwd=ROOT):
    """Execute a native command without exposing stdout/stderr."""
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            env=_safe_environment(),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FlinkRuntimeError(
            "FLINK_COMMAND_EXECUTION_FAILED"
        ) from None


def _resource_attributes(state, resource_type):
    """Extract exactly one managed Terraform resource instance."""
    instances = []

    for resource in state.get("resources", []):
        if (
            resource.get("mode") != "managed"
            or resource.get("type") != resource_type
        ):
            continue

        for instance in resource.get("instances", []):
            attributes = instance.get("attributes") or {}

            if isinstance(attributes, dict):
                instances.append(attributes)

    if len(instances) != 1:
        raise FlinkRuntimeError(
            "TERRAFORM_RESOURCE_REFERENCE_UNAVAILABLE"
        )

    return instances[0]


def load_config(command_runner=run_command):
    """Load Flink connection metadata from Terraform State."""
    result = command_runner(
        ["terraform", "state", "pull"],
        timeout=30,
        cwd=ROOT / "infra" / "terraform",
    )

    if result is None or result.returncode != 0:
        raise FlinkRuntimeError("TERRAFORM_STATE_UNAVAILABLE")

    try:
        state = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise FlinkRuntimeError("TERRAFORM_STATE_INVALID") from None

    if not isinstance(state, dict):
        raise FlinkRuntimeError("TERRAFORM_STATE_INVALID")

    environment = _resource_attributes(
        state, "confluent_environment"
    )
    cluster = _resource_attributes(
        state, "confluent_kafka_cluster"
    )
    pool = _resource_attributes(
        state, "confluent_flink_compute_pool"
    )

    values = {
        "environment_id": environment.get("id"),
        "kafka_cluster_id": cluster.get("id"),
        "compute_pool_id": pool.get("id"),
        "cloud": pool.get("cloud"),
        "region": pool.get("region"),
    }

    if any(
        not isinstance(value, str) or not value.strip()
        for value in values.values()
    ):
        raise FlinkRuntimeError(
            "FLINK_CONFIGURATION_INCOMPLETE"
        )

    return FlinkConfig(
        environment_id=values["environment_id"],
        kafka_cluster_id=values["kafka_cluster_id"],
        compute_pool_id=values["compute_pool_id"],
        cloud=values["cloud"].lower(),
        region=values["region"],
    )


class FlinkRuntime:
    """Shared interface for bounded queries and Flink statements."""

    def __init__(
        self,
        config,
        command_runner=run_command,
    ):
        self.config = config
        self.command_runner = command_runner

    @classmethod
    def from_terraform_state(cls):
        return cls(load_config())

    def _execute(self, args, timeout=90, operation="FLINK_OPERATION"):
        result = self.command_runner(
            args,
            timeout=timeout,
            cwd=ROOT,
        )

        if result is None or result.returncode != 0:
            return_code = (
                result.returncode if result is not None else "UNAVAILABLE"
            )
            raise FlinkRuntimeError(
                f"{operation}_FAILED_EXIT_{return_code}"
            )

        return result

    @staticmethod
    def _validate_statement(name, sql):
        if not isinstance(name, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,128}", name
        ):
            raise FlinkRuntimeError("INVALID_STATEMENT_NAME")

        if not isinstance(sql, str) or not sql.strip():
            raise FlinkRuntimeError("EMPTY_SQL_STATEMENT")

    def create_statement(self, name, sql, wait=True):
        """Submit a named Flink statement.

        The CLI --wait flag waits for RUNNING or FAILED, not necessarily
        for completion of a bounded statement. Call describe_statement
        to inspect its actual state.
        """
        self._validate_statement(name, sql)

        args = [
            "confluent",
            "flink",
            "statement",
            "create",
            name,
            "--sql",
            sql.strip(),
            *self.config.query_flags(),
        ]

        if wait:
            args.append("--wait")

        args.extend(["--output", "json"])

        self._execute(
            args,
            timeout=120,
            operation="FLINK_STATEMENT_CREATE",
        )

        return True

    def describe_statement(self, name):
        """Retrieve the state of a named Flink statement."""
        if not isinstance(name, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,128}", name
        ):
            raise FlinkRuntimeError("INVALID_STATEMENT_NAME")

        args = [
            "confluent",
            "flink",
            "statement",
            "describe",
            name,
            *self.config.common_flags(),
            "--output",
            "json",
        ]

        result = self._execute(
            args,
            timeout=45,
            operation="FLINK_STATEMENT_DESCRIBE",
        )

        try:
            data = json.loads(result.stdout)
        except (ValueError, TypeError):
            raise FlinkRuntimeError(
                "FLINK_STATEMENT_RESPONSE_INVALID"
            ) from None

        if not isinstance(data, dict):
            raise FlinkRuntimeError(
                "FLINK_STATEMENT_RESPONSE_INVALID"
            )

        return data


    @staticmethod
    def statement_phase(statement):
        """Extract a recognized lifecycle phase from CLI JSON."""
        recognized = {
            "PENDING", "PROVISIONING", "RUNNING",
            "COMPLETED", "FAILED", "STOPPED",
            "CANCELLED", "DELETING",
        }

        def visit(value):
            if isinstance(value, dict):
                for key in ("phase", "status", "state"):
                    candidate = value.get(key)

                    if isinstance(candidate, str):
                        phase = candidate.upper()
                        if phase in recognized:
                            return phase

                    if isinstance(candidate, dict):
                        found = visit(candidate)
                        if found:
                            return found

                for child in value.values():
                    found = visit(child)
                    if found:
                        return found

            elif isinstance(value, list):
                for child in value:
                    found = visit(child)
                    if found:
                        return found

            return None

        return visit(statement)

    def list_statements(self):
        """List statements belonging to the configured environment/pool."""
        args = [
            "confluent", "flink", "statement", "list",
            "--compute-pool", self.config.compute_pool_id,
            *self.config.common_flags(),
            "--output", "json",
        ]

        result = self._execute(
            args,
            timeout=45,
            operation="FLINK_STATEMENT_LIST",
        )

        try:
            data = json.loads(result.stdout)
        except (ValueError, TypeError):
            raise FlinkRuntimeError(
                "FLINK_STATEMENT_LIST_RESPONSE_INVALID"
            ) from None

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            for key in ("statements", "data", "results", "items"):
                if isinstance(data.get(key), list):
                    return data[key]

            if data.get("name"):
                return [data]

        raise FlinkRuntimeError(
            "FLINK_STATEMENT_LIST_RESPONSE_INVALID"
        )

    @staticmethod
    def statement_name(statement):
        metadata = statement.get("metadata") or {}
        spec = statement.get("spec") or {}
        return (
            statement.get("name")
            or metadata.get("name")
            or spec.get("name")
        )

    def find_statement(self, name):
        """Find a statement by its stable name."""
        for statement in self.list_statements():
            if self.statement_name(statement) == name:
                return statement

        return None

    def delete_statement(self, name):
        """Delete one statement by name (environment/cloud/region explicit)."""
        self._validate_statement(name, "-")
        self._execute(
            [
                "confluent", "flink", "statement", "delete", name,
                *self.config.common_flags(),
                "--force",
            ],
            timeout=60,
            operation="FLINK_STATEMENT_DELETE",
        )

    def delete_all_statements(self):
        """Delete every statement of the configured pool; return the count.

        Statements are not Terraform resources: a forgotten continuous
        statement keeps consuming CFUs, and teardown must not depend on a
        manual CLI loop (run-20261111 needed one for 44 statements).
        """
        names = [
            self.statement_name(statement)
            for statement in self.list_statements()
        ]
        names = [name for name in names if name]
        for name in names:
            try:
                self.delete_statement(name)
            except FlinkRuntimeError:
                # Pode ja estar sendo removido; a espera abaixo decide.
                pass

        # A remocao na Confluent e assincrona: o statement continua listado
        # por alguns segundos (na execucao guiada, 35 statements ainda
        # apareciam logo apos o delete). Espera a lista esvaziar.
        import time

        sleep = getattr(self, "sleep", time.sleep)
        remaining = self.list_statements()
        for _ in range(DELETE_WAIT_ATTEMPTS):
            if not remaining:
                return len(names)
            sleep(DELETE_WAIT_SECONDS)
            remaining = self.list_statements()
        if remaining:
            raise FlinkRuntimeError(
                f"FLINK_STATEMENTS_REMAIN_AFTER_DELETE_{len(remaining)}"
            )
        return len(names)

    def wait_for_statement(
        self,
        name,
        timeout=120,
        poll_interval=2,
        clock=None,
        sleep=None,
    ):
        """Wait for a statement to reach COMPLETED or a failure state."""
        clock = clock or time.monotonic
        sleep = sleep or time.sleep
        deadline = clock() + timeout

        while True:
            statement = self.describe_statement(name)
            phase = self.statement_phase(statement)

            if phase == "COMPLETED":
                return statement

            if phase in {"FAILED", "STOPPED", "CANCELLED"}:
                raise FlinkRuntimeError(
                    f"FLINK_STATEMENT_TERMINAL_{phase}"
                )

            if phase not in {"PENDING", "PROVISIONING", "RUNNING"}:
                raise FlinkRuntimeError(
                    "FLINK_STATEMENT_PHASE_UNRECOGNIZED"
                )

            if clock() >= deadline:
                raise FlinkRuntimeError(
                    "FLINK_STATEMENT_WAIT_TIMEOUT"
                )

            sleep(poll_interval)

    def query(self, sql, timeout=35):
        """Execute a bounded query and return its JSON rows."""
        if not isinstance(sql, str) or not sql.strip():
            raise FlinkRuntimeError("EMPTY_SQL_QUERY")

        args = [
            "confluent",
            "flink",
            "query",
            "--sql",
            sql.strip(),
            *self.config.query_flags(),
            "--timeout",
            f"{timeout}s",
            "--output",
            "json",
        ]

        result = self._execute(
            args,
            timeout=timeout + 15,
            operation="FLINK_BOUNDED_QUERY",
        )

        try:
            data = json.loads(result.stdout)
        except (ValueError, TypeError):
            raise FlinkRuntimeError(
                "FLINK_QUERY_RESPONSE_INVALID"
            ) from None

        if not isinstance(data, list):
            raise FlinkRuntimeError(
                "FLINK_QUERY_RESPONSE_INVALID"
            )

        return data
