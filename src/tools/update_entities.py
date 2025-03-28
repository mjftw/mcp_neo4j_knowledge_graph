from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from neo4j import AsyncDriver, AsyncSession
from mcp.server.fastmcp import FastMCP

from .delete_entities import _neo4j_to_entity, Entity


@dataclass
class UpdateEntityRequest:
    id: str
    properties: Optional[Dict[str, any]] = None  # Properties to update/add
    remove_properties: Optional[List[str]] = None  # Properties to remove
    add_labels: Optional[List[str]] = None  # Labels to add
    remove_labels: Optional[List[str]] = None  # Labels to remove


@dataclass
class UpdateEntitiesResult:
    success: bool
    updated_entities: List[Entity]
    errors: Optional[List[str]] = None


async def update_entities_impl(
    driver: AsyncDriver,
    requests: List[UpdateEntityRequest]
) -> UpdateEntitiesResult:
    """Update entities in the graph.
    
    Args:
        driver: Neo4j async driver instance
        requests: List of UpdateEntityRequest objects specifying what to update
    
    Returns:
        UpdateEntitiesResult containing:
        - success: Whether all updates were successful
        - updated_entities: List of entities after updates
        - errors: Optional list of error messages if any updates failed
    """
    async with driver.session() as session:
        # First verify all entities exist
        entity_ids = [r.id for r in requests]
        query = """
        MATCH (n:Entity)
        WHERE n.id IN $entity_ids
        RETURN collect(n.id) as found_ids
        """
        result = await session.run(query, {"entity_ids": entity_ids})
        record = await result.single()
        found_ids = record["found_ids"] if record else []
        
        missing_ids = set(entity_ids) - set(found_ids)
        if missing_ids:
            return UpdateEntitiesResult(
                success=False,
                updated_entities=[],
                errors=[f"Entities not found: {', '.join(missing_ids)}"]
            )

        # Process each update request
        updated_entities = []
        errors = []
        
        for request in requests:
            try:
                # Build dynamic SET and REMOVE clauses based on the request
                set_clauses = []
                remove_clauses = []
                params = {"id": request.id}
                
                # Handle property updates
                if request.properties:
                    params["props"] = request.properties
                    set_clauses.append("n += $props")
                
                # Handle property removals
                if request.remove_properties:
                    for prop in request.remove_properties:
                        remove_clauses.append(f"n.{prop}")
                
                # Handle label additions
                if request.add_labels:
                    for label in request.add_labels:
                        set_clauses.append(f"n:`{label}`")
                
                # Handle label removals
                if request.remove_labels:
                    for label in request.remove_labels:
                        remove_clauses.append(f"n:`{label}`")
                
                # Build and execute the update query
                query_parts = ["MATCH (n:Entity) WHERE n.id = $id"]
                
                if set_clauses:
                    query_parts.append("SET " + ", ".join(set_clauses))
                if remove_clauses:
                    query_parts.append("REMOVE " + ", ".join(remove_clauses))
                    
                query_parts.append("""
                RETURN {
                    id: n.id,
                    type: labels(n),
                    properties: properties(n)
                } as entity
                """)
                
                query = "\n".join(query_parts)
                result = await session.run(query, params)
                record = await result.single()
                
                if record:
                    updated_entities.append(_neo4j_to_entity(record["entity"]))
                
            except Exception as e:
                errors.append(f"Failed to update entity {request.id}: {str(e)}")
        
        return UpdateEntitiesResult(
            success=len(errors) == 0,
            updated_entities=updated_entities,
            errors=errors if errors else None
        )


async def register(server: FastMCP, driver: AsyncDriver) -> None:
    """Register the update_entities tool with the MCP server."""
    
    @server.tool("update_entities")
    async def update_entities(
        updates: List[Dict],
        context: Dict = None
    ) -> Dict:
        """Update existing entities in the knowledge graph with comprehensive modification options.
        
        Provides atomic updates to entities including:
        - Adding or updating properties
        - Removing specific properties
        - Adding new labels/types
        - Removing existing labels/types
        
        All updates in a request are processed as a batch, but each entity update
        is independent. If one update fails, others will still proceed.
        
        Args:
            updates: List of update requests, each containing:
                - id: String (required) - ID of the entity to update
                - properties: Optional[Dict] - Properties to add or update
                - remove_properties: Optional[List[String]] - Property names to remove
                - add_labels: Optional[List[String]] - Labels to add to the entity
                - remove_labels: Optional[List[String]] - Labels to remove from the entity
            context: Optional[Dict] - Additional context for the update operation
            
        Returns:
            Dict containing:
                - success: Boolean - True if all updates succeeded, False if any failed
                - updated_entities: List[Dict] - Entities after updates, each with:
                    - id: String - Entity's identifier
                    - type: List[String] - Entity's current labels
                    - properties: Dict - All current properties
                - errors: Optional[List[String]] - Error messages if any updates failed
                
        Raises:
            ValueError: If entity IDs don't exist or update format is invalid
            Neo4jError: For database-level errors
            
        Notes:
            - At least one modification (properties, remove_properties, add_labels,
              or remove_labels) must be specified
            - Property updates are merged with existing properties
            - Removing a non-existent property or label is not an error
            - The Entity label and type cannot be removed
            - Updates are atomic per entity
        """
        requests = [UpdateEntityRequest(**update) for update in updates]
        result = await update_entities_impl(driver, requests)
        return result.__dict__ 