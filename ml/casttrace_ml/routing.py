"""Three-tier routing mechanism with explicit metric definitions and Wilson confidence intervals."""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


def wilson_score_interval(successes: int, total: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Compute the Wilson score confidence interval for a binomial proportion.
    
    Formula:
        (p_hat + z^2/(2n) +/- z * sqrt(p_hat*(1-p_hat)/n + z^2/(4n^2))) / (1 + z^2/n)
    """
    if total <= 0:
        return (0.0, 0.0)
    
    # z-value for confidence level
    # 95% -> 1.95996, 99% -> 2.57583
    if confidence == 0.95:
        z = 1.959963984540054
    elif confidence == 0.99:
        z = 2.5758293035489004
    else:
        # Standard normal inverse approximation
        z = 1.95996
        
    p_hat = float(successes) / float(total)
    denominator = 1.0 + (z ** 2) / total
    centre_adjusted = (p_hat + (z ** 2) / (2.0 * total)) / denominator
    margin = (z / denominator) * math.sqrt(
        (p_hat * (1.0 - p_hat) / total) + ((z ** 2) / (4.0 * (total ** 2)))
    )
    
    lower = max(0.0, centre_adjusted - margin)
    upper = min(1.0, centre_adjusted + margin)
    return (round(lower, 4), round(upper, 4))


@dataclass
class RoutingThresholds:
    t_ok: float       # Scores <= t_ok routed to LIKELY_OK
    t_def: float      # Scores >= t_def routed to LIKELY_DEFECTIVE
    
    def route(self, score_defective: float, is_unfamiliar: bool = False, quality_passed: bool = True) -> str:
        """Route a single prediction score to LIKELY_OK, NEEDS_REVIEW, or LIKELY_DEFECTIVE."""
        if not quality_passed or is_unfamiliar:
            return "NEEDS_REVIEW"
        if score_defective <= self.t_ok:
            return "LIKELY_OK"
        elif score_defective >= self.t_def:
            return "LIKELY_DEFECTIVE"
        else:
            return "NEEDS_REVIEW"


@dataclass
class RoutingEvaluationResult:
    thresholds: RoutingThresholds
    total_samples: int
    total_defective: int
    total_good: int
    
    # Counts per bucket
    count_likely_ok: int
    count_needs_review: int
    count_likely_defective: int
    
    # Coverage
    routing_coverage: float   # (likely_ok + likely_defective) / total
    review_rate: float        # needs_review / total
    
    # LIKELY_DEFECTIVE precision
    likely_def_true_def: int
    likely_def_precision: float
    likely_def_precision_ci: Tuple[float, float]
    
    # LIKELY_OK miss rate (against all actual defectives)
    likely_ok_false_negatives: int
    likely_ok_miss_rate: float
    likely_ok_miss_rate_ci: Tuple[float, float]
    
    # False Omission Rate (FOR): defective in likely_ok / total likely_ok
    false_omission_rate: float
    false_omission_rate_ci: Tuple[float, float]
    
    # Target status
    target_precision_met: bool
    target_miss_rate_met: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "thresholds": {"t_ok": self.thresholds.t_ok, "t_def": self.thresholds.t_def},
            "total_samples": self.total_samples,
            "total_defective": self.total_defective,
            "total_good": self.total_good,
            "counts": {
                "LIKELY_OK": self.count_likely_ok,
                "NEEDS_REVIEW": self.count_needs_review,
                "LIKELY_DEFECTIVE": self.count_likely_defective,
            },
            "coverage": {
                "automated_routing_coverage": round(self.routing_coverage, 4),
                "review_rate": round(self.review_rate, 4),
            },
            "likely_defective_precision": {
                "value": round(self.likely_def_precision, 4),
                "numerator": self.likely_def_true_def,
                "denominator": self.count_likely_defective,
                "ci_95": list(self.likely_def_precision_ci),
                "target_met": self.target_precision_met,
            },
            "likely_ok_miss_rate": {
                "value": round(self.likely_ok_miss_rate, 4),
                "numerator": self.likely_ok_false_negatives,
                "denominator": self.total_defective,
                "ci_95": list(self.likely_ok_miss_rate_ci),
                "target_met": self.target_miss_rate_met,
            },
            "false_omission_rate": {
                "value": round(self.false_omission_rate, 4),
                "numerator": self.likely_ok_false_negatives,
                "denominator": self.count_likely_ok,
                "ci_95": list(self.false_omission_rate_ci),
            },
        }


def evaluate_routing(
    scores: np.ndarray,
    labels: np.ndarray,  # 1 for DEFECTIVE, 0 for GOOD
    thresholds: RoutingThresholds,
    target_precision: float = 0.90,
    target_miss_rate: float = 0.05,
) -> RoutingEvaluationResult:
    """Evaluate routing metrics for a given set of scores and ground truth labels."""
    total_samples = len(labels)
    total_defective = int(np.sum(labels == 1))
    total_good = int(np.sum(labels == 0))
    
    # Route scores
    routes = []
    for s in scores:
        if s <= thresholds.t_ok:
            routes.append("LIKELY_OK")
        elif s >= thresholds.t_def:
            routes.append("LIKELY_DEFECTIVE")
        else:
            routes.append("NEEDS_REVIEW")
            
    routes = np.array(routes)
    count_likely_ok = int(np.sum(routes == "LIKELY_OK"))
    count_needs_review = int(np.sum(routes == "NEEDS_REVIEW"))
    count_likely_defective = int(np.sum(routes == "LIKELY_DEFECTIVE"))
    
    routing_coverage = (count_likely_ok + count_likely_defective) / total_samples if total_samples > 0 else 0.0
    review_rate = count_needs_review / total_samples if total_samples > 0 else 0.0
    
    # 1. LIKELY_DEFECTIVE precision
    # true DEFECTIVE images routed LIKELY_DEFECTIVE / all images routed LIKELY_DEFECTIVE
    likely_def_true_def = int(np.sum((routes == "LIKELY_DEFECTIVE") & (labels == 1)))
    likely_def_precision = (likely_def_true_def / count_likely_defective) if count_likely_defective > 0 else 0.0
    likely_def_precision_ci = wilson_score_interval(likely_def_true_def, count_likely_defective)
    
    # 2. LIKELY_OK miss rate
    # actual DEFECTIVE images routed LIKELY_OK / all actual DEFECTIVE validation images
    likely_ok_false_negatives = int(np.sum((routes == "LIKELY_OK") & (labels == 1)))
    likely_ok_miss_rate = (likely_ok_false_negatives / total_defective) if total_defective > 0 else 0.0
    likely_ok_miss_rate_ci = wilson_score_interval(likely_ok_false_negatives, total_defective)
    
    # 3. False Omission Rate (FOR)
    # actual DEFECTIVE images routed LIKELY_OK / all images routed LIKELY_OK
    false_omission_rate = (likely_ok_false_negatives / count_likely_ok) if count_likely_ok > 0 else 0.0
    false_omission_rate_ci = wilson_score_interval(likely_ok_false_negatives, count_likely_ok)
    
    target_prec_met = (likely_def_precision >= target_precision) if count_likely_defective > 0 else False
    target_miss_met = (likely_ok_miss_rate <= target_miss_rate)
    
    return RoutingEvaluationResult(
        thresholds=thresholds,
        total_samples=total_samples,
        total_defective=total_defective,
        total_good=total_good,
        count_likely_ok=count_likely_ok,
        count_needs_review=count_needs_review,
        count_likely_defective=count_likely_defective,
        routing_coverage=routing_coverage,
        review_rate=review_rate,
        likely_def_true_def=likely_def_true_def,
        likely_def_precision=likely_def_precision,
        likely_def_precision_ci=likely_def_precision_ci,
        likely_ok_false_negatives=likely_ok_false_negatives,
        likely_ok_miss_rate=likely_ok_miss_rate,
        likely_ok_miss_rate_ci=likely_ok_miss_rate_ci,
        false_omission_rate=false_omission_rate,
        false_omission_rate_ci=false_omission_rate_ci,
        target_precision_met=target_prec_met,
        target_miss_rate_met=target_miss_met,
    )


def optimize_routing_thresholds(
    val_scores: np.ndarray,
    val_labels: np.ndarray,
    target_precision: float = 0.90,
    target_miss_rate: float = 0.05,
    resolution: float = 0.01,
) -> Tuple[RoutingThresholds, RoutingEvaluationResult]:
    """Search for thresholds that satisfy the proposed targets while maximizing useful automated coverage."""
    best_eval = None
    best_thresholds = None
    best_coverage = -1.0
    
    # t_ok grid: 0.01 to 0.50
    t_ok_candidates = np.arange(0.01, 0.501, resolution)
    # t_def grid: 0.50 to 0.99
    t_def_candidates = np.arange(0.50, 0.991, resolution)
    
    fallback_best = None
    fallback_score = -1.0
    
    for t_ok in t_ok_candidates:
        for t_def in t_def_candidates:
            if t_ok >= t_def:
                continue
            th = RoutingThresholds(t_ok=round(float(t_ok), 4), t_def=round(float(t_def), 4))
            res = evaluate_routing(val_scores, val_labels, th, target_precision, target_miss_rate)
            
            # Check if both targets are strictly satisfied
            if res.target_precision_met and res.target_miss_rate_met:
                if res.routing_coverage > best_coverage:
                    best_coverage = res.routing_coverage
                    best_eval = res
                    best_thresholds = th
            else:
                # Track best candidate even if one target is missed
                combined = (res.likely_def_precision / target_precision) - (res.likely_ok_miss_rate / target_miss_rate) + res.routing_coverage
                if combined > fallback_score:
                    fallback_score = combined
                    fallback_best = (th, res)
                    
    if best_thresholds is not None:
        return best_thresholds, best_eval
    
    # If targets were unattainable on this validation set, do not silently relax:
    # return the fallback best and mark target flags clearly
    th, res = fallback_best
    return th, res
