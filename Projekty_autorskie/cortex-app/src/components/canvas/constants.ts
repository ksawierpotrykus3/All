export const ZOOM_MACRO_THRESHOLD = 0.15;
export const ZOOM_CLUSTER_THRESHOLD = 0.70;
export const PROJECT_CARD_WIDTH = 340;
export const PROJECT_CARD_HEIGHT = 140;

export const NODE_WIDTH = 240;
export const NODE_HEADER_HEIGHT = 6;
export const NODE_BODY_HEIGHT = 48;
export const NODE_HEIGHT = NODE_HEADER_HEIGHT + NODE_BODY_HEIGHT;

export const PORTAL_NODE_WIDTH = 320;
export const PORTAL_NODE_HEIGHT = 240;

export const NOISE_DATA_URI =
  "data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E";

export const genId = () => `n_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
