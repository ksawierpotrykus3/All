import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { StorageEngine } from './StorageEngine';

describe('StorageEngine pipeline merging', () => {
  let tmpDir: string;
  let engine: StorageEngine;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cortex-storage-test-'));
    engine = new StorageEngine(tmpDir);
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('merges declared blueprint steps with live runtime execution state', () => {
    const pipelinesDir = path.join(tmpDir, 'pipelines');
    fs.mkdirSync(pipelinesDir, { recursive: true });

    // 1. Zapisz szablon rurociagu (2 kroki: Wycena i dni, Tresc oferty)
    const blueprint = {
      id: 'useme-oferty',
      nazwa: 'Generator oferty Useme',
      kroki: [
        { id: 1, nazwa: 'Wycena i dni', typ: 'ai', status: 'w_kolejce' },
        { id: 2, nazwa: 'Tresc oferty', typ: 'ai', status: 'w_kolejce' },
      ],
      uruchom: { komenda: 'python', args: ['chain_executor.py'] }
    };
    fs.writeFileSync(path.join(pipelinesDir, 'useme-oferty.json'), JSON.stringify(blueprint), 'utf-8');

    // 2. Zapisz stan wykonania (tylko 1 krok ruszyl: Wycena i dni - w toku)
    const stanDir = path.join(pipelinesDir, 'useme-oferty');
    fs.mkdirSync(stanDir, { recursive: true });
    const stan = {
      id: 'useme-oferty',
      nazwa: 'Generator oferty Useme',
      kroki: [
        { id: 1, nazwa: 'Wycena i dni', typ: 'ai', status: 'w_toku', reasoning: 'Mysle nad stawka...' },
      ],
      status_ogolny: 'w_toku',
      updated_at: '2026-09-09T14:00:00'
    };
    fs.writeFileSync(path.join(stanDir, 'stan.json'), JSON.stringify(stan), 'utf-8');

    // 3. Sprawdz getPipelines
    const pipelines = engine.getPipelines();
    expect(pipelines).toHaveLength(1);
    const p = pipelines[0];
    expect(p.id).toBe('useme-oferty');
    expect(p.kroki).toHaveLength(2);

    // Krok 1 powinien miec stan z wykonania na zywo
    expect(p.kroki[0].id).toBe(1);
    expect(p.kroki[0].nazwa).toBe('Wycena i dni');
    expect(p.kroki[0].status).toBe('w_toku');
    expect(p.kroki[0].reasoning).toBe('Mysle nad stawka...');

    // Krok 2 NIE POWINIEN ZNIKNAC - powinien czekac w kolejce
    expect(p.kroki[1].id).toBe(2);
    expect(p.kroki[1].nazwa).toBe('Tresc oferty');
    expect(p.kroki[1].status).toBe('w_kolejce');

    // Powinno zachowac uruchom z definicji
    expect(p.uruchom?.komenda).toBe('python');
  });
});
