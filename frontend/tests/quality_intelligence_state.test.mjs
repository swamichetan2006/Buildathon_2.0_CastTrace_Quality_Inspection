import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

describe('Quality Intelligence State Management & Batch Isolation', () => {
  // Simulates the state machine in QualityIntelligencePage
  class QualityIntelligenceStateManager {
    constructor() {
      this.selectedBatchIdentifier = '';
      this.displayedBatchIdentifier = null;
      this.question = '';
      this.queryResult = null;
      this.queryError = null;
      this.isPending = false;
    }

    handleBatchChange(newBatch) {
      this.selectedBatchIdentifier = newBatch;
      this.queryResult = null;
      this.displayedBatchIdentifier = null;
      this.queryError = null;
    }

    handleSubmitStart(effectiveBatch, promptText) {
      if (!effectiveBatch.trim() || !promptText.trim() || this.isPending) {
        return false;
      }
      this.isPending = true;
      this.queryResult = null;
      this.displayedBatchIdentifier = null;
      this.queryError = null;
      return true;
    }

    handleQuerySuccess(data, batchIdentifier) {
      this.isPending = false;
      this.queryResult = data;
      this.displayedBatchIdentifier = batchIdentifier;
      this.queryError = null;
    }

    handleQueryError(err) {
      this.isPending = false;
      this.queryResult = null;
      this.displayedBatchIdentifier = null;
      this.queryError = err;
    }

    isResultVisible(effectiveBatch) {
      return (
        this.queryResult !== null &&
        !this.isPending &&
        this.displayedBatchIdentifier === effectiveBatch
      );
    }
  }

  test('Switching batch clears stale query results and previous errors', () => {
    const sm = new QualityIntelligenceStateManager();
    sm.handleBatchChange('BATCH-IDEM-f93aad');
    sm.handleSubmitStart('BATCH-IDEM-f93aad', 'Summarise this batch');
    sm.handleQuerySuccess(
      { answer: 'Summary for IDEM', deterministic_metrics: { release_blockers_count: 6 } },
      'BATCH-IDEM-f93aad'
    );

    assert.equal(sm.isResultVisible('BATCH-IDEM-f93aad'), true);
    assert.equal(sm.queryResult.deterministic_metrics.release_blockers_count, 6);

    // User switches to BATCH-QA-c7ab67
    sm.handleBatchChange('BATCH-QA-c7ab67');
    assert.equal(sm.queryResult, null);
    assert.equal(sm.displayedBatchIdentifier, null);
    assert.equal(sm.isResultVisible('BATCH-QA-c7ab67'), false);
    assert.equal(sm.isResultVisible('BATCH-IDEM-f93aad'), false);
  });

  test('BATCH-QA-c7ab67 cannot display data from BATCH-IDEM-f93aad', () => {
    const sm = new QualityIntelligenceStateManager();
    sm.handleBatchChange('BATCH-IDEM-f93aad');
    sm.handleSubmitStart('BATCH-IDEM-f93aad', 'Quality check');
    sm.handleQuerySuccess(
      { answer: 'IDEM data', deterministic_metrics: { release_blockers_count: 6 } },
      'BATCH-IDEM-f93aad'
    );

    // If effective batch is BATCH-QA-c7ab67, IDEM result must NOT be visible
    assert.equal(sm.isResultVisible('BATCH-QA-c7ab67'), false);
  });

  test('Submitting a new query clears previous result immediately', () => {
    const sm = new QualityIntelligenceStateManager();
    sm.handleBatchChange('BATCH-IDEM-f93aad');
    sm.handleSubmitStart('BATCH-IDEM-f93aad', 'First query');
    sm.handleQuerySuccess({ answer: 'First answer' }, 'BATCH-IDEM-f93aad');

    assert.equal(sm.queryResult !== null, true);

    // User submits second query
    sm.handleSubmitStart('BATCH-IDEM-f93aad', 'Second query');
    assert.equal(sm.queryResult, null);
    assert.equal(sm.isResultVisible('BATCH-IDEM-f93aad'), false);
  });

  test('Query failure after successful response leaves zero stale metrics', () => {
    const sm = new QualityIntelligenceStateManager();
    sm.handleBatchChange('BATCH-IDEM-f93aad');
    sm.handleSubmitStart('BATCH-IDEM-f93aad', 'Quality summary');
    sm.handleQuerySuccess(
      { answer: 'Valid summary', deterministic_metrics: { confirmed_defects_count: 1 } },
      'BATCH-IDEM-f93aad'
    );
    assert.equal(sm.isResultVisible('BATCH-IDEM-f93aad'), true);

    // User asks "who is pm of india?" which fails with OUT_OF_SCOPE_QUESTION
    sm.handleSubmitStart('BATCH-IDEM-f93aad', 'who is pm of india?');
    sm.handleQueryError({
      status: 400,
      code: 'OUT_OF_SCOPE_QUESTION',
      message: 'I can answer questions about production batches, inspections, confirmed defects, CAPAs, and release-gate evidence. Please ask a quality-related question.',
    });

    assert.equal(sm.queryResult, null);
    assert.equal(sm.displayedBatchIdentifier, null);
    assert.equal(sm.isResultVisible('BATCH-IDEM-f93aad'), false);
    assert.equal(sm.queryError.code, 'OUT_OF_SCOPE_QUESTION');
  });
});
