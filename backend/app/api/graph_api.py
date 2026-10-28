from fastapi import APIRouter, HTTPException
import logging
from master_graph import MasterGraph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["graph"])

# Initialize master graph (loaded once at startup or lazy loaded)
master_graph_instance = None

async def init_graph():
    global master_graph_instance
    master_graph_instance = MasterGraph()
    await master_graph_instance.load()
    return master_graph_instance

@router.get("/master_graph/hotspots")
async def get_globe_hotspots():
    """
    Returns a list of hotspots for globe visualization.
    
    Each hotspot represents a region with supply chain disruptions.
    Intensity is based on article count and recency.
    """
    global master_graph_instance
    if master_graph_instance is None:
        try:
            master_graph_instance = MasterGraph()
        except Exception as e:
            logger.error(f"Failed to instantiate MasterGraph: {e}")
            raise HTTPException(status_code=500, detail="Graph not initialized")
    
    try:
        hotspots = master_graph_instance.get_hotspots_for_globe()
        return hotspots
    except Exception as e:
        logger.error(f"Hotspot generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Hotspot generation failed: {str(e)}")

@router.get("/graph/hotspots")
async def get_globe_hotspots_alias():
    """Alias for /api/master_graph/hotspots."""
    return await get_globe_hotspots()
