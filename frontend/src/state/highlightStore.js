import { create } from 'zustand';

export const useHighlightStore = create((set) => ({
  selectedEventId: null,
  hoveredEventId: null,

  setSelectedEvent: (eventId) =>
    set(() => ({
      selectedEventId: eventId,
    })),

  setHoveredEvent: (eventId) =>
    set(() => ({
      hoveredEventId: eventId,
    })),

  clearSelectedEvent: () =>
    set(() => ({
      selectedEventId: null,
      hoveredEventId: null,
    })),
}));
