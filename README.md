# Comparative Analysis of Perpetual vs Spot Contracts

## Cost-Benefit Evaluation for Long Positions on Bitcoin

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Jupyter](https://img.shields.io/badge/Jupyter-Notebook-orange.svg)](https://jupyter.org/)

This project provides a comprehensive analysis comparing the costs and benefits of holding long positions on Bitcoin through perpetual contracts versus direct spot market purchases. The analysis includes funding cost calculations, leverage effects, risk assessment, and detailed interpretations of market behavior.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Key Findings](#key-findings)
- [Methodology](#methodology)
- [Results](#results)
- [Limitations](#limitations)
- [Future Research Directions](#future-research-directions)

## Overview

This project examines and compares the costs associated with holding a long position on a perpetual contract compared to directly purchasing Bitcoin on the spot market. The analysis uses historical data from Binance for the period from November 1, 2023 to March 20, 2024, with detailed focus on the period from January 1, 2024 to March 20, 2024.

### Key Questions Addressed

- What are the financial implications of funding costs on perpetual positions?
- How do leveraged perpetual positions compare to direct spot purchases?
- What is the net profitability difference between these two strategies?
- How do market efficiency and integration affect price alignment between spot and perpetual markets?

## Features

### Data Collection
- Automated retrieval of historical Bitcoin price data from Binance API
  - Spot market prices (daily)
  - Perpetual futures prices (daily)
  - Funding rates (updated every 8 hours, 3 per day)
- Robust error handling with exponential backoff retry mechanism
- Automatic pagination for large datasets

### Analysis Tools
- **Statistical Analysis**:
  - Volatility and correlation analysis
  - Daily returns distribution analysis
  - Market efficiency indicators
  
- **Financial Calculations**:
  - Funding cost calculations with dynamic mark price adjustments
  - Profit/loss comparison between spot and perpetual positions
  - Leverage impact analysis
  
- **Visualizations**:
  - Closing prices comparison (Spot vs Perpetual)
  - Daily returns comparison
  - Strategy comparison bar charts
  - Period-based profit/loss analysis
  - Interactive Plotly visualizations

### Interactive Dashboard
- Web application built with Dash for exploring different time periods
- Dynamic profit/loss calculations for selected periods
- Time series visualization of opening prices
- Automatic annotations showing profit/loss values

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

1. Clone this repository:
```bash
git clone https://github.com/dan-allouche-qf/perpetual-vs-spot-analysis.git
cd perpetual-vs-spot-analysis
```

2. Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Running the Notebook

1. Start Jupyter Notebook:
```bash
jupyter notebook
```

2. Open `perpetual_vs_spot_analysis.ipynb` and run all cells sequentially.

The notebook is structured to be read linearly, with each section building upon the previous one:
1. Data Collection
2. Data Processing and Analysis
3. Comparison of Long Spot/Perpetual Positions
4. Results and Interpretation
5. Conclusion
6. Interactive Visualization

### Running the Interactive Dashboard

The notebook includes a Dash application that can be launched from the last cell. The application will automatically find an available port (starting from 8050) and will be accessible at `http://127.0.0.1:<port>`.

## Project Structure

```
perpetual-vs-spot-analysis/
├── perpetual_vs_spot_analysis.ipynb  # Main analysis notebook
├── requirements.txt                  # Python dependencies
├── README.md                         # Project documentation
└── .gitignore                        # Git ignore file
```

## Key Findings

Based on the analysis of a $1,000 investment from January 1, 2024 to March 20, 2024 with 4x leverage:

| Strategy | Profit/Loss | Return | Notes |
|----------|------------|--------|-------|
| **Spot Position** | $464.81 | 46.5% | Direct purchase |
| **Perpetual (No Funding)** | $1,858.50 | 185.8% | With 4x leverage |
| **Perpetual (With Funding)** | $1,598.01 | 159.8% | Net after funding costs |
| **Funding Costs** | -$260.49 | -26.0% | Total fees paid |

### Main Insights

1. **Market Integration**: Spot and perpetual markets show near-perfect price alignment (correlation: 0.999999) and identical volatility patterns (2.86% vs 2.87%), indicating high market efficiency and strong integration.

2. **Leverage Impact**: The 4x leverage multiplies returns by approximately 4x compared to spot, but funding costs reduce this advantage by 14% of gross profits. The net effect is still a 3.4x return multiplier.

3. **Funding Cost Significance**: Funding costs represent 26% of initial investment over the period, demonstrating their substantial impact on net profitability in perpetual trading strategies.

4. **Net Advantage**: Despite funding costs, leveraged perpetual positions provide substantially higher returns than spot positions (159.8% vs 46.5%) in bullish market conditions, but with correspondingly higher risk exposure.

5. **Risk-Return Trade-off**: The risk-return trade-off favors perpetual positions in bullish scenarios, but the opposite would be true in bearish conditions where leverage amplifies losses.

## Methodology

### Data Collection

- **Source**: Binance API
- **Period**: November 1, 2023 to March 20, 2024
- **Data Points**: 
  - 141 daily spot market prices
  - 141 daily perpetual futures prices
  - 421 funding rate data points (3 per day)

### Calculations

The project implements several key formulas with an important improvement: the position's nominal value is recalculated at each funding interval using the current mark price, which more accurately reflects market reality.

1. **Initial Position Size**: `(Investment Amount / Opening Price) × Leverage`
2. **Nominal Value**: `Mark Price × Position Size` (recalculated at each funding interval)
3. **Funding Costs**: `Nominal Value × Funding Rate` (summed over all intervals)
4. **Profit/Loss**: Standard percentage return calculations with leverage adjustments

See the notebook for detailed mathematical formulations and explanations.

### Analysis Approach

The analysis follows a progressive methodology:
1. **Market Behavior Analysis**: First examines price alignment, volatility, and correlation between markets
2. **Financial Impact Analysis**: Then incorporates funding costs and leverage to evaluate net profitability
3. **Temporal Analysis**: Explores performance variations across different time periods
4. **Risk Assessment**: Discusses limitations and risk factors not captured in the model

## Results

### Market Characteristics

- **Volatility**: Spot (2.86%) vs Perpetual (2.87%) - virtually identical (difference of only 0.01%)
- **Correlation**: 0.999999 - near-perfect correlation indicating high market efficiency
- **Price Alignment**: Near-perfect price alignment throughout the entire period, demonstrating effective funding rate mechanisms

### Performance Comparison

The perpetual position with funding costs outperforms the spot position by **$1,133.20** (or **113.3% additional return**) in the analyzed period. However, this comes with proportionally higher risk exposure due to leverage.

### Key Observations

- Funding costs account for 14.0% of gross profit and 26.0% of initial investment
- The funding rate mechanism effectively maintains price parity between spot and perpetual markets
- Both markets respond to the same underlying factors, showing strong market integration
- Perpetual contracts do not introduce additional volatility beyond the underlying asset

## Limitations

This analysis has important limitations that should be considered:

1. **Margin Calls**: The model does not account for margin call mechanisms, which are crucial in managing leveraged positions during periods of increased volatility.

2. **Bankruptcy Risk**: High leverage increases the risk of total loss, especially if contract value decreases significantly. If losses exceed deposited margins, investors may lose their entire initial investment and be held responsible for remaining debt.

3. **Market Conditions**: Results are specific to the analyzed period (bullish market conditions) and may not generalize to other market environments. The analysis period (January-March 2024) was characterized by generally positive price movements.

4. **Transaction Costs**: Additional fees such as trading fees (maker/taker fees on Binance, typically 0.1% per trade) and withdrawal fees are not included in the analysis.

5. **Liquidation Risk**: The model does not simulate liquidation events that could occur during adverse market movements with leveraged positions.

## Future Research Directions

While this analysis provides valuable insights, several areas could be explored to extend and deepen the understanding:

- **Extended Time Period Analysis**: Including bearish market conditions and different market cycles
- **Transaction Costs Integration**: Incorporating trading fees for a more complete cost-benefit analysis
- **Risk Metrics Enhancement**: Adding risk-adjusted performance metrics (Sharpe ratio, Sortino ratio, maximum drawdown)
- **Margin Call and Liquidation Modeling**: Developing models that incorporate margin call mechanisms and liquidation risks
- **Multi-Asset Analysis**: Extending the analysis to other cryptocurrencies (Ethereum, etc.)
- **Sensitivity Analysis**: Conducting sensitivity analysis on key parameters (leverage ratio, holding period, funding rate levels)

## Requirements

All dependencies are listed in `requirements.txt`. Key packages include:

- `requests>=2.31.0` - HTTP requests for Binance API
- `pandas>=2.0.0` - Data manipulation and analysis
- `numpy>=1.24.0` - Numerical computations
- `plotly>=5.17.0` - Interactive visualizations
- `matplotlib>=3.7.0` - Static visualizations
- `dash>=2.14.0` - Interactive web application
- `nbformat>=4.2.0` - Jupyter notebook support for Plotly rendering
- `ipython>=8.0.0` - Enhanced interactive Python shell

## Acknowledgments

- [Binance API](https://www.binance.com/en/support/faq/360002502072) for providing market data
- Open-source Python libraries used in this project
