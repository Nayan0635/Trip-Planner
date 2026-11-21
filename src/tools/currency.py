
from __future__ import annotations
from langchain.tools import tool
import requests

BASE_URL = "https://api.frankfurter.app/latest"


@tool
def convert_currency(amount: float, source_currency: str, target_currency: str) -> dict:
    '''Converts an amount between currencies using current exchange rates'''
    source_currency = source_currency.upper()
    target_currency = target_currency.upper()

    response = requests.get(
        BASE_URL,
        params={"amount": amount, "from": source_currency, "to": target_currency},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    rates = data.get("rates", {})
    if target_currency not in rates:
        raise ValueError(f"Unsupported currency pair: {source_currency} -> {target_currency}")

    converted_amount = rates[target_currency]
    exchange_rate = converted_amount / amount if amount else None

    return {
        "amount": amount,
        "source_currency": source_currency,
        "target_currency": target_currency,
        "exchange_rate": round(exchange_rate, 6) if exchange_rate is not None else None,
        "converted_amount": round(converted_amount, 2),
        "date": data.get("date"),
    }
