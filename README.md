# Archlence 📊

Archlence is a local-first, privacy-centric personal finance and portfolio management application built with Python and Kivy. Designed with engineering rigor, it features a robust double-entry ledger system, automated subscription tracking, and real-time asset pricing.

## 🚀 Key Features

* **Robust Ledger Architecture:** Built on a `SAVEPOINT`-backed reconciliation engine (`settle_due_transactions`) to guarantee data integrity and prevent orphan transactions.
* **Smart Dynamic TTL Caching:** A non-blocking, asynchronous price-fetching service. Automatically adjusts caching TTL based on asset type and market hours (e.g., 3 mins for Crypto, 5 mins for active Stock markets, infinite during closed hours) ensuring 60 FPS UI performance.
* **Subscription Radar & Interceptor:** Automatically detects recurring payments and known brands from credit card transactions, placing them into an active subscription management flow with automated budget synchronization.
* **Local-First & Privacy Focused:** Your financial data belongs to you. Archlence runs locally entirely on SQLite without phoning home to third-party tracking servers.
* **Production-Ready:** Covered by a comprehensive test suite with 270+ passing unit and E2E tests, ensuring zero regressions on core financial logic.

## 🛠️ Tech Stack

* **Core:** Python
* **UI Framework:** Kivy / KivyMD (Modular Mixin Architecture)
* **Database:** SQLite (Relational structure with Pragma validations)
* **Testing:** `unittest` (Headless Xvfb / SDL2 environment compatibility)

## 🧠 AI / LLM Vision (Upcoming)

Archlence is currently integrating advanced LLM capabilities to act as a personal, privacy-first financial advisor. Planned features include:
* **Natural Language to SQL:** Querying local financial data conversationally (e.g., *"How much did I spend on digital subscriptions in the last 3 months?"*).
* **Algorithmic Foresight:** Projecting future balances and offering 50-30-20 rule optimizations based on historical spending behavior.
* **Receipt Parsing:** Local OCR combined with LLM parsing to instantly categorize and input transactions via JSON.
