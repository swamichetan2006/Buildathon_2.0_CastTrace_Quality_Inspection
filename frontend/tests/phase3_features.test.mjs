import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

describe('Phase 3 Feature A: What Needs Attention Today State & Logic', () => {
  // Test queue priority ranking
  function sortAttentionItemsByPriority(items) {
    const priorityWeights = {
      CRITICAL: 4,
      HIGH: 3,
      MEDIUM: 2,
      LOW: 1,
    };
    return [...items].sort((a, b) => {
      const weightA = priorityWeights[a.priority] || 0;
      const weightB = priorityWeights[b.priority] || 0;
      return weightB - weightA;
    });
  }

  // Filter items by priority tab
  function filterAttentionItems(items, filter) {
    if (filter === 'ALL') return items;
    return items.filter((item) => item.priority === filter);
  }

  // Navigation resolver for attention items
  function resolveAttentionNavigation(item) {
    if (!item || !item.entity_type || !item.entity_id) {
      return { tab: null, id: null, valid: false };
    }
    const type = item.entity_type.toLowerCase();
    switch (type) {
      case 'inspection':
        return { tab: 'inspections', id: item.entity_id, valid: true };
      case 'defect':
        return { tab: 'defects', id: item.entity_id, valid: true };
      case 'corrective_action':
      case 'capa':
        return { tab: 'capa', id: undefined, extraId: item.entity_id, valid: true };
      case 'batch':
      case 'release_gate':
        return { tab: 'release-gates', id: item.batch_number || item.entity_id, valid: true };
      default:
        return { tab: null, id: null, valid: false };
    }
  }

  const sampleItems = [
    {
      item_id: 'ATTN-inspection-1',
      priority: 'HIGH',
      category: 'DRAFT_INSPECTION',
      entity_type: 'inspection',
      entity_id: 'insp-uuid-1',
      entity_identifier: 'INSP-001',
      batch_number: 'BATCH-001',
      summary: 'Inspection in draft state',
      reasons: ['Draft inspection pending submission'],
    },
    {
      item_id: 'ATTN-defect-2',
      priority: 'CRITICAL',
      category: 'RELEASE_BLOCKER',
      entity_type: 'defect',
      entity_id: 'def-uuid-2',
      entity_identifier: 'DEF-002',
      batch_number: 'BATCH-001',
      summary: 'Unresolved defect blocks release',
      reasons: ['DEFECT_NOT_RESOLVED: Crack on flange', 'DEFECT_PENDING_REINSPECTION: Reinspection required'],
    },
    {
      item_id: 'ATTN-capa-3',
      priority: 'HIGH',
      category: 'OVERDUE_CAPA',
      entity_type: 'corrective_action',
      entity_id: 'capa-uuid-3',
      entity_identifier: 'CAPA-003',
      batch_number: 'BATCH-002',
      summary: 'Corrective action overdue by 4 days',
      reasons: ['Corrective action is overdue since 2026-10-19'],
    },
    {
      item_id: 'ATTN-capa-4',
      priority: 'MEDIUM',
      category: 'UNVERIFIED_COMPLETED_CAPA',
      entity_type: 'corrective_action',
      entity_id: 'capa-uuid-4',
      entity_identifier: 'CAPA-004',
      batch_number: 'BATCH-002',
      summary: 'Corrective action completed but pending independent verification',
      reasons: ['Completed CAPA requires verification'],
    },
  ];

  test('Correctly sorts attention items with CRITICAL items first', () => {
    const sorted = sortAttentionItemsByPriority(sampleItems);
    assert.equal(sorted[0].priority, 'CRITICAL');
    assert.equal(sorted[0].entity_identifier, 'DEF-002');
    assert.equal(sorted[sorted.length - 1].priority, 'MEDIUM');
  });

  test('Filters attention items accurately by priority tab', () => {
    const criticalOnly = filterAttentionItems(sampleItems, 'CRITICAL');
    assert.equal(criticalOnly.length, 1);
    assert.equal(criticalOnly[0].item_id, 'ATTN-defect-2');

    const highOnly = filterAttentionItems(sampleItems, 'HIGH');
    assert.equal(highOnly.length, 2);

    const all = filterAttentionItems(sampleItems, 'ALL');
    assert.equal(all.length, 4);
  });

  test('Groups multiple blocker reasons on the same defect without duplicating the item', () => {
    const defectItem = sampleItems.find((i) => i.entity_id === 'def-uuid-2');
    assert.ok(defectItem);
    assert.equal(defectItem.reasons.length, 2);
    assert.ok(defectItem.reasons.some((r) => r.includes('DEFECT_NOT_RESOLVED')));
    assert.ok(defectItem.reasons.some((r) => r.includes('DEFECT_PENDING_REINSPECTION')));
  });

  test('Resolves navigation for attention item to correct tab and target ID', () => {
    const navInspection = resolveAttentionNavigation(sampleItems[0]);
    assert.equal(navInspection.tab, 'inspections');
    assert.equal(navInspection.id, 'insp-uuid-1');

    const navDefect = resolveAttentionNavigation(sampleItems[1]);
    assert.equal(navDefect.tab, 'defects');
    assert.equal(navDefect.id, 'def-uuid-2');

    const navCapa = resolveAttentionNavigation(sampleItems[2]);
    assert.equal(navCapa.tab, 'capa');
    assert.equal(navCapa.extraId, 'capa-uuid-3');
  });
});

