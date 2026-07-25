import numpy as np
import pandas as pd

from data.loader import load_csv
from data.cleaner import fill_na_values


def buy_sell_randomly(data: pd.DataFrame, capital: float = 10000.0) -> list[float]:
    prices = data.iloc[:, 0].to_numpy()
    is_buy = np.random.random(len(prices)) < 0.5

    number_of_stocks = 0.0
    portfolio_values = []

    for price, buy in zip(prices, is_buy):
        if buy and capital >= price:
            number_of_stocks = capital / price
            capital = 0.0
        elif not buy and number_of_stocks > 0:
            capital += number_of_stocks * price
            number_of_stocks = 0.0
        portfolio_values.append(capital + number_of_stocks * price)

    return portfolio_values

def main():
    loaded_data = load_csv("data/raw/EQNR_OL_monthly.csv")
    loaded_data = fill_na_values(loaded_data) # ffill NA values in the DataFrame
    print(buy_sell_randomly(loaded_data, capital=10000.0))


if __name__ == "__main__":
    main()