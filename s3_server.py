from typing import Any
import subprocess
import tempfile
import random
import string
import logging
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn

# Initialize FastMCP server
mcp = FastMCP("s3-mcp", version="0.1.0",
              description="MCP server for S3 bucket creation using kubectl apply")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_random_name(prefix: str = "bucket") -> str:
    """Generate a random bucket name with given prefix."""
    suffix = ''.join(random.choices(
        string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}-{suffix}"


@mcp.tool()
async def create_s3_bucket(name: str = None, max_retries: int = 3) -> str:
    """Create an S3 bucket using kubectl apply.

    Args:
        name: Optional bucket name. If not provided, a random name will be generated.
        max_retries: Maximum number of retries if bucket name exists.
    """
    current_try = 0
    while current_try < max_retries:
        try:
            bucket_name = name if name else generate_random_name()
            if current_try > 0:
                bucket_name = f"{bucket_name}-{current_try}"

            # Create manifest content
            manifest = f"""apiVersion: s3.services.k8s.aws/v1alpha1
kind: Bucket
metadata:
  name: {bucket_name}
spec:
  name: {bucket_name}
"""
            # Write manifest to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
                tmp.write(manifest)
                tmp.flush()

                # First do a dry-run
                dry_run = subprocess.run(
                    ['kubectl', 'apply', '--dry-run=server', '-f', tmp.name],
                    capture_output=True, text=True, check=True
                )
                logger.info(f"Dry run output: {dry_run.stdout}")

                # If dry-run succeeds, do the actual apply
                result = subprocess.run(
                    ['kubectl', 'apply', '-f', tmp.name],
                    capture_output=True, text=True, check=True
                )

                return f"""Successfully validated and created bucket: {bucket_name}
Dry run output: {dry_run.stdout}
Apply output: {result.stdout}"""

        except subprocess.CalledProcessError as e:
            if "already exists" in e.stderr and current_try < max_retries - 1:
                current_try += 1
                continue
            return f"Error creating bucket: {e.stderr}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"

    return f"Failed to create bucket after {max_retries} attempts"


def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can serve the provided mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


if __name__ == "__main__":
    mcp_server = mcp._mcp_server

    import argparse

    parser = argparse.ArgumentParser(
        description='Run MCP SSE-based S3 bucket creation server using kubectl apply')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080,
                        help='Port to listen on')
    args = parser.parse_args()

    # Bind SSE request handling to MCP server
    starlette_app = create_starlette_app(mcp_server, debug=True)

    uvicorn.run(starlette_app, host=args.host, port=args.port)
