from dataclasses import dataclass
from typing import Dict, List, Optional

from neo4j import AsyncDriver, AsyncSession
from mcp.server.fastmcp import FastMCP


@dataclass
class Entity:
    id: str
    type: str
    properties: Dict[str, any]


@dataclass
class Relationship:
    type: str
    from_id: str
    to_id: str
    properties: Optional[Dict[str, any]] = None


@dataclass
class DeletionResult:
    deleted_entities: List[Entity]
    deleted_relations: List[Relationship]
    stats: Dict[str, int]
    error: Optional[str] = None
    orphaned_relations: Optional[List[Relationship]] = None


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
        type=neo4j_entity["type"][0] if isinstance(neo4j_entity["type"], list) else neo4j_entity["type"],
        properties=properties
    )


def _neo4j_to_relationship(neo4j_rel: Dict) -> Relationship:
    """Convert Neo4j relationship format to our Relationship dataclass"""
    return Relationship(
        type=neo4j_rel["type"],
        from_id=neo4j_rel["from"],
        to_id=neo4j_rel["to"],
        properties=neo4j_rel.get("properties")
    )


async def delete_entities_impl(
    driver: AsyncDriver,
    entity_ids: List[str],
    cascade: bool = False,
    dry_run: bool = False
) -> DeletionResult:
    """Delete entities from the graph with optional cascade deletion of relationships.
    
    Args:
        driver: Neo4j async driver instance
        entity_ids: List of entity IDs to delete
        cascade: If True, delete all relationships connected to these entities
        dry_run: If True, only return what would be deleted without making changes
    
    Returns:
        DeletionResult containing:
        - deleted_entities: List of entities that were/would be deleted
        - deleted_relations: List of relationships that were/would be deleted
        - stats: Counts of deleted entities and relationships
        - error: Optional error message if deletion was prevented
        - orphaned_relations: Optional list of relationships that would be orphaned
    """
    async with driver.session() as session:
        # First get all affected entities and relationships
        impact = await _analyze_deletion_impact(session, entity_ids)
        
        if dry_run:
            return DeletionResult(
                deleted_entities=[_neo4j_to_entity(e) for e in impact["entities"]],
                deleted_relations=[_neo4j_to_relationship(r) for r in impact["relations"]],
                stats={"entities_deleted": 0, "relations_deleted": 0},
                orphaned_relations=[_neo4j_to_relationship(r) for r in impact["orphaned_relations"]]
            )
            
        # If not cascading, check for orphaned relationships
        if not cascade and impact["orphaned_relations"]:
            return DeletionResult(
                deleted_entities=[],
                deleted_relations=[],
                stats={"entities_deleted": 0, "relations_deleted": 0},
                error="Cannot delete entities as it would create orphaned relationships. Use cascade=True to delete relationships as well.",
                orphaned_relations=[_neo4j_to_relationship(r) for r in impact["orphaned_relations"]]
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
        
        # Handle case where no entities were found/deleted
        if stats is None:
            stats = {"deleted_entities": 0, "deleted_relations": 0}
            
        return DeletionResult(
            deleted_entities=[_neo4j_to_entity(e) for e in impact["entities"]],
            deleted_relations=[_neo4j_to_relationship(r) for r in impact["relations"]] if cascade else [],
            stats={
                "entities_deleted": stats["deleted_entities"],
                "relations_deleted": stats["deleted_relations"]
            }
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
            dry_run: If True, only preview what would be deleted without making changes
            context: MCP context (unused)
            
        Returns:
            Dict containing:
            - deleted_entities: List of entities that were/would be deleted
            - deleted_relations: List of relationships that were/would be deleted
            - orphaned_relations: List of relationships that would be orphaned (if cascade=False)
            - stats: Counts of deleted entities and relationships
        """
        driver = server.get_tool("neo4j_driver")
        if not driver:
            return {"error": "Neo4j driver not found"}
            
        return await delete_entities_impl(driver, entity_ids, cascade, dry_run) 