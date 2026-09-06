"""Unit tests for clinical dataset loading and safe fallbacks."""

from src.data.loader import ClinicalDatasetLoader


def test_curated_sample_loading():
    loader = ClinicalDatasetLoader()
    cases = loader.load_curated_sample()
    assert len(cases) >= 10
    first = cases[0]
    assert "question" in first
    assert "gold_diagnosis" in first
    assert "specialty" in first


def test_pubmedqa_loader():
    loader = ClinicalDatasetLoader()
    cases = loader.load_pubmedqa(limit=2)
    assert isinstance(cases, list)
    if cases:
        assert "question" in cases[0]
        assert "gold_diagnosis" in cases[0]


def test_meddialog_loader():
    loader = ClinicalDatasetLoader()
    cases = loader.load_meddialog(limit=2)
    assert isinstance(cases, list)
    if cases:
        assert "question" in cases[0]


def test_stratified_benchmark_assembly():
    loader = ClinicalDatasetLoader()
    # Test assembling a 5-case stratified mix
    cases = loader.get_benchmark_cases(requested_count=5, source="curated")
    assert len(cases) == 5

