from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, List
from mcp.server.fastmcp import FastMCP
from neo4j import AsyncGraphDatabase
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

@asynccontextmanager
async def lifespan(mcp: FastMCP):
    # Initialize Neo4j driver with docker-compose configuration
    driver = AsyncGraphDatabase.driver(
        "neo4j://localhost:7687",  # Bolt port from docker-compose
        auth=("neo4j", "password")  # Auth from NEO4J_AUTH in docker-compose
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

    @mcp.tool()
    async def create_entities(entities: List[Dict], context: Dict) -> Dict:
        """Create multiple new entities in the knowledge graph"""
        if "driver" not in mcp.state:
            raise ValueError("Neo4j driver not found in server state")
        
        results = []
        driver = mcp.state["driver"]
        
        async with driver.session() as session:
            for entity in entities:
                # Create node with entity type as label
                query = """
                CREATE (n:Entity {
                    id: $id,
                    type: $type,
                    name: $name
                })
                WITH n, $type as type
                CALL apoc.create.addLabels(n, [type]) YIELD node
                RETURN node
                """
                params = {
                    "id": entity["properties"].get("name"),  # Using name as ID
                    "type": entity["type"],
                    "name": entity["properties"].get("name")
                }
                
                result = await session.run(query, params)
                record = await result.single()
                if record:
                    results.append(record["node"])
        
        return {"result": results}

    @mcp.tool()
    async def create_relations(relations: List[Dict]) -> Dict:
        """Create multiple new relations between entities"""
        if "driver" not in mcp.state:
            raise ValueError("Neo4j driver not found in server state")
        
        results = []
        driver = mcp.state["driver"]
        
        async with driver.session() as session:
            for relation in relations:
                query = """
                MATCH (a:Entity {id: $from}), (b:Entity {id: $to})
                CREATE (a)-[r:$type]->(b)
                RETURN type(r) as type, a.id as from_id, b.id as to_id
                """
                params = {
                    "from": relation["from"],
                    "to": relation["to"],
                    "type": relation["type"]
                }
                
                result = await session.run(query, params)
                record = await result.single()
                if record:
                    results.append({
                        "type": record["type"],
                        "from": record["from_id"],
                        "to": record["to_id"]
                    })
        
        return {"result": results}

    return mcp

if __name__ == "__main__":
    print("Starting Neo4j MCP server with stdio transport")
    server = create_server()
    server.run(transport="stdio")