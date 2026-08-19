import { create } from 'zustand';

export const useGlobeStore = create((set) => ({
  selectedRegion: null, // null | 'continent' | 'country' | 'event-pin'
  selectedRegionName: '',
  cameraPosition: { lat: 20, lng: 0, altitude: 2.5 },
  dashboardOpen: false,
  selectedEventId: null,

  // Phase 3: Pin drill-down state
  pinnedEventId: null, // the event whose ring has been replaced by a precise pin

  setSelectedEvent: (eventId) =>
    set(() => ({
      selectedEventId: eventId,
    })),

  /**
   * Phase 3: Transition a ring into a pin.
   * Sets pinnedEventId so the ring is hidden and a pin appears.
   * Also updates selectedRegion to 'event-pin' for UI breadcrumb tracking.
   */
  pinEvent: (eventId, eventName) =>
    set(() => ({
      pinnedEventId: eventId,
      selectedEventId: eventId,
      selectedRegion: 'event-pin',
      selectedRegionName: eventName || '',
    })),

  /**
   * Phase 3: Back out of pin view to the region/ring view.
   * Clears the pin but keeps the selectedEventId so the HUD stays focused.
   */
  unpinEvent: () =>
    set((state) => ({
      pinnedEventId: null,
      selectedRegion: null,
      selectedRegionName: '',
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
      pinnedEventId: null,
      cameraPosition: { lat: 20, lng: 0, altitude: 2.5 },
    })),
}));
