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
from neo4j_driver import create_neo4j_driver

# Load environment variables
load_dotenv()


@asynccontextmanager
async def lifespan(mcp: FastMCP):
    # Initialize Neo4j driver with docker-compose configuration
    driver = await create_neo4j_driver()

    try:
        # Verify connection
        await driver.verify_connectivity()
        
        # Register all tools
        await register_create_entities(mcp, driver)
        await register_create_relations(mcp, driver)
        await register_delete_entities(mcp, driver)
        await register_introspect_schema(mcp, driver)
        await register_search_entities(mcp, driver)
        await register_update_entities(mcp, driver)
        
        # Initialize state dictionary
        mcp.state = {"driver": driver}
        print("Successfully connected to Neo4j")
        yield {"driver": driver}
    finally:
        # Close the driver when the server shuts down
        await driver.close()


def create_server():
    return FastMCP(lifespan=lifespan)


if __name__ == "__main__":
    print("Starting Neo4j MCP server with stdio transport")
    server = create_server()
    server.run(transport="stdio")
