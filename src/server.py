import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from neo4j import AsyncGraphDatabase

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
                    "name": entity["properties"].get("name"),
                }

                result = await session.run(query, params)
                record = await result.single()
                if record:
                    results.append(record["node"])

        return {"result": results}

    @mcp.tool()
    async def introspect_schema() -> Dict:
        """Introspect the Neo4j database schema to get information about node labels and relationship types"""
        if "driver" not in mcp.state:
            raise ValueError("Neo4j driver not found in server state")

        driver = mcp.state["driver"]
        schema_info = {
            "node_labels": [],
            "relationship_types": [],
            "node_properties": {},
            "relationship_properties": {},
        }

        async with driver.session() as session:
            # Get all node labels
            labels_query = "CALL db.labels() YIELD label RETURN label"
            labels_result = await session.run(labels_query)
            schema_info["node_labels"] = [
                record["label"] async for record in labels_result
            ]

            # Get all relationship types
            rel_types_query = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
            rel_types_result = await session.run(rel_types_query)
            schema_info["relationship_types"] = [
                record["relationshipType"] async for record in rel_types_result
            ]

            # Get property keys for each node label
            for label in schema_info["node_labels"]:
                props_query = f"""
                MATCH (n:{label})
                WITH n LIMIT 1
                RETURN keys(n) as properties
                """
                props_result = await session.run(props_query)
                record = await props_result.single()
                if record:
                    schema_info["node_properties"][label] = record["properties"]

            # Get property keys for each relationship type
            for rel_type in schema_info["relationship_types"]:
                props_query = f"""
                MATCH ()-[r:{rel_type}]->()
                WITH r LIMIT 1
                RETURN keys(r) as properties
                """
                props_result = await session.run(props_query)
                record = await props_result.single()
                if record:
                    schema_info["relationship_properties"][rel_type] = record[
                        "properties"
                    ]

        return {"schema": schema_info}

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
                    "type": relation["type"],
                }

                result = await session.run(query, params)
                record = await result.single()
                if record:
                    results.append(
                        {
                            "type": record["type"],
                            "from": record["from_id"],
                            "to": record["to_id"],
                        }
                    )

        return {"result": results}

    return mcp


if __name__ == "__main__":
    print("Starting Neo4j MCP server with stdio transport")
    server = create_server()
    server.run(transport="stdio")
