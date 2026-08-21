"""TANI ARACI — kalıcı kapı DEĞİL. projection_service hassasiyet ölçümü.

A (mevcut float RK4) / B (yüksek hassasiyetli Decimal RK4) / C (analitik
referans) üçlüsünü aynı vakalar üzerinde koşturur. Üretim kodu
DEĞİŞTİRİLMEZ; `project_wealth_series` olduğu gibi çağrılır.

ÖLÇÜMÜN SONUCU (karar): RK4 çekirdeği bilinçli olarak float kalır — 22
vakanın 21'inde kuruş aynı çıktı ve Decimal çekirdek 4,1x maliyetliydi.

Bilerek CI kapısı DEĞİL ve test paketine bağlı değil: ürettiği sayılar
kayan nokta aritmetiğinin özellikleri, uygulamanın verdiği sözler değil.
Bir eşik koymak, donanım/kütüphane farklarında anlamsız kırmızılar üretirdi.

Çalıştırma:
    python -m scripts.audit.measure_projection_precision

Ayrıştırma:
    |A - B|  -> float temsil/birikim hatası   (aynı algoritma, farklı aritmetik)
    |B - C|  -> RK4 kesme hatası              (aynı aritmetik, farklı yöntem)
    |A - C|  -> mevcut toplam hata
"""

import sys
import time as _time
from decimal import Decimal, getcontext, localcontext
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

from services.projection_service import project_wealth_series

getcontext().prec = 80


# ---------------------------------------------------------------- B: Decimal RK4
def decimal_rk4(w0, income, expense, days, r, prec=80):
    """Üretimdeki RK4'ün BİREBİR aynısı, yalnız aritmetik Decimal."""
    with localcontext() as ctx:
        ctx.prec = prec
        wealth = Decimal(str(w0))
        c = Decimal(str(income)) - Decimal(str(expense))
        rate = Decimal(str(r))
        dt = Decimal(1)
        half = dt / 2
        six = Decimal(6)
        series = [wealth]
        for _ in range(days):
            k1 = rate * wealth + c
            k2 = rate * (wealth + half * k1) + c
            k3 = rate * (wealth + half * k2) + c
            k4 = rate * (wealth + dt * k3) + c
            wealth = wealth + (dt / six) * (k1 + 2 * k2 + 2 * k3 + k4)
            series.append(wealth)
        return series


def analytic(w0, income, expense, days, r, prec=80):
    """dW/dt = rW + c çözümü, yüksek hassasiyetle.

    r = 0     ->  W0 + c*t                    (kapalı form, yaklaşım YOK)
    r != 0    ->  W0*exp(rt) + c*expm1(rt)/r

    İkinci biçim bilerek `(W0 + c/r)*exp(rt) - c/r` DEĞİL: küçük r'de c/r
    devasa olur ve çıkarma iptal (cancellation) üretir. `expm1` biçiminde
    iptal yalnız `exp(rt) - 1` içinde kalır ve 80 hane taşındığı için
    sonuca yansımaz. Ayrıca iki ayrı hassasiyette hesaplanıp referansın
    kendisinin kararlı olduğu doğrulanıyor (`_reference_is_stable`).
    """
    with localcontext() as ctx:
        ctx.prec = prec
        w0d = Decimal(str(w0))
        c = Decimal(str(income)) - Decimal(str(expense))
        rate = Decimal(str(r))
        out = []
        for day in range(days + 1):
            t = Decimal(day)
            if rate == 0:
                out.append(w0d + c * t)
            else:
                rt = rate * t
                expm1 = rt.exp() - 1
                out.append(w0d * rt.exp() + c * expm1 / rate)
        return out


def _reference_is_stable(case, tol=Decimal("1e-30")):
    """Referans iki farklı hassasiyette aynı mı? Değilse ölçüm güvenilmez."""
    a = analytic(*case, prec=60)[-1]
    b = analytic(*case, prec=120)[-1]
    return abs(a - b) <= tol * max(abs(b), Decimal(1))


def fiat_str(value):
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


def kurus_diff(x, y):
    return abs(Decimal(str(x)) - Decimal(str(y))) * 100


