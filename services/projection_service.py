"""Kivy'den bağımsız RK4 servet projeksiyonu ve what-if senaryoları."""

import math


def project_wealth_series(
        initial_wealth, daily_income, daily_expense, days=30, r=0.0001):
    """`dW/dt = rW + I - E` denklemini günlük RK4 adımlarıyla çözer.

    Gün 0 dahil `[(0, W0), ..., (days, W_days)]` döndürür.
    """
    days = int(days)
    if days < 0:
        raise ValueError("Projeksiyon ufku negatif olamaz")

    values = {
        "initial_wealth": float(initial_wealth),
        "daily_income": float(daily_income),
        "daily_expense": float(daily_expense),
        "r": float(r),
    }
    if not all(math.isfinite(value) for value in values.values()):
        raise ValueError("Projeksiyon girdileri sonlu sayılar olmalıdır")

    wealth = values["initial_wealth"]
    income = values["daily_income"]
    expense = values["daily_expense"]
    rate = values["r"]
    dt = 1.0
    series = [(0, wealth)]

    def derivative(_time, current_wealth):
        return rate * current_wealth + income - expense

    time = 0.0
    for day in range(1, days + 1):
        k1 = derivative(time, wealth)
        k2 = derivative(time + dt / 2, wealth + dt / 2 * k1)
        k3 = derivative(time + dt / 2, wealth + dt / 2 * k2)
        k4 = derivative(time + dt, wealth + dt * k3)
        wealth += (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        time += dt
        series.append((day, wealth))

    return series


def project_final_wealth(
        initial_wealth, daily_income, daily_expense, days=30, r=0.0001):
    """Mevcut dashboard kartı için geriye uyumlu tek nihai değer."""
    return project_wealth_series(
        initial_wealth, daily_income, daily_expense, days, r,
    )[-1][1]


def simulate_scenario(
        base_balance,
        base_daily_income,
        base_daily_expense,
        income_delta_pct=0.0,
        expense_delta_pct=0.0,
        r=0.0001,
        days=30,
        one_time_adjustment=0.0):
    """Taban ve what-if serilerini aynı parametre setiyle karşılaştırır.

    `one_time_adjustment` pozitifse ek gelir, negatifse tek seferlik giderdir
    ve senaryo serisinin gün-0 bakiyesine uygulanır.
    """
    base_balance = float(base_balance)
    base_income = float(base_daily_income)
    base_expense = float(base_daily_expense)
    income_pct = float(income_delta_pct)
    expense_pct = float(expense_delta_pct)
    adjustment = float(one_time_adjustment)
    days = int(days)

    scenario_income = base_income * (1.0 + income_pct / 100.0)
    scenario_expense = base_expense * (1.0 + expense_pct / 100.0)

    base_series = project_wealth_series(
        base_balance, base_income, base_expense, days, r,
    )
    scenario_series = project_wealth_series(
        base_balance + adjustment,
        scenario_income,
        scenario_expense,
        days,
        r,
    )
    base_final = base_series[-1][1]
    scenario_final = scenario_series[-1][1]

    return {
        "days": days,
        "base_series": base_series,
        "scenario_series": scenario_series,
        "base_final": base_final,
        "scenario_final": scenario_final,
        "difference": scenario_final - base_final,
        "goes_negative": any(value < 0 for _day, value in scenario_series),
        "inputs": {
            "base_balance": base_balance,
            "base_daily_income": base_income,
            "base_daily_expense": base_expense,
            "scenario_daily_income": scenario_income,
            "scenario_daily_expense": scenario_expense,
            "income_delta_pct": income_pct,
            "expense_delta_pct": expense_pct,
            "one_time_adjustment": adjustment,
            "r": float(r),
        },
    }
