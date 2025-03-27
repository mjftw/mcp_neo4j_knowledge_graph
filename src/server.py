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

    @mcp.tool(
        name="create_entities",
        description="Create multiple new entities in the knowledge graph"
    )
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

    @mcp.tool(
        name="introspect_schema",
        description="Introspect the Neo4j database schema to get information about node labels and relationship types"
    )
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

    @mcp.tool(
        name="create_relations",
        description="Create multiple new relations between entities"
    )
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

    @mcp.tool(
        name="search_entities",
        description="Search for entities in the knowledge graph with fuzzy matching support"
    )
    async def search_entities(
        search_term: str,
        entity_type: str = None,
        properties: List[str] = None,
        include_relationships: bool = False,
        fuzzy_match: bool = True
    ) -> Dict[str, Any]:
        """Search for entities in the knowledge graph with fuzzy matching support
        
        Args:
            search_term: The text to search for
            entity_type: Optional entity type to filter by
            properties: Optional list of property names to search in (defaults to all)
            include_relationships: Whether to include relationships in results
            fuzzy_match: Whether to use fuzzy matching for text properties
        """
        if "driver" not in mcp.state:
            raise ValueError("Neo4j driver not found in server state")

        driver = mcp.state["driver"]
        results = []

        async with driver.session() as session:
            # Build the query dynamically based on parameters
            where_clauses = []
            params = {"search_term": search_term}
            
            # Add type filter if specified
            type_match = "n:Entity"
            if entity_type:
                type_match += f":{entity_type}"
                
            # Build property matching clause
            if properties:
                property_clauses = []
                for prop in properties:
                    if fuzzy_match:
                        property_clauses.append(f"n.{prop} =~ '(?i).*{search_term}.*'")
                    else:
                        property_clauses.append(f"n.{prop} = $search_term")
                if property_clauses:
                    where_clauses.append(f"({' OR '.join(property_clauses)})")
            else:
                # Search all string properties with fuzzy matching
                if fuzzy_match:
                    where_clauses.append("ANY (prop IN keys(n) WHERE n[prop] =~ $fuzzy_pattern)")
                    params["fuzzy_pattern"] = f"(?i).*{search_term}.*"
                else:
                    where_clauses.append("ANY (prop IN keys(n) WHERE n[prop] = $search_term)")

            # Construct the full query
            query = f"""
            MATCH (n:{type_match})
            WHERE {' AND '.join(where_clauses)}
            """

            # Optionally include relationships
            if include_relationships:
                query += """
                OPTIONAL MATCH (n)-[r]-(related)
                WITH n, collect({type: type(r), direction: CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END, 
                               node: {id: related.id, type: labels(related)[0], properties: properties(related)}}) as rels
                """
            
            query += """
            RETURN {
                id: n.id,
                type: labels(n)[0],
                properties: properties(n)
            } as node
            """
            
            if include_relationships:
                query += ", rels as relationships"

            # Execute query
            result = await session.run(query, params)
            
            async for record in result:
                node_data = record["node"]
                if include_relationships:
                    node_data["relationships"] = record["relationships"]
                results.append(node_data)

        return {"results": results}

    return mcp


if __name__ == "__main__":
    print("Starting Neo4j MCP server with stdio transport")
    server = create_server()
    server.run(transport="stdio")
