# Neo4j MCP Server

This is a Memory Control Protocol (MCP) server implementation that uses Neo4j as the backend storage for knowledge graph management. It provides a stdio-based interface for storing and retrieving knowledge in a graph database format.

## Prerequisites

- Python 3.8+
- Neo4j Database (local or remote)
- Poetry (Python package manager)
- Docker and Docker Compose (for running Neo4j)
- Go Task (optional, for task automation)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd neo4j_mcp_server
```

2. Install Poetry if you haven't already:
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

3. Install dependencies:
```bash
poetry install
```

## Running the Server

### Using Task (Recommended)

If you have Go Task installed, you can use the provided Taskfile to manage the server:

```bash
# Show available tasks
task

# Start everything (Docker + Server)
task run

# Start development environment (Docker + Server + Test)
task dev

# Stop all services
task down
```

### Using Docker Compose directly

1. Start the Neo4j container:
```bash
docker-compose up -d
```

2. Wait for Neo4j to be ready (the container will show as "healthy" in `docker ps`)

### Running the MCP Server directly

Start the server with:
```bash
poetry run python src/server.py
```

The server will start in stdio mode, ready to accept MCP protocol messages.

## Testing

### Using Task

Run the test client:
```bash
task test
```

### Running directly

Run the test client:
```bash
poetry run python src/test_mcp_client.py
```

This will:
1. Start the MCP server
2. List available tools
3. Test creating an entity in the knowledge graph

## Available Tools

### 1. Create Entities
Creates new entities in the knowledge graph.

Example input:
```json
{
    "entities": [{
        "type": "Person",
        "properties": {
            "name": "John Doe",
            "occupation": "Developer"
        }
    }],
    "context": {}
}
```

### 2. Create Relations
Creates relationships between existing entities.

Example input:
```json
{
    "relations": [{
        "type": "KNOWS",
        "from": "John Doe",
        "to": "Jane Smith"
    }]
}
```

## Development

### Using Task

The project includes several development tasks:

```bash
# Format code
task format

# Run linter
task lint

# Run tests
task test-all

# Start development environment
task dev
```

### Running directly

This project uses several development tools that are automatically installed with Poetry:

- `black` for code formatting
- `isort` for import sorting
- `flake8` for linting
- `pytest` for testing

You can run these tools using Poetry:

```bash
# Format code
poetry run black .

# Sort imports
poetry run isort .

# Run linter
poetry run flake8

# Run tests
poetry run pytest
```

## Error Handling

The server includes comprehensive error handling for:
- Database connection issues
- Invalid queries
- Missing nodes
- Invalid request formats

All errors are returned with appropriate error messages in the MCP protocol format.

## Docker Configuration

The Neo4j container is configured with the following settings:
- Ports: 7474 (HTTP) and 7687 (Bolt)
- Default credentials: neo4j/password
- APOC plugin enabled
- File import/export enabled
- Health check configured

You can modify these settings in the `docker-compose.yml` file.

## Task Commands Reference

- `task` - Show available tasks
- `task run` - Start Docker and MCP server
- `task dev` - Start development environment (Docker + Server + Test)
- `task docker` - Start Neo4j database
- `task server` - Run the MCP server
- `task test` - Run the test client
- `task down` - Stop all Docker services
- `task format` - Format code using black and isort
- `task lint` - Run flake8 linter
- `task test-all` - Run all tests
- `task help` - Show detailed help for all tasks 