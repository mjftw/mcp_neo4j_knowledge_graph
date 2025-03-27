from dataclasses import dataclass
from typing import Dict, List, Optional

from neo4j import AsyncDriver
from mcp.server.fastmcp import FastMCP


@dataclass
class SchemaLabel:
    """Represents a node label in the Neo4j schema"""
    name: str
    properties: List[str]


@dataclass
class SchemaRelationType:
    """Represents a relationship type in the Neo4j schema"""
    type: str
    properties: List[str]


@dataclass
class SchemaIntrospectionResult:
    """Result of schema introspection containing labels and relationship types"""
    node_labels: List[str]
    relationship_types: List[str]
    node_properties: Dict[str, List[str]]
    relationship_properties: Dict[str, List[str]]


async def introspect_schema_impl(driver: AsyncDriver) -> SchemaIntrospectionResult:
    """Introspect the Neo4j database schema to get information about node labels and relationship types
    
    Args:
        driver: Neo4j async driver instance
        
    Returns:
        SchemaIntrospectionResult containing schema information including node labels, relationship types,
        and their respective properties
    """
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
            UNWIND keys(n) as prop
            WITH DISTINCT prop
            RETURN collect(prop) as properties
            """
            props_result = await session.run(props_query)
            record = await props_result.single()
            if record:
                schema_info["node_properties"][label] = record["properties"]

        # Get property keys for each relationship type
        for rel_type in schema_info["relationship_types"]:
            props_query = f"""
            MATCH ()-[r:{rel_type}]->()
            UNWIND keys(r) as prop
            WITH DISTINCT prop
            RETURN collect(prop) as properties
            """
            props_result = await session.run(props_query)
            record = await props_result.single()
            if record:
                schema_info["relationship_properties"][rel_type] = record["properties"]

    return SchemaIntrospectionResult(
        node_labels=schema_info["node_labels"],
        relationship_types=schema_info["relationship_types"],
        node_properties=schema_info["node_properties"],
        relationship_properties=schema_info["relationship_properties"]
    )


async def register(server: FastMCP) -> None:
    """Register the introspect_schema tool with the MCP server."""
    
    @server.tool("mcp_neo4j_knowledge_graph_introspect_schema")
    async def introspect_schema(random_string: str) -> Dict:
        """Introspect the Neo4j database schema to get information about node labels and relationship types"""
        if "driver" not in server.state:
            raise ValueError("Neo4j driver not found in server state")

        result = await introspect_schema_impl(server.state["driver"])
        
        # Convert result back to dict format for MCP interface
        return {
            "schema": {
                "node_labels": result.node_labels,
                "relationship_types": result.relationship_types,
                "node_properties": result.node_properties,
                "relationship_properties": result.relationship_properties
            }
        } 