CASES = [
    # (etiket, W0, gelir, gider, gun, r)
    ("r=0 · 30g · kurusiu",        10000.00, 150.75, 100.25,   30, 0.0),
    ("r=0 · 365g · kurusiu",       10000.00, 150.75, 100.25,  365, 0.0),
    ("r=0 · 3650g · kurusiu",      10000.00, 150.75, 100.25, 3650, 0.0),
    ("r=0 · 3650g · 0.1/0.3",          0.00,    0.30,   0.10, 3650, 0.0),
    ("r=0.0001 · 1g",              10000.00, 150.75, 100.25,    1, 0.0001),
    ("r=0.0001 · 30g",             10000.00, 150.75, 100.25,   30, 0.0001),
    ("r=0.0001 · 365g",            10000.00, 150.75, 100.25,  365, 0.0001),
    ("r=0.0001 · 3650g",           10000.00, 150.75, 100.25, 3650, 0.0001),
    ("r=1e-9 · 3650g",             10000.00, 150.75, 100.25, 3650, 1e-9),
    ("r=0.01 · 3650g",             10000.00, 150.75, 100.25, 3650, 0.01),
    ("r=0.0001 · buyuk servet",  9_500_000.00, 1500.00, 1200.00, 3650, 0.0001),
    ("r=-0.0002 · 365g",           10000.00, 100.00, 150.00,  365, -0.0002),
    ("gelir=gider · r=0 · 365g",   10000.00, 100.00, 100.00,  365, 0.0),
    ("gelir<gider · r=0 · 365g",   10000.00,  50.00, 150.00,  365, 0.0),
    ("kurus alti · r=0 · 365g",      100.00,   0.005,  0.001,  365, 0.0),
]


def main():
    print("=" * 118)
    print("A = mevcut float RK4 | B = Decimal RK4 (ayni algoritma) | C = analitik referans")
    print("=" * 118)
    header = (f"{'vaka':<26} {'|A-B| float':>13} {'|B-C| RK4':>13} "
              f"{'|A-C| toplam':>13} {'A kurus':>14} {'C kurus':>14} {'ayni?':>6}")
    print(header)
    print("-" * 118)

    verdicts = []
    for label, w0, inc, exp, days, r in CASES:
        case = (w0, inc, exp, days, r)
        if not _reference_is_stable(case):
            print(f"{label:<26} REFERANS KARARSIZ — bu vaka atlandi")
            continue
        a = project_wealth_series(w0, inc, exp, days, r)[-1][1]
        b = decimal_rk4(*case)[-1]
        c = analytic(*case)[-1]
        ab = abs(Decimal(str(a)) - b)
        bc = abs(b - c)
        ac = abs(Decimal(str(a)) - c)
        same = fiat_str(a) == str(c.quantize(Decimal("0.01")))
        verdicts.append((label, ab, bc, ac, same))
        print(f"{label:<26} {ab:>13.3e} {bc:>13.3e} {ac:>13.3e} "
              f"{fiat_str(a):>14} {str(c.quantize(Decimal('0.01'))):>14} "
              f"{'EVET' if same else 'HAYIR':>6}")

    print("-" * 118)
    differing = [v for v in verdicts if not v[4]]
    print(f"kurusa yuvarlandiginda A ile C'nin AYRISTIGI vaka: {len(differing)}/{len(verdicts)}")
    for label, ab, bc, ac, _ in differing:
        dominant = "float temsil" if ab > bc else "RK4 kesme"
        print(f"   - {label}: baskin hata = {dominant} (|A-B|={ab:.2e}, |B-C|={bc:.2e})")

    # Hangi hata baskin?
    print("\n=== Baskin hata kaynagi (tum vakalar) ===")
    float_dom = sum(1 for _, ab, bc, _, _ in verdicts if ab > bc)
    print(f"  float temsil hatasi baskin : {float_dom}/{len(verdicts)} vaka")
    print(f"  RK4 kesme hatasi baskin    : {len(verdicts) - float_dom}/{len(verdicts)} vaka")


