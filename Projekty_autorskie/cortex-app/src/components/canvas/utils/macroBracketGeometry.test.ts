import { describe, it, expect } from 'vitest';
import { computeMacroBracketGeometries, MacroClusterBox } from './macroBracketGeometry';
import { ProjektyBracket } from '../../../types';

describe('computeMacroBracketGeometries', () => {
  const sampleBracket: ProjektyBracket = {
    id: 'b-1',
    project_id: 'p-1',
    name: 'Ulepszenie oznaczania w cortex',
    node_ids: ['node-1', 'node-2'],
    created_at: new Date().toISOString(),
  };

  const projectCenter = { x: 100, y: 50 };

  it('detects vertical layout and places bracket on left when clusters are close and to the left of project', () => {
    const clusterBoxes: MacroClusterBox[] = [
      { key: 'node-1', desc: 'Klaster A', x: -200, y: -50, width: 220, height: 60 },
      { key: 'node-2', desc: 'Klaster B', x: -200, y: 30, width: 220, height: 60 },
    ];

    const results = computeMacroBracketGeometries([sampleBracket], undefined, clusterBoxes, projectCenter);
    expect(results).toHaveLength(1);
    expect(results[0].mode).toBe('bracket');
    expect(results[0].isVertical).toBe(true);
    expect(results[0].side).toBe('left');
    expect(results[0].name).toBe('Ulepszenie oznaczania w cortex');
    expect(results[0].pathD).toContain('M');
  });

  it('detects horizontal layout and places bracket on top when clusters are close and above project', () => {
    const clusterBoxes: MacroClusterBox[] = [
      { key: 'node-1', desc: 'Klaster A', x: -100, y: -150, width: 220, height: 60 },
      { key: 'node-2', desc: 'Klaster B', x: 130, y: -150, width: 220, height: 60 },
    ];

    const results = computeMacroBracketGeometries([sampleBracket], undefined, clusterBoxes, projectCenter);
    expect(results).toHaveLength(1);
    expect(results[0].mode).toBe('bracket');
    expect(results[0].isVertical).toBe(false);
    expect(results[0].side).toBe('top');
  });

  it('switches to tether mode when clusters are too far apart (> 200px gap)', () => {
    const clusterBoxes: MacroClusterBox[] = [
      { key: 'node-1', desc: 'Klaster A', x: -300, y: -250, width: 220, height: 60 },
      { key: 'node-2', desc: 'Klaster B', x: 200, y: 300, width: 220, height: 60 },
    ];

    const results = computeMacroBracketGeometries([sampleBracket], undefined, clusterBoxes, projectCenter);
    expect(results).toHaveLength(1);
    expect(results[0].mode).toBe('tether');
    expect(results[0].tetherPathD).toBeDefined();
    expect(results[0].tetherLabelX).toBeDefined();
  });

  it('resolves member clusters when bracket contains secondary nodes belonging to the same cluster descriptions', () => {
    const clusterBoxes: MacroClusterBox[] = [
      { key: 'node-root-1', desc: 'Ulepszenie ofert/wycen', x: 200, y: -50, width: 220, height: 60 },
      { key: 'node-root-2', desc: 'Problemy poprzednich prób', x: 200, y: 30, width: 220, height: 60 },
    ];

    const clusterDescriptions = {
      'node-root-1': 'Ulepszenie ofert/wycen',
      'node-child-1': 'Ulepszenie ofert/wycen',
      'node-root-2': 'Problemy poprzednich prób',
      'node-child-2': 'Problemy poprzednich prób',
    };

    const bracketWithSecondaryNodes: ProjektyBracket = {
      id: 'b-secondary',
      project_id: 'p-1',
      name: 'Ulepszanie ofert',
      node_ids: ['node-child-1', 'node-child-2'],
      created_at: new Date().toISOString(),
    };

    const results = computeMacroBracketGeometries([bracketWithSecondaryNodes], clusterDescriptions, clusterBoxes, projectCenter);
    expect(results).toHaveLength(1);
    expect(results[0].name).toBe('Ulepszanie ofert');
    expect(results[0].mode).toBe('bracket');
  });
});
