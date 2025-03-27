from typing import Dict
from neo4j import AsyncDriver


async def introspect_schema_impl(driver: AsyncDriver) -> Dict:
    """Introspect the Neo4j database schema to get information about node labels and relationship types
    
    Args:
        driver: Neo4j async driver instance
        
    Returns:
        Dict containing schema information including node labels, relationship types,
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
                schema_info["relationship_properties"][rel_type] = record[
                    "properties"
                ]

    return {"schema": schema_info}


async def register(mcp):
    @mcp.tool(
        name="introspect_schema",
        description="Introspect the Neo4j database schema to get information about node labels and relationship types"
    )
    async def introspect_schema() -> Dict:
        """Introspect the Neo4j database schema to get information about node labels and relationship types"""
        if "driver" not in mcp.state:
            raise ValueError("Neo4j driver not found in server state")

        return await introspect_schema_impl(mcp.state["driver"]) 