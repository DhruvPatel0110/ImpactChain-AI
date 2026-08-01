"""
ImpactChain AI — Entity Filter Module

Removes generic, technical, or irrelevant entity names (e.g. conductor, resistor, product)
and validates entity roles against allowed whitelist before storing records in master DB.
"""

import logging

logger = logging.getLogger(__name__)

# List of generic, technical, or vague non-entity terms to exclude
IRRELEVANT_ENTITIES = {
    # Generic electronic/technical components (unless specific supply chain context)
    "conductor",
    "conductors",
    "resistor",
    "resistors",
    "capacitor",
    "capacitors",
    "diode",
    "diodes",
    "transistor",
    "transistors",
    "inductor",
    "inductors",
    "wire",
    "wires",
    "cable",
    "cables",
    "switch",
    "switches",
    "connector",
    "connectors",
    "circuit",
    "circuits",
    "board",
    "boards",
    # Generic meta-terms and vague placeholders
    "product",
    "products",
    "item",
    "items",
    "commodity",
    "commodities",
    "goods",
    "stuff",
    "thing",
    "things",
    "company",
    "companies",
    "firm",
    "firms",
    "country",
    "countries",
    "government",
    "governments",
    "industry",
    "industries",
    "sector",
    "sectors",
    "market",
    "markets",
    "price",
    "prices",
    "cost",
    "costs",
    "report",
    "reports",
    "news",
    "article",
    "articles",
    "statement",
    "statements",
    "analyst",
    "analysts",
    "expert",
    "experts",
}

# Allowed entity roles per Phase 1 specification
VALID_ENTITY_ROLES = {
    "supplier",
    "consumer",
    "logistics_node",
    "regulatory_body",
    "disruption_cause",
    "price_influencer",
}


def is_irrelevant_entity(entity_name: str) -> bool:
    """
    Check if an entity name is blank, invalid, or present in the IRRELEVANT_ENTITIES set.
    """
    if not entity_name or not isinstance(entity_name, str):
        return True

    entity_lower = entity_name.strip().lower()
    if not entity_lower:
        return True

    if entity_lower in IRRELEVANT_ENTITIES:
        logger.info(f"Filtered out irrelevant entity: {entity_lower}")
        return True

    return False


def filter_commodities(commodities: list[str]) -> list[str]:
    """Filter out irrelevant or generic commodities."""
    if not isinstance(commodities, list):
        return []

    filtered = []
    for item in commodities:
        if not item:
            continue
        c_str = str(item).strip().lower()
        if not is_irrelevant_entity(c_str):
            filtered.append(c_str)

    return filtered


def filter_entity_roles(entity_roles: dict) -> dict:
    """
    Filter entity_roles dictionary:
      1. Remove keys that match IRRELEVANT_ENTITIES
      2. Ensure roles match VALID_ENTITY_ROLES whitelist
    """
    if not isinstance(entity_roles, dict):
        return {}

    filtered = {}
    for entity_name, role in entity_roles.items():
        if is_irrelevant_entity(entity_name):
            continue

        role_str = str(role).strip().lower() if role else ""
        if role_str not in VALID_ENTITY_ROLES:
            logger.warning(
                f"Entity '{entity_name}' has invalid role '{role}' — skipping role assignment"
            )
            continue

        filtered[str(entity_name).strip().lower()] = role_str

    return filtered


def filter_relationships(relationships: list) -> list:
    """
    Filter out relationship triples where either source or target is an irrelevant entity.
    """
    if not isinstance(relationships, list):
        return []

    filtered = []
    for triple in relationships:
        if not isinstance(triple, (list, tuple)) or len(triple) != 3:
            continue

        source, rel_type, target = str(triple[0]), str(triple[1]), str(triple[2])

        if is_irrelevant_entity(source) or is_irrelevant_entity(target):
            logger.debug(f"Skipping relationship with irrelevant entity: [{source}, {rel_type}, {target}]")
            continue

        filtered.append([source.strip().lower(), rel_type.strip().lower(), target.strip().lower()])

    return filtered


def filter_entities_from_scaffold(raw_entities: dict) -> dict:
    """
    Filter out irrelevant entity strings from all lists inside spaCy's raw_entities dictionary.
    """
    if not isinstance(raw_entities, dict):
        return {}

    filtered_scaffold = {}
    for key, entity_list in raw_entities.items():
        if isinstance(entity_list, list):
            valid_list = []
            for item in entity_list:
                item_str = str(item).strip()
                # Skip irrelevant entity names if it's a textual entity list (not money/percent/quantity signals)
                if key in {"organizations", "locations", "products_mentioned", "events_mentioned", "norp_mentioned"}:
                    if not is_irrelevant_entity(item_str):
                        valid_list.append(item_str.lower())
                else:
                    valid_list.append(item_str)
            filtered_scaffold[key] = valid_list
        else:
            filtered_scaffold[key] = entity_list

    return filtered_scaffold
