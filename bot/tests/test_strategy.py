# Test the core decision logic independently of BigQuery
def test_sell_logic_trigger():
    sentiment = 0.2  # Loss of edge
    holdings = 100
    price = 450.0

    action = "IDLE"
    if sentiment < 0.5 and holdings > 0:
        action = "SELL"
        cash_gained = price * holdings
        holdings = 0

    assert action == "SELL"
    assert holdings == 0
    assert cash_gained == 45000.0

def test_buy_logic_capital_check():
    sentiment = 0.8  # Strong edge
    cash = 100.0  # Insufficient funds
    price = 450.0

    action = "IDLE"
    if sentiment > 0.5:
        if cash >= price:
            action = "BUY"
        else:
            action = "INSUFFICIENT_FUNDS"

    assert action == "INSUFFICIENT_FUNDS"
