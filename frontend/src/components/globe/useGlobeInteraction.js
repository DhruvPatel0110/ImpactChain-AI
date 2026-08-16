import { useState, useEffect, useCallback, useMemo } from 'react';
import { feature as topojsonFeature } from 'topojson-client';
import worldBoundaries from '../../data/worldBoundaries.json';
import { useGlobeStore } from '../../state/globeStore';
import { getContinentForFeature, CONTINENT_CENTERS, WORLD_CENTER } from '../../data/continentMapping';

export function useGlobeInteraction(globeRef) {
  const [hoveredPolygon, setHoveredPolygon] = useState(null);
  
  const selectedRegion = useGlobeStore((state) => state.selectedRegion);
  const selectedRegionName = useGlobeStore((state) => state.selectedRegionName);
  const setSelectedRegion = useGlobeStore((state) => state.setSelectedRegion);
  const resetToWorld = useGlobeStore((state) => state.resetToWorld);

  // Convert TopoJSON to GeoJSON features
  const countryPolygons = useMemo(() => {
    try {
      if (worldBoundaries && worldBoundaries.objects && worldBoundaries.objects.countries) {
        const geojson = topojsonFeature(worldBoundaries, worldBoundaries.objects.countries);
        return geojson.features.map((f) => ({
          ...f,
          continent: getContinentForFeature(f),
        }));
      }
    } catch (err) {
      console.error('Failed to parse world boundaries TopoJSON:', err);
    }
    return [];
  }, []);

  // Fly camera smoothly using react-globe.gl pointOfView API
  const flyTo = useCallback(
    (lat, lng, altitude, durationMs = 1200) => {
      if (globeRef.current) {
        globeRef.current.pointOfView({ lat, lng, altitude }, durationMs);
      }
    },
    [globeRef]
  );

  // Handle polygon click for Continent -> Country drill-down
  const handlePolygonClick = useCallback(
    (polygon, event, { lat, lng }) => {
      if (!polygon) return;

      const continent = polygon.continent || getContinentForFeature(polygon);
      const countryName = polygon.properties?.name || `Country (${polygon.id})`;

      if (selectedRegion === null) {
        // World -> Continent drill down
        const center = CONTINENT_CENTERS[continent] || { lat, lng, altitude: 2.2 };
        flyTo(center.lat, center.lng, center.altitude);
        setSelectedRegion('continent', continent, center);
      } else if (selectedRegion === 'continent') {
        // Continent -> Country drill down
        const countryPos = { lat, lng, altitude: 1.0 };
        flyTo(lat, lng, 1.0);
        setSelectedRegion('country', countryName, countryPos);
      } else if (selectedRegion === 'country') {
        // Switch country in tight view
        const countryPos = { lat, lng, altitude: 1.0 };
        flyTo(lat, lng, 1.0);
        setSelectedRegion('country', countryName, countryPos);
      }
    },
    [selectedRegion, flyTo, setSelectedRegion]
  );

  // Reset framing back to full world view
  const handleResetToWorld = useCallback(() => {
    resetToWorld();
    flyTo(WORLD_CENTER.lat, WORLD_CENTER.lng, WORLD_CENTER.altitude, 1500);
  }, [resetToWorld, flyTo]);

  // Idempotent hover handler to prevent React re-render cascades
  const handlePolygonHover = useCallback((newPolygon) => {
    setHoveredPolygon((prev) => {
      if ((!prev && !newPolygon) || (prev && newPolygon && prev.id === newPolygon.id)) {
        return prev;
      }
      return newPolygon;
    });
  }, []);

  // Polygon styling logic - Solid opaque black landmasses with crisp vector outlines
  const getPolygonCapColor = useCallback(() => '#060a14', []);
  const getPolygonSideColor = useCallback(() => '#060a14', []);
  const getPolygonStrokeColor = useCallback(
    (polygon) => {
      if (hoveredPolygon && hoveredPolygon.id === polygon.id) {
        return 'rgba(147, 197, 253, 0.95)'; // Bright blue hover border
      }
      return 'rgba(255, 255, 255, 0.7)'; // Crisp clean white country outline
    },
    [hoveredPolygon]
  );

  // Calculate centroids for 3D globe text labels
  const countryLabels = useMemo(() => {
    return countryPolygons
      .map((f) => {
        let minLng = 180,
          maxLng = -180,
          minLat = 90,
          maxLat = -90;

        const processCoords = (coords) => {
          if (typeof coords[0] === 'number') {
            const [lng, lat] = coords;
            if (lng < minLng) minLng = lng;
            if (lng > maxLng) maxLng = lng;
            if (lat < minLat) minLat = lat;
            if (lat > maxLat) maxLat = lat;
          } else {
            coords.forEach(processCoords);
          }
        };

        if (f.geometry && f.geometry.coordinates) {
          processCoords(f.geometry.coordinates);
          return {
            lat: (minLat + maxLat) / 2,
            lng: (minLng + maxLng) / 2,
            name: f.properties?.name || '',
            continent: f.continent,
            id: f.id,
          };
        }
        return null;
      })
      .filter((label) => label && label.name);
  }, [countryPolygons]);

  return {
    countryPolygons,
    countryLabels,
    hoveredPolygon,
    handlePolygonHover,
    handlePolygonClick,
    handleResetToWorld,
    getPolygonCapColor,
    getPolygonSideColor,
    getPolygonStrokeColor,
  };
}

