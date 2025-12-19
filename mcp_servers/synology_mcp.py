"""
Synology SSH MCP Server for Perun's BlackBook.

Provides tools for executing commands on a Synology NAS via SSH,
specifically designed for Docker container management.

Usage:
    python synology_mcp.py
"""

import asyncio
import subprocess
import json
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

# Configuration
SYNOLOGY_HOST = "XrisNYC@bearcave.tail1d5888.ts.net"
DOCKER_PATH = "/usr/local/bin/docker"
DOCKER_COMPOSE_PATH = "/usr/local/bin/docker-compose"
BLACKBOOK_DIR = "/volume1/docker/blackbook"

# Initialize MCP server
mcp = FastMCP("synology_mcp")


# =============================================================================
# Pydantic Input Models
# =============================================================================


class ShellCommandInput(BaseModel):
    """Input model for running shell commands on Synology."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    command: str = Field(
        ...,
        description="Shell command to execute on Synology (e.g., 'ls -la', 'cat /etc/hostname')",
        min_length=1,
        max_length=2000
    )
    working_directory: Optional[str] = Field(
        default=None,
        description="Working directory for command execution (e.g., '/volume1/docker/blackbook')"
    )


class DockerCommandInput(BaseModel):
    """Input model for Docker commands."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    command: str = Field(
        ...,
        description="Docker subcommand and arguments (e.g., 'ps', 'logs blackbook-app --tail 50', 'exec blackbook-db psql -U blackbook -c \"SELECT 1\"')",
        min_length=1,
        max_length=2000
    )


class DockerComposeCommandInput(BaseModel):
    """Input model for Docker Compose commands."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    command: str = Field(
        ...,
        description="Docker Compose subcommand and arguments (e.g., 'up -d --build', 'down', 'logs -f', 'restart app')",
        min_length=1,
        max_length=2000
    )
    compose_file: str = Field(
        default="docker-compose.prod.yml",
        description="Compose file to use (default: docker-compose.prod.yml)"
    )


class DockerLogsInput(BaseModel):
    """Input model for fetching Docker logs."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    container: str = Field(
        default="blackbook-app",
        description="Container name (default: blackbook-app)"
    )
    tail: int = Field(
        default=50,
        description="Number of lines to fetch from end of logs",
        ge=1,
        le=1000
    )


