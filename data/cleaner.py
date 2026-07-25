import pandas as pd

def fill_na_values(data: pd.DataFrame) -> pd.DataFrame:
    """
    Fill missing NA values in the DataFrame using forward fill method.

    Parameters:
    data (pd.DataFrame): Input DataFrame

    Returns:
    pd.DataFrame: DataFrame with missing NA values filled.
    """
    return data.ffill()