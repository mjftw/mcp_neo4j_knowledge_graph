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

## Configuration

### Claude Desktop Configuration

For Ubuntu users running Claude Desktop, you can configure the MCP server by adding it to your Claude desktop configuration file at:
```
~/.config/Claude/claude_desktop_config.json
```

An example configuration is provided in `example_mcp_config.json`. You can copy and modify this file:

```bash
cp example_mcp_config.json ~/.config/Claude/claude_desktop_config.json
```

The configuration includes:
- Server name and description
- Command to start the server
- Available tools and their parameters
- Required fields and data types

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

### 3. Search Entities
Searches for entities in the knowledge graph with fuzzy matching support.

Example input:
```json
{
    "search_term": "John",
    "entity_type": "Person",
    "properties": ["name", "occupation"],
    "include_relationships": true,
    "fuzzy_match": true
}
```

### 4. Update Entities
Updates existing entities in the knowledge graph.

Example input:
```json
{
    "updates": [{
        "id": "John Doe",
        "properties": {
            "occupation": "Senior Developer"
        },
        "remove_properties": ["temp_field"],
        "add_labels": ["Verified"],
        "remove_labels": ["Pending"]
    }]
}
```

### 5. Delete Entities
Deletes entities from the knowledge graph with optional cascade deletion of relationships.

Example input:
```json
{
    "entity_ids": ["John Doe", "Jane Smith"],
    "cascade": false,
    "dry_run": true
}
```

### 6. Introspect Schema
Retrieves information about the Neo4j database schema, including node labels and relationship types.

Example input:
```json
{}
```

## Testing

### Test Scripts

The project includes several test scripts for different aspects of the system:

1. `src/test_mcp_client.py` - Tests the MCP client functionality
   - Verifies server startup
   - Tests tool listing
   - Tests schema introspection
   - Tests entity creation
   ```bash
   task test-client  # Run just the client test
   ```

2. `src/test_mcp_config.py` - Tests the MCP configuration
   - Validates configuration file loading
   - Tests server connection using the official MCP SDK
   - Verifies all required tools are available
   ```bash
   task test-config  # Run just the config test
   ```

3. `src/test_neo4j_connection.py` - Tests the Neo4j database connection
   - Verifies database connectivity
   - Tests basic query functionality
   - Checks environment configuration
   ```bash
   task test-db  # Run just the database test
   ```

### Running Tests

You can run the tests in several ways:

1. Run all tests together:
   ```bash
   task test  # Runs all tests including pytest and integration tests
   ```

2. Run individual test types:
   ```bash
   task test-client    # Run MCP client test
   task test-config    # Run MCP config test
   task test-db        # Run Neo4j connection test
   task test-integration  # Run integration tests
   ```

3. Run tests with pytest directly:
   ```bash
   poetry run pytest  # Run all pytest-compatible tests
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
task test

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
- Schema validation errors
- Relationship creation failures
- Entity update conflicts

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
- `task test` - Run all tests
- `task test-client` - Run MCP client tests
- `task test-config` - Run MCP config tests
- `task test-db` - Run database tests
- `task test-integration` - Run integration tests
- `task down` - Stop all Docker services
- `task format` - Format code using black and isort
- `task lint` - Run flake8 linter
- `task help` - Show detailed help for all tasks 