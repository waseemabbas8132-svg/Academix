"""Public evaluation-pipeline API consumed by the FastAPI application."""

from inference.evaluation_pipeline import EvaluationPipeline, EvaluationRequest

__all__ = ["EvaluationPipeline", "EvaluationRequest"]
