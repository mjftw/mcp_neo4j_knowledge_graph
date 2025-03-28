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


async def register(server: FastMCP, driver: AsyncDriver) -> None:
    """Register the create_entities tool with the MCP server."""
    
    @server.tool("create_entities")
    async def create_entities(entities: List[Dict]) -> Dict:
        """Create multiple new entities in the knowledge graph.
        
        Each entity is created with:
        - An Entity label and the specified type as an additional label
        - All provided properties
        - An ID field (either provided or derived from the name property)
        
        Args:
            entities: List of entity dictionaries, each containing:
                - type: String - The type of entity (e.g., Person, Organization)
                - properties: Dict - Properties of the entity, must include either:
                    - id: String - Unique identifier for the entity
                    - name: String - Name used as ID if no ID provided
                    - Any additional properties as key-value pairs
            
        Returns:
            Dict containing:
                result: List of created entities, each with:
                    - id: String - Entity's unique identifier
                    - type: String - Entity's type label
                    - properties: Dict - All properties of the created entity
                    
        Raises:
            ValueError: If required fields are missing or invalid
            Neo4jError: If there are database errors (e.g., duplicate IDs)
        """
     
            
        # Convert input dicts to CreateEntityRequest objects
        entity_requests = [
            CreateEntityRequest(
                type=e["type"],
                properties=e["properties"]
            ) for e in entities
        ]
        
        result = await create_entities_impl(driver, entity_requests)
        
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