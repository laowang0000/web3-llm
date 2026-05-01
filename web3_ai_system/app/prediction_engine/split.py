import pandas as pd


def time_series_train_test_split(
    frame: pd.DataFrame,
    test_ratio: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not 0 < test_ratio < 1:
        raise ValueError("test_ratio must be between 0 and 1")

    split_index = int(len(frame) * (1 - test_ratio))
    if split_index <= 0 or split_index >= len(frame):
        raise ValueError("Not enough rows for a chronological train/test split")

    train_frame = frame.iloc[:split_index].copy()
    test_frame = frame.iloc[split_index:].copy()
    return train_frame, test_frame
