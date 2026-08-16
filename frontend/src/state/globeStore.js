import { create } from 'zustand';

export const useGlobeStore = create((set) => ({
  selectedRegion: null, // null | 'continent' | 'country'
  selectedRegionName: '',
  cameraPosition: { lat: 20, lng: 0, altitude: 2.5 },
  dashboardOpen: false,
  selectedEventId: null,

  setSelectedEvent: (eventId) =>
    set(() => ({
      selectedEventId: eventId,
    })),

  setSelectedRegion: (type, name, position = null) =>
    set((state) => ({
      selectedRegion: type,
      selectedRegionName: name || '',
      cameraPosition: position || state.cameraPosition,
    })),

  setCameraPosition: (lat, lng, altitude) =>
    set(() => ({
      cameraPosition: { lat, lng, altitude },
    })),

  setDashboardOpen: (isOpen) =>
    set(() => ({
      dashboardOpen: isOpen,
    })),

  resetToWorld: () =>
    set(() => ({
      selectedRegion: null,
      selectedRegionName: '',
      selectedEventId: null,
      cameraPosition: { lat: 20, lng: 0, altitude: 2.5 },
    })),
}));
