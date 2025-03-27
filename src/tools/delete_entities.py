from dataclasses import dataclass
from typing import Dict, List, Optional

from neo4j import AsyncDriver, AsyncSession
from mcp.server.fastmcp import FastMCP


@dataclass
class DeleteEntityRequest:
    id: str
    cascade: bool = False


@dataclass
class Entity:
    id: str
    type: List[str]  # Updated to match the actual type from Neo4j
    properties: Dict[str, any]
    relationships: Optional[List[Dict]] = None


@dataclass
class DeletionResult:
    success: bool
    deleted_entities: List[Entity]
    deleted_relationships: List[Dict]
    errors: List[str] = None
    impacted_entities: List[Entity] = None
    impacted_relationships: List[Dict] = None


def _neo4j_to_entity(neo4j_entity: Dict) -> Entity:
    """Convert Neo4j entity format to our Entity dataclass"""
    # Handle case where properties are already in the right format
    if "properties" in neo4j_entity:
        properties = neo4j_entity["properties"]
    else:
        # Remove internal Neo4j properties and type/id fields
        properties = {k: v for k, v in neo4j_entity.items() 
                     if k not in ["type", "id", "labels"] and not k.startswith("_")}
    
    return Entity(
        id=neo4j_entity["id"],
        type=neo4j_entity["type"] if isinstance(neo4j_entity["type"], list) else [neo4j_entity["type"]],
        properties=properties
    )


async def delete_entities_impl(
    driver: AsyncDriver,
    requests: List[DeleteEntityRequest],
    dry_run: bool = False
) -> DeletionResult:
    """Delete entities from the graph with optional cascade deletion of relationships.
    
    Args:
        driver: Neo4j async driver instance
        requests: List of DeleteEntityRequest objects specifying what to delete
        dry_run: If True, only return what would be deleted without making changes
    
    Returns:
        DeletionResult containing:
        - success: Whether the operation was successful
        - deleted_entities: List of entities that were deleted
        - deleted_relationships: List of relationships that were deleted
        - errors: Optional list of error messages if deletion was prevented
        - impacted_entities: Optional list of entities that would be affected (dry_run only)
        - impacted_relationships: Optional list of relationships that would be affected (dry_run only)
    """
    entity_ids = [r.id for r in requests]
    cascade = any(r.cascade for r in requests)

    async with driver.session() as session:
        # First get all affected entities and relationships
        impact = await _analyze_deletion_impact(session, entity_ids)
        
        if dry_run:
            return DeletionResult(
                success=True,
                deleted_entities=[],
                deleted_relationships=[],
                impacted_entities=[_neo4j_to_entity(e) for e in impact["entities"]],
                impacted_relationships=impact["relations"]
            )
            
        # If not cascading, check for orphaned relationships
        if not cascade and impact["orphaned_relations"]:
            return DeletionResult(
                success=False,
                deleted_entities=[],
                deleted_relationships=[],
                errors=["Cannot delete entities as it would create orphaned relationships. Use cascade=True to delete relationships as well."]
            )
            
        # Perform the deletion
        if cascade:
            # Delete both entities and relationships
            query = """
            MATCH (n:Entity)
            WHERE n.id IN $entity_ids
            WITH n
            OPTIONAL MATCH (n)-[r]-()
            DELETE n, r
            RETURN count(DISTINCT n) as deleted_entities, count(DISTINCT r) as deleted_relations
            """
        else:
            # Delete only entities that have no relationships
            query = """
            MATCH (n:Entity)
            WHERE n.id IN $entity_ids
            AND NOT (n)-[]-()
            DELETE n
            RETURN count(n) as deleted_entities, 0 as deleted_relations
            """
            
        result = await session.run(query, {"entity_ids": entity_ids})
        stats = await result.single()
        
        # Handle case where no entities were found
        if stats is None or stats["deleted_entities"] == 0:
            return DeletionResult(
                success=False,
                deleted_entities=[],
                deleted_relationships=[],
                errors=["Entity not found"]
            )
            
        return DeletionResult(
            success=True,
            deleted_entities=[_neo4j_to_entity(e) for e in impact["entities"]],
            deleted_relationships=impact["relations"] if cascade else []
        )


async def _analyze_deletion_impact(
    session: AsyncSession,
    entity_ids: List[str]
) -> Dict:
    """Analyze what would be affected by deleting the specified entities.
    
    Args:
        session: Neo4j async session
        entity_ids: List of entity IDs to analyze
        
    Returns:
        Dict containing affected entities and relationships
    """
    # Get entities and their relationships
    query = """
    MATCH (n:Entity)
    WHERE n.id IN $entity_ids
    OPTIONAL MATCH (n)-[r]-()
    RETURN 
        collect(DISTINCT {
            id: n.id,
            type: labels(n),
            properties: properties(n)
        }) as entities,
        collect(DISTINCT {
            type: type(r),
            from: startNode(r).id,
            to: endNode(r).id,
            properties: properties(r)
        }) as relations
    """
    
    result = await session.run(query, {"entity_ids": entity_ids})
    record = await result.single()
    
    if not record:
        return {"entities": [], "relations": [], "orphaned_relations": []}
        
    entities = record["entities"]
    relations = record["relations"]
    
    # Filter out None from relations (when there are no relationships)
    relations = [r for r in relations if r is not None]
    
    # Identify orphaned relationships (those where only one end is being deleted)
    orphaned_relations = []
    for rel in relations:
        if (rel["from"] in entity_ids) != (rel["to"] in entity_ids):
            orphaned_relations.append(rel)
            
    return {
        "entities": entities,
        "relations": relations,
        "orphaned_relations": orphaned_relations
    }


async def register(server: FastMCP) -> None:
    """Register the delete_entities tool with the MCP server."""
    
    @server.tool("mcp_neo4j_knowledge_graph_delete_entities")
    async def delete_entities(
        entity_ids: List[str],
        cascade: bool = False,
        dry_run: bool = False,
        context: Dict = None
    ) -> Dict:
        """Delete entities from the knowledge graph.
        
        Args:
            entity_ids: List of entity IDs to delete
            cascade: If True, delete all relationships connected to these entities
            dry_run: If True, only return what would be deleted without making changes
            context: Optional context with Neo4j driver instance
            
        Returns:
            Dict containing:
            - success: Whether the operation was successful
            - deleted_entities: List of entities that were deleted
            - deleted_relationships: List of relationships that were deleted
            - errors: Optional list of error messages if deletion was prevented
            - impacted_entities: Optional list of entities that would be affected (dry_run only)
            - impacted_relationships: Optional list of relationships that would be affected (dry_run only)
        """
        driver = context["driver"]
        requests = [DeleteEntityRequest(id=id, cascade=cascade) for id in entity_ids]
        result = await delete_entities_impl(driver, requests, dry_run)
        return result.__dict__ 