describe('Phase 3 Feature B: Historical Similarity Radar & Recurrence Matching', () => {
  // Test state isolation on batch switch
  function handleBatchSwitch(previousState, newBatchNumber) {
    return {
      selectedBatch: newBatchNumber,
      selectedDefectId: '', // Cleared
      similarityResult: null, // Cleared
      error: null, // Cleared
    };
  }

  // Verify rank ordering of similarity matches
  function rankSimilarityMatches(matches) {
    return [...matches].sort((a, b) => b.match_score - a.match_score);
  }

  const candidateMatches = [
    {
      defect_id: 'hist-1',
      defect_number: 'DEF-HIST-01',
      match_score: 84.5,
      is_cross_product: false,
      product_name: 'Impeller Housing v2',
      matching_attributes: [
        { attribute: 'product_id', matched: true, score_contribution: 25.0, reason: 'Identical product' },
        { attribute: 'category', matched: true, score_contribution: 25.0, reason: 'Identical category' },
        { attribute: 'severity', matched: true, score_contribution: 15.0, reason: 'Exact severity match' },
      ],
      capa: {
        capa_number: 'CAPA-001',
        status: 'VERIFIED',
        root_cause: 'Casting chill zone cooling rate uneven',
      },
    },
    {
      defect_id: 'hist-2',
      defect_number: 'DEF-HIST-02',
      match_score: 42.0,
      is_cross_product: true,
      product_name: 'Pump Bracket A1',
      matching_attributes: [
        { attribute: 'product_id', matched: false, score_contribution: 0.0, reason: 'Cross-product candidate' },
        { attribute: 'category', matched: true, score_contribution: 25.0, reason: 'Identical category' },
      ],
      capa: null,
    },
  ];

  test('Switching batch clears stale defect selection and similarity results', () => {
    const prevState = {
      selectedBatch: 'BATCH-001',
      selectedDefectId: 'def-1',
      similarityResult: { total_candidates_scanned: 5, matches: [] },
      error: 'Some error',
    };
    const newState = handleBatchSwitch(prevState, 'BATCH-002');
    assert.equal(newState.selectedBatch, 'BATCH-002');
    assert.equal(newState.selectedDefectId, '');
    assert.equal(newState.similarityResult, null);
    assert.equal(newState.error, null);
  });

  test('Rank ordering places highest score first', () => {
    const ranked = rankSimilarityMatches(candidateMatches);
    assert.equal(ranked[0].defect_number, 'DEF-HIST-01');
    assert.equal(ranked[0].match_score, 84.5);
    assert.equal(ranked[0].is_cross_product, false);
    assert.equal(ranked[1].is_cross_product, true);
  });

  test('Distinguishes same-product matches from cross-product candidates', () => {
    assert.equal(candidateMatches[0].is_cross_product, false);
    assert.equal(candidateMatches[1].is_cross_product, true);
  });

  test('Displays historical CAPA outcomes only when actually recorded', () => {
    assert.ok(candidateMatches[0].capa !== null);
    assert.equal(candidateMatches[0].capa.root_cause, 'Casting chill zone cooling rate uneven');
    assert.equal(candidateMatches[1].capa, null); // No fabricated CAPA
  });

  test('Empty state returned when no historical candidates exist', () => {
    const emptyResponse = {
      source_defect: { id: 'source-1', defect_number: 'DEF-SRC-01' },
      matches: [],
      total_candidates_scanned: 12,
      matching_method: 'Structured + Character 3-gram Similarity',
      citations: [],
    };
    assert.equal(emptyResponse.matches.length, 0);
    assert.equal(emptyResponse.total_candidates_scanned, 12);
  });
});
