# 🐍 Hydra-HFT
### High-Frequency Hybrid Trading Engine (C++ / Python)

![C++](https://img.shields.io/badge/C++-20-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Architecture](https://img.shields.io/badge/Architecture-Hybrid%20IPC-purple?style=for-the-badge)
![Latency](https://img.shields.io/badge/Latency-~40μs-red?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Production%20Ready-success?style=for-the-badge)

---

## ⚡ Overview

**Hydra** is an institutional-grade algorithmic trading system designed to bridge the gap between **low-latency execution** and **high-level statistical analysis**.

It solves the "Two Language Problem" in quantitative finance by decoupling the critical path:
* **Execution Layer (C++20):** Handles market data ingestion and order routing via WebSockets/REST.
* **Strategy Layer (Python):** Runs complex inference (Trend Following, LSTM-PPO) using the rich Python ecosystem.
* **The Bridge:** A custom **Shared Memory (IPC)** ring buffer allows sub-microsecond communication without network overhead.

---

## 🏗️ System Architecture

```mermaid
graph LR
    A[Binance Exchange] <==>|WebSocket / REST| B(C++ Engine)
    B <==>|Shared Memory Ring Buffer| C(Python Strategy)
    C -->|Telemetry| D(Mission Control Dashboard)
    
    style B fill:#00599C,stroke:#333,stroke-width:2px,color:#fff
    style C fill:#3776AB,stroke:#333,stroke-width:2px,color:#fff
    style D fill:#222,stroke:#333,stroke-width:2px,color:#fff


