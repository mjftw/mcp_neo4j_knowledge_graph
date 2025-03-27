from dataclasses import dataclass
from typing import Dict, List, Optional

from neo4j import AsyncDriver
from mcp.server.fastmcp import FastMCP


@dataclass
class Entity:
    id: str
    type: str
    properties: Dict[str, any]


@dataclass
class CreateEntityRequest:
    type: str
    properties: Dict[str, any]


@dataclass
class CreateEntitiesResult:
    result: List[Entity]


async def create_entities_impl(driver: AsyncDriver, entities: List[CreateEntityRequest]) -> CreateEntitiesResult:
    """Create multiple new entities in the knowledge graph
    
    Args:
        driver: Neo4j async driver instance
        entities: List of entity requests with type and properties fields
        
    Returns:
        CreateEntitiesResult containing the created entities with their properties
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
            RETURN {
                id: node.id,
                type: node.type,
                properties: properties(node)
            } as result
            """
            
            # Ensure id is set (use name if not provided)
            properties = dict(entity.properties)
            if "id" not in properties:
                properties["id"] = properties.get("name")
            
            params = {
                "properties": properties,
                "type": entity.type
            }

            result = await session.run(query, params)
            record = await result.single()
            if record:
                node_data = record["result"]
                results.append(Entity(
                    id=node_data["id"],
                    type=node_data["type"],
                    properties=node_data["properties"]
                ))

    return CreateEntitiesResult(result=results)


async def register(server: FastMCP) -> None:
    """Register the create_entities tool with the MCP server."""
    
    @server.tool("mcp_neo4j_knowledge_graph_create_entities")
    async def create_entities(entities: List[Dict], context: Dict = None) -> Dict:
        """Create multiple new entities in the knowledge graph
        
        Args:
            entities: List of entity dictionaries with type and properties fields
            context: MCP context (unused)
            
        Returns:
            Dict containing the created entities with their properties
        """
        if "driver" not in server.state:
            raise ValueError("Neo4j driver not found in server state")
            
        # Convert input dicts to CreateEntityRequest objects
        entity_requests = [
            CreateEntityRequest(
                type=e["type"],
                properties=e["properties"]
            ) for e in entities
        ]
        
        result = await create_entities_impl(server.state["driver"], entity_requests)
        
        # Convert result back to dict format for MCP interface
        return {
            "result": [
                {
                    "id": e.id,
                    "type": e.type,
                    "properties": e.properties
                } for e in result.result
            ]
        } 