from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).parent
CSV_PATH = DATA_DIR / "sample_data.csv"


def load_dataset(path: Path = CSV_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def get_schema_summary(df: pd.DataFrame) -> str:
    lines = [f"Dataset: {len(df)} rows, {len(df.columns)} columns\n"]
    lines.append("Columns:")

    for col in df.columns:
        dtype = df[col].dtype
        samples = df[col].dropna().head(3).tolist()
        sample_str = ", ".join(str(s) for s in samples)
        line = f"  - {col} ({dtype}): e.g. {sample_str}"

        if pd.api.types.is_numeric_dtype(df[col]):
            line += f" | min={df[col].min()}, max={df[col].max()}, mean={df[col].mean():.2f}"

        lines.append(line)

    return "\n".join(lines)
