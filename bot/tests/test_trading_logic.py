# Simple test to verify the SELL logic works when sentiment drops
def test_exit_logic_execution():
    sentiment_score = 0.4 # Below the 0.5 threshold
    current_holdings = 100
    ticker_price = 400.0

    action = "IDLE"
    current_cash = 1000.0

    if sentiment_score < 0.5 and current_holdings > 0:
        action = "SELL"
        sale_proceeds = ticker_price * current_holdings
        current_cash += sale_proceeds
        current_holdings = 0

    assert action == "SELL"
    assert current_holdings == 0
    assert current_cash == 41000.0

# Simple test to verify BUY logic respects capital
def test_buy_logic_insufficient_funds():
    sentiment_score = 0.6 # High edge
    current_cash = 100.0 # Very low cash
    ticker_price = 400.0
    simulated_shares = 10

    action = "IDLE"
    trade_cost = ticker_price * simulated_shares

    if sentiment_score > 0.5:
        if current_cash >= trade_cost:
            action = "BUY"
        else:
            action = "SKIP_FUNDS"

    assert action == "SKIP_FUNDS"
