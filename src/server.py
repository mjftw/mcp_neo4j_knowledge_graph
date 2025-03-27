import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from neo4j import AsyncGraphDatabase

# Import tool registration functions
from tools.create_entities import register as register_create_entities
from tools.create_relations import register as register_create_relations
from tools.delete_entities import register as register_delete_entities
from tools.introspect_schema import register as register_introspect_schema
from tools.search_entities import register as register_search_entities
from tools.update_entities import register as register_update_entities

# Load environment variables
load_dotenv()


@asynccontextmanager
async def lifespan(mcp: FastMCP):
    # Initialize Neo4j driver with docker-compose configuration
    driver = AsyncGraphDatabase.driver(
        "neo4j://localhost:7687",  # Bolt port from docker-compose
        auth=("neo4j", "password"),  # Auth from NEO4J_AUTH in docker-compose
    )

    try:
        # Verify connection
        await driver.verify_connectivity()
        mcp.state = {"driver": driver}  # Initialize state dictionary
        print("Successfully connected to Neo4j")
        yield {"driver": driver}
    finally:
        # Close the driver when the server shuts down
        await driver.close()


def create_server():
    mcp = FastMCP(lifespan=lifespan)

    driver = AsyncGraphDatabase.driver(
        "neo4j://localhost:7687",  # Bolt port from docker-compose
        auth=("neo4j", "password"),  # Auth from NEO4J_AUTH in docker-compose
    )

    # Register all tools
    asyncio.run(register_create_entities(mcp, driver))
    asyncio.run(register_create_relations(mcp, driver))
    asyncio.run(register_delete_entities(mcp, driver))
    asyncio.run(register_introspect_schema(mcp, driver))
    asyncio.run(register_search_entities(mcp, driver))
    asyncio.run(register_update_entities(mcp, driver))

    return mcp


if __name__ == "__main__":
    print("Starting Neo4j MCP server with stdio transport")
    server = create_server()
    server.run(transport="stdio")
