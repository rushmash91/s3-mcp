# S3 MCP Server and Client

This project implements an MCP server and client for creating S3 buckets using the AWS ACK controller.

## Prerequisites

- Python 3.10 or higher
- Kubernetes cluster with AWS ACK controller installed
- `kubectl` configured to access your cluster
- AWS credentials configured for ACK controller

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start the server:

```bash
python s3_server.py
```

3. In a separate terminal, run the client:

```bash
python s3_client.py
```

## Features

- Create S3 buckets with custom names
- Auto-generate bucket names if none provided
- Automatic retry with suffix if bucket name exists
- Uses AWS ACK controller for bucket creation

## Usage

The server exposes a single tool:

- `create_s3_bucket(name: Optional[str] = None, max_retries: int = 3)`: Creates an S3 bucket with the given name or generates a random one if not provided.