def measure_goes_negative():
    """Sifir gecisi: karar `any(value < 0)` ile TUM seri uzerinde veriliyor."""
    print("\n=== goes_negative sinir davranisi ===")
    print(f"{'vaka':<34} {'A karar':>9} {'C karar':>9} {'A min':>18} {'C min':>18}")
    cases = [
        ("tam sifira inen",        1000.00, 0.00, 10.00,  100, 0.0),
        ("sifirin bir kurus ustu", 1000.01, 0.00, 10.00,  100, 0.0),
        ("sifirin bir kurus alti",  999.99, 0.00, 10.00,  100, 0.0),
        ("r ile toparlanan",         50.00, 0.00,  1.00,  200, 0.02),
    ]
    for label, w0, inc, exp, days, r in cases:
        a_series = [v for _d, v in project_wealth_series(w0, inc, exp, days, r)]
        c_series = analytic(w0, inc, exp, days, r)
        a_neg = any(v < 0 for v in a_series)
        c_neg = any(v < 0 for v in c_series)
        flag = "" if a_neg == c_neg else "   <== KARAR FARKLI"
        print(f"{label:<34} {str(a_neg):>9} {str(c_neg):>9} "
              f"{min(a_series):>18.10f} {float(min(c_series)):>18.10f}{flag}")


def measure_scenario_arithmetic():
    """Senaryo yuzde aritmetigi — RK4'ten AYRI olcum."""
    from services.projection_service import simulate_scenario
    print("\n=== Senaryo yuzde aritmetigi (kernel disinda) ===")
    cases = [
        (10000.00, 150.75, 100.25, 7.0, 0.0, 0.0001, 365, 0.0),
        (10000.00, 150.75, 100.25, 0.0, 3.0, 0.0001, 365, 0.0),
        (10000.00, 100.00, 100.00, 0.1, 0.0, 0.0,     365, 0.0),
    ]
    for bal, inc, exp, ipct, epct, r, days, adj in cases:
        res = simulate_scenario(bal, inc, exp, ipct, epct, r, days, adj)
        f_inc = res["inputs"]["scenario_daily_income"]
        f_exp = res["inputs"]["scenario_daily_expense"]
        d_inc = Decimal(str(inc)) * (1 + Decimal(str(ipct)) / 100)
        d_exp = Decimal(str(exp)) * (1 + Decimal(str(epct)) / 100)
        print(f"  gelir%={ipct:<5} gider%={epct:<5} "
              f"float={f_inc!r:<22} Decimal={str(d_inc):<22} "
              f"kurus fark={kurus_diff(f_inc, d_inc):.2e}")
        if epct:
            print(f"{'':>32}gider float={f_exp!r:<20} Decimal={str(d_exp):<20} "
                  f"kurus fark={kurus_diff(f_exp, d_exp):.2e}")
        # difference sonucu
        diff = res["difference"]
        print(f"{'':>4}difference={diff!r}  kurusa={fiat_str(diff)}")


def measure_performance():
    print("\n=== Performans (3650 gun, 200 tekrar) ===")
    args = (10000.00, 150.75, 100.25, 3650, 0.0001)
    n = 200
    t0 = _time.perf_counter()
    for _ in range(n):
        project_wealth_series(*args)
    float_s = _time.perf_counter() - t0
    t0 = _time.perf_counter()
    for _ in range(n):
        decimal_rk4(*args, prec=28)
    dec28_s = _time.perf_counter() - t0
    t0 = _time.perf_counter()
    for _ in range(n // 4):
        decimal_rk4(*args, prec=80)
    dec80_s = (_time.perf_counter() - t0) * 4
    print(f"  float RK4          : {float_s:7.3f} s  (1.0x)")
    print(f"  Decimal RK4 prec=28: {dec28_s:7.3f} s  ({dec28_s / float_s:.1f}x)")
    print(f"  Decimal RK4 prec=80: {dec80_s:7.3f} s  ({dec80_s / float_s:.1f}x)")


if __name__ == "__main__":
    main()
    measure_goes_negative()
    measure_scenario_arithmetic()
    measure_performance()
