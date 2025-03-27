from typing import Dict, List
from neo4j import AsyncDriver


async def create_entities_impl(driver: AsyncDriver, entities: List[Dict]) -> Dict:
    """Create multiple new entities in the knowledge graph
    
    Args:
        driver: Neo4j async driver instance
        entities: List of entity dictionaries with type and properties fields
        
    Returns:
        Dict containing the created entities
    """
    results = []

    async with driver.session() as session:
        for entity in entities:
            # Create node with entity type as label and all properties
            query = """
            CREATE (n:Entity)
            SET n = $properties
            SET n.type = $type
            WITH n, $type as type
            CALL apoc.create.addLabels(n, [type]) YIELD node
            RETURN node
            """
            
            # Ensure id is set (use name if not provided)
            properties = dict(entity["properties"])
            if "id" not in properties:
                properties["id"] = properties.get("name")
            
            params = {
                "properties": properties,
                "type": entity["type"]
            }

            result = await session.run(query, params)
            record = await result.single()
            if record:
                results.append(record["node"])

    return {"result": results}


async def register(mcp):
    @mcp.tool(
        name="create_entities",
        description="Create multiple new entities in the knowledge graph"
    )
    async def create_entities(entities: List[Dict], context: Dict) -> Dict:
        """Create multiple new entities in the knowledge graph"""
        if "driver" not in mcp.state:
            raise ValueError("Neo4j driver not found in server state")

        return await create_entities_impl(mcp.state["driver"], entities) 