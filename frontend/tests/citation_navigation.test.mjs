import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

describe('Citation Navigation & Routing Logic', () => {
  // Test citation navigation resolver
  function resolveCitationNavigation(citation, activeBatchNumber) {
    if (!citation || !citation.entity) {
      return { tab: null, id: null, extraId: null, valid: false };
    }

    const entity = citation.entity.toLowerCase();
    const id = citation.id || citation.source_reference;

    if (!id || typeof id !== 'string') {
      return { tab: null, id: null, extraId: null, valid: false };
    }

    if (entity === 'batches') {
      return { tab: 'batches', id: id.trim(), extraId: null, valid: true };
    } else if (entity === 'inspections') {
      return { tab: 'inspections', id: id.trim(), extraId: null, valid: true };
    } else if (entity === 'defects') {
      return { tab: 'defects', id: id.trim(), extraId: null, valid: true };
    } else if (entity === 'corrective_actions') {
      // Must map to capa with capaId in extraId slot, not defectId slot
      return { tab: 'capa', id: undefined, extraId: id.trim(), valid: true };
    } else if (entity === 'batch_decisions' || entity === 'release_gates') {
      return { tab: 'release-gates', id: activeBatchNumber || id.trim(), extraId: null, valid: true };
    }

    return { tab: null, id: null, extraId: null, valid: false };
  }

  test('Resolves batch citations to batches tab with exact batch UUID or number', () => {
    const res = resolveCitationNavigation(
      { entity: 'batches', id: 'f62daf97-f7a6-4c33-a785-9671c4a64b59', source_reference: 'BATCH-IDEM-f93aad' },
      'BATCH-IDEM-f93aad'
    );
    assert.equal(res.valid, true);
    assert.equal(res.tab, 'batches');
    assert.equal(res.id, 'f62daf97-f7a6-4c33-a785-9671c4a64b59');
  });

  test('Resolves inspection citations to inspections tab with inspection UUID', () => {
    const res = resolveCitationNavigation(
      { entity: 'inspections', id: '86088d10-0622-4caa-a3a4-0088eb89dae2', source_reference: 'INSP-20261022-782EB8' },
      'BATCH-IDEM-f93aad'
    );
    assert.equal(res.valid, true);
    assert.equal(res.tab, 'inspections');
    assert.equal(res.id, '86088d10-0622-4caa-a3a4-0088eb89dae2');
  });

  test('Resolves defect citations to defects tab with target defect identifier', () => {
    const res = resolveCitationNavigation(
      { entity: 'defects', id: '038d36e0-481a-4a68-b0d8-0003e26a6cf8', source_reference: 'DEF-20261022-0009' },
      'BATCH-IDEM-f93aad'
    );
    assert.equal(res.valid, true);
    assert.equal(res.tab, 'defects');
    assert.equal(res.id, '038d36e0-481a-4a68-b0d8-0003e26a6cf8');
  });

  test('Resolves corrective action citations to capa tab without triggering create-modal defect assignment', () => {
    const res = resolveCitationNavigation(
      { entity: 'corrective_actions', id: 'b123997d-47f9-4c65-a537-78d48fbd0134', source_reference: 'CAPA-20261022-0007' },
      'BATCH-IDEM-f93aad'
    );
    assert.equal(res.valid, true);
    assert.equal(res.tab, 'capa');
    assert.equal(res.id, undefined); // defectId is undefined
    assert.equal(res.extraId, 'b123997d-47f9-4c65-a537-78d48fbd0134'); // capaId set
  });

  test('Resolves batch decisions to release-gates tab targeting the queried batch', () => {
    const res = resolveCitationNavigation(
      { entity: 'batch_decisions', id: 'dec-1234', source_reference: 'DECISION-HOLD' },
      'BATCH-IDEM-f93aad'
    );
    assert.equal(res.valid, true);
    assert.equal(res.tab, 'release-gates');
    assert.equal(res.id, 'BATCH-IDEM-f93aad');
  });

  test('Gracefully rejects missing, invalid, or unsupported citation entities without throwing errors', () => {
    assert.equal(resolveCitationNavigation(null).valid, false);
    assert.equal(resolveCitationNavigation({}).valid, false);
    assert.equal(resolveCitationNavigation({ entity: 'unknown_entity', id: '123' }).valid, false);
    assert.equal(resolveCitationNavigation({ entity: 'batches', id: '' }).valid, false);
  });
});
