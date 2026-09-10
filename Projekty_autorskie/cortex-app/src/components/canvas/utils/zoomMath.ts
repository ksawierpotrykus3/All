import type { ZoomTransformParams, ZoomTransformResult } from '../types';
import type { Projekt } from '../../../types';
import { PROJECT_CARD_WIDTH, PROJECT_CARD_HEIGHT } from '../constants';

/**
 * Wyznacza nową skalę i offset płótna.
 * - Przy Zoom In: punkt pod kursorem delikatnie i płynnie przyciąga się ku środkowi ekranu.
 * - Przy Zoom Out: widok zmniejsza się stabilnie pod kursorem myszy (zero odrzutu / strzelania w boki).
 */
export function calculateZoomTransform({
  currentScale,
  currentOffset,
  focalX,
  focalY,
  factor,
  viewportWidth,
  viewportHeight,
  centeringFactor = 0.45,
  minScale = 0.15,
  maxScale = 3.0,
}: ZoomTransformParams): ZoomTransformResult {
  const safeCurrentScale = Math.max(0.01, currentScale || 1);
  const newScale = Math.min(maxScale, Math.max(minScale, safeCurrentScale * factor));

  if (Math.abs(newScale - safeCurrentScale) < 1e-6) {
    return { scale: safeCurrentScale, offset: currentOffset };
  }

  // Punkt w układzie świata (world coords) przed zmianą skali:
  const worldX = (focalX - currentOffset.x) / safeCurrentScale;
  const worldY = (focalY - currentOffset.y) / safeCurrentScale;

  let targetScreenX = focalX;
  let targetScreenY = focalY;

  // Podczas Zoom In (powiększanie): delikatne przyciąganie wskazywanego punktu ku centrum
  if (newScale > safeCurrentScale && viewportWidth && viewportHeight && viewportWidth > 0 && viewportHeight > 0 && centeringFactor > 0) {
    const centerX = viewportWidth / 2;
    const centerY = viewportHeight / 2;
    const scaleRatioChange = (1 - safeCurrentScale / newScale) * centeringFactor;
    targetScreenX = focalX + (centerX - focalX) * scaleRatioChange;
    targetScreenY = focalY + (centerY - focalY) * scaleRatioChange;
  }
  // Podczas Zoom Out (oddalanie): czysty stabilny focal zoom bez odrzucania na boki

  const newOffsetX = targetScreenX - worldX * newScale;
  const newOffsetY = targetScreenY - worldY * newScale;

  return {
    scale: newScale,
    offset: { x: newOffsetX, y: newOffsetY },
  };
}

export const getProjectMacroPosition = (
  project: Projekt,
  index: number,
  totalProjects: number,
): { x: number; y: number } => {
  if (typeof project.x === 'number' && typeof project.y === 'number') {
    return { x: project.x, y: project.y };
  }
  if (totalProjects <= 1) {
    return { x: -PROJECT_CARD_WIDTH / 2, y: -PROJECT_CARD_HEIGHT / 2 };
  }
  const cols = totalProjects > 4 ? 3 : 2;
  const col = index % cols;
  const row = Math.floor(index / cols);
  const spacingX = 420;
  const spacingY = 220;
  const totalCols = Math.min(totalProjects, cols);
  const startX = -((totalCols - 1) * spacingX) / 2 - PROJECT_CARD_WIDTH / 2;
  const startY = -80 + row * spacingY - PROJECT_CARD_HEIGHT / 2;
  return {
    x: Math.round(startX + col * spacingX),
    y: Math.round(startY),
  };
};
