import type { Section } from "@/stores/roadStore";

export const COLUMN_WIDTH = 200;
export const NODE_SPACING = 120;
export const VIEWPORT_CENTER_Y = 400;

export const VIRTUAL_MARKER_TYPES = new Set(['HASS-A', 'HASS-H', 'HASS-S', 'HASS-E']);

export const ALL_SECTIONS: Section[] = [
  { id: -2, title: 'Must Take' },
  { id: -1, title: 'ASEs' },
  { id: 0, title: "Freshman Fall" },
  { id: 1, title: "Freshman IAP" },
  { id: 2, title: "Freshman Spring" },
  { id: 3, title: "Sophomore Fall" },
  { id: 4, title: "Sophomore IAP" },
  { id: 5, title: "Sophomore Spring" },
  { id: 6, title: "Junior Fall" },
  { id: 7, title: "Junior IAP" },
  { id: 8, title: "Junior Spring" },
  { id: 9, title: "Senior Fall" },
  { id: 10, title: "Senior IAP" },
  { id: 11, title: "Senior Spring" },
];

export const SECTION_INDEX_MAP = new Map(
  ALL_SECTIONS.map((section, index) => [section.id, index])
);
