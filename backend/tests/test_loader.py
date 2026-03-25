import pandas as pd
from app.data.loader import load_dataset, get_schema_summary


def test_get_schema_summary_contains_column_names():
    df = pd.DataFrame({
        "company_name": ["Acme", "Beta", "Gamma"],
        "arr": [1000000, 2000000, 3000000],
        "employee_count": [50, 100, 150],
    })
    summary = get_schema_summary(df)
    assert "company_name" in summary
    assert "arr" in summary
    assert "employee_count" in summary


def test_get_schema_summary_contains_row_count():
    df = pd.DataFrame({"x": [1, 2, 3]})
    summary = get_schema_summary(df)
    assert "3" in summary


def test_load_dataset_returns_dataframe():
    df = load_dataset()
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
