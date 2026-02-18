#!/bin/bash
# Quick script to check current portfolio state

bq query --nouse_legacy_sql --format=pretty \
 'SELECT asset_name, cash_balance, holdings, avg_price, last_updated
 FROM `utopian-calling-429014-r9.trading_data.portfolio`
 ORDER BY asset_name'