class DockerExecInput(BaseModel):
    """Input model for executing commands inside containers."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    container: str = Field(
        default="blackbook-app",
        description="Container name (default: blackbook-app)"
    )
    command: str = Field(
        ...,
        description="Command to execute inside container",
        min_length=1,
        max_length=2000
    )


class PostgresQueryInput(BaseModel):
    """Input model for executing PostgreSQL queries."""
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    
    query: str = Field(
        ...,
        description="SQL query to execute (e.g., 'SELECT COUNT(*) FROM persons')",
        min_length=1,
        max_length=5000
    )
    database: str = Field(
        default="perunsblackbook",
        description="Database name (default: perunsblackbook)"
    )


# =============================================================================
# Helper Functions
# =============================================================================


def run_ssh_command(command: str, working_dir: Optional[str] = None) -> dict:
    """
    Execute a command on Synology via SSH.
    
    Returns dict with 'success', 'stdout', 'stderr', 'returncode'.
    """
    if working_dir:
        full_command = f"cd {working_dir} && {command}"
    else:
        full_command = command
    
    try:
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", SYNOLOGY_HOST, full_command],
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Command timed out after 120 seconds",
            "returncode": -1
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1
        }


def format_result(result: dict) -> str:
    """Format command result for display."""
    output_parts = []
    
    if result["success"]:
        output_parts.append("✅ Command succeeded")
    else:
        output_parts.append(f"❌ Command failed (exit code: {result['returncode']})")
    
    if result["stdout"].strip():
        output_parts.append(f"\n**Output:**\n```\n{result['stdout'].strip()}\n```")
    
    if result["stderr"].strip():
        output_parts.append(f"\n**Errors:**\n```\n{result['stderr'].strip()}\n```")
    
    return "\n".join(output_parts)


# =============================================================================
# MCP Tools
# =============================================================================


@mcp.tool(
    name="synology_shell",
    annotations={
        "title": "Run Shell Command on Synology",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def synology_shell(params: ShellCommandInput) -> str:
    """
    Execute a shell command on the Synology NAS via SSH.
    
    Use this for general shell operations like listing files, reading configs,
    checking system status, etc. For Docker operations, use the specialized
    docker tools instead.
    
    Args:
        params: ShellCommandInput with command and optional working_directory
        
    Returns:
        str: Command output with success/failure status
    """
    result = run_ssh_command(params.command, params.working_directory)
    return format_result(result)


@mcp.tool(
    name="synology_docker",
    annotations={
        "title": "Run Docker Command on Synology",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False
    }
)
async def synology_docker(params: DockerCommandInput) -> str:
    """
    Execute a Docker command on the Synology NAS.
    
    Common commands:
    - 'ps' - List running containers
    - 'ps -a' - List all containers
    - 'images' - List images
    - 'logs <container> --tail 50' - View container logs
    - 'restart <container>' - Restart a container
    - 'stop <container>' - Stop a container
    - 'start <container>' - Start a container
    
    Args:
        params: DockerCommandInput with docker subcommand and arguments
        
    Returns:
        str: Docker command output with success/failure status
    """
    command = f"sudo {DOCKER_PATH} {params.command}"
    result = run_ssh_command(command)
    return format_result(result)


@mcp.tool(
    name="synology_docker_compose",
    annotations={
        "title": "Run Docker Compose Command on Synology",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False
    }
)
async def synology_docker_compose(params: DockerComposeCommandInput) -> str:
    """
    Execute a Docker Compose command for BlackBook on Synology.
    
    Common commands:
    - 'up -d --build' - Rebuild and restart containers
    - 'down' - Stop and remove containers
    - 'restart' - Restart all services
    - 'logs --tail 50' - View recent logs
    - 'ps' - List compose services
    
    Args:
        params: DockerComposeCommandInput with compose subcommand
        
    Returns:
        str: Docker Compose output with success/failure status
    """
    command = f"sudo {DOCKER_COMPOSE_PATH} -f {params.compose_file} {params.command}"
    result = run_ssh_command(command, BLACKBOOK_DIR)
    return format_result(result)


@mcp.tool(
    name="synology_docker_logs",
    annotations={
        "title": "Get Docker Container Logs",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def synology_docker_logs(params: DockerLogsInput) -> str:
    """
    Fetch logs from a Docker container on Synology.
    
    Useful for debugging application issues, checking startup status,
    and monitoring container health.
    
    Args:
        params: DockerLogsInput with container name and tail count
        
    Returns:
        str: Container logs with success/failure status
    """
    command = f"sudo {DOCKER_PATH} logs {params.container} --tail {params.tail}"
    result = run_ssh_command(command)
    return format_result(result)


@mcp.tool(
    name="synology_docker_exec",
    annotations={
        "title": "Execute Command in Docker Container",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False
    }
)
async def synology_docker_exec(params: DockerExecInput) -> str:
    """
    Execute a command inside a running Docker container.
    
    Useful for:
    - Running database queries via psql in blackbook-db
    - Checking application state inside blackbook-app
    - Running one-off maintenance commands
    
    Args:
        params: DockerExecInput with container name and command
        
    Returns:
        str: Command output with success/failure status
    """
    command = f"sudo {DOCKER_PATH} exec {params.container} {params.command}"
    result = run_ssh_command(command)
    return format_result(result)


@mcp.tool(
    name="synology_postgres_query",
    annotations={
        "title": "Execute PostgreSQL Query",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False
    }
)
async def synology_postgres_query(params: PostgresQueryInput) -> str:
    """
    Execute a PostgreSQL query on the BlackBook database.
    
    Runs the query via psql in the blackbook-db container.
    
    Common queries:
    - 'SELECT COUNT(*) FROM persons' - Count people
    - 'SELECT COUNT(*) FROM organizations' - Count orgs
    - 'SELECT COUNT(*) FROM tags' - Count tags
    - '\\dt' - List all tables
    - '\\d+ tablename' - Describe table structure
    
    Args:
        params: PostgresQueryInput with SQL query and database name
        
    Returns:
        str: Query results with success/failure status
    """
    # Escape single quotes in query for shell
    escaped_query = params.query.replace("'", "'\\''")
    command = f"sudo {DOCKER_PATH} exec blackbook-db psql -U blackbook -d {params.database} -c '{escaped_query}'"
    result = run_ssh_command(command)
    return format_result(result)


@mcp.tool(
    name="synology_blackbook_rebuild",
    annotations={
        "title": "Rebuild and Restart BlackBook",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def synology_blackbook_rebuild() -> str:
    """
    Rebuild and restart the BlackBook application on Synology.
    
    This is the standard deployment command that:
    1. Rebuilds the Docker image with latest code
    2. Restarts containers with the new image
    3. Maintains database data
    
    Use after making code changes to deploy updates.
    
    Returns:
        str: Deployment output with success/failure status
    """
    command = f"sudo {DOCKER_COMPOSE_PATH} -f docker-compose.prod.yml up -d --build"
    result = run_ssh_command(command, BLACKBOOK_DIR)
    return format_result(result)


@mcp.tool(
    name="synology_blackbook_status",
    annotations={
        "title": "Check BlackBook Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def synology_blackbook_status() -> str:
    """
    Check the status of BlackBook containers and health.
    
    Returns information about:
    - Container status (running/stopped)
    - Health check status
    - Resource usage
    
    Returns:
        str: Status information for all BlackBook containers
    """
    # Get container status
    status_cmd = f"sudo {DOCKER_PATH} ps -a --filter 'name=blackbook' --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'"
    status_result = run_ssh_command(status_cmd)
    
    output_parts = ["## BlackBook Container Status\n"]
    output_parts.append(format_result(status_result))
    
    # Get recent app logs
    logs_cmd = f"sudo {DOCKER_PATH} logs blackbook-app --tail 10"
    logs_result = run_ssh_command(logs_cmd)
    
    output_parts.append("\n## Recent App Logs (last 10 lines)\n")
    if logs_result["stdout"].strip():
        output_parts.append(f"```\n{logs_result['stdout'].strip()}\n```")
    elif logs_result["stderr"].strip():
        output_parts.append(f"```\n{logs_result['stderr'].strip()}\n```")
    
    return "\n".join(output_parts)


# =============================================================================
# Main Entry Point
# =============================================================================


if __name__ == "__main__":
    mcp.run()
