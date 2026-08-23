from __future__ import annotations

from math import sqrt


def classification_metrics(labels: list[int], probabilities: list[float], threshold: float = 0.5) -> dict:
    if len(labels) != len(probabilities):
        raise ValueError("labels and probabilities must have equal length")
    n = len(labels)
    if not n:
        return {"samples": 0, "accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "roc_auc": None, "brier_score": 0.0, "confusion_matrix": {"tp": 0, "tn": 0, "fp": 0, "fn": 0}}
    preds = [1 if p >= threshold else 0 for p in probabilities]
    tp = sum(y == 1 and p == 1 for y, p in zip(labels, preds)); tn = sum(y == 0 and p == 0 for y, p in zip(labels, preds))
    fp = sum(y == 0 and p == 1 for y, p in zip(labels, preds)); fn = sum(y == 1 and p == 0 for y, p in zip(labels, preds))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    positives = [(p, y) for p, y in zip(probabilities, labels) if y == 1]
    negatives = [(p, y) for p, y in zip(probabilities, labels) if y == 0]
    auc = None
    if positives and negatives:
        wins = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p, _ in positives for n, _ in negatives)
        auc = wins / (len(positives) * len(negatives))
    brier = sum((p - y) ** 2 for p, y in zip(probabilities, labels)) / n
    return {"samples": n, "accuracy": (tp + tn) / n, "precision": precision, "recall": recall, "f1": f1, "roc_auc": auc, "brier_score": brier, "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn}}


def trading_metrics(returns: list[float]) -> dict:
    if not returns:
        return {"trades": 0, "net_return": 0.0, "win_rate": 0.0, "profit_factor": None, "max_drawdown": 0.0, "sharpe_like": 0.0}
    equity = 1.0; peak = 1.0; max_dd = 0.0
    wins = [r for r in returns if r > 0]; losses = [r for r in returns if r < 0]
    for r in returns:
        equity *= 1 + r; peak = max(peak, equity); max_dd = max(max_dd, (peak - equity) / peak)
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    return {"trades": len(returns), "net_return": equity - 1, "win_rate": len(wins) / len(returns), "profit_factor": sum(wins) / abs(sum(losses)) if losses else None, "max_drawdown": max_dd, "sharpe_like": mean / sqrt(variance) if variance else 0.0}
