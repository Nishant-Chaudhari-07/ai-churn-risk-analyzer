 
# AI-Powered Customer Churn & Revenue Risk Analyzer

An automated business intelligence pipeline that connects to Snowflake,
runs customer churn analysis across 41,000+ customer records, detects
anomalies, and generates an AI-written executive summary - delivered
automatically via email every Monday morning.

## Business Problem
Companies lose millions in revenue to customer churn before anyone notices
the pattern. This tool automates the entire detection and reporting workflow
that a Business Analyst would normally perform manually over 2-3 hours -
completing it in under 60 seconds.

## Architecture
Snowflake (Data) → Python (Orchestration) → Groq LLaMA 3.3 70B (AI) → Email Report

## What It Does
- Connects to Snowflake and queries 41,000+ churned customer records
- Segments customers by market (Household, Furniture, Building, Machinery, Automobile)
- Scores each customer as HIGH / MEDIUM / LOW churn risk based on recency and revenue
- Detects anomalies automatically - flags segments exceeding risk thresholds
- Generates a board-ready executive summary using an LLM
- Saves a timestamped report and emails it to stakeholders
- Schedules itself to run every Monday at 8am with zero manual intervention

## Key Findings (Sample Output)
- 41,053 customers identified as churned across all segments
- $78B+ in total revenue at risk
- Risk evenly distributed across segments (~20% each) - indicating a systemic
  retention problem rather than a segment-specific issue
- HIGH risk tier accounts for ~30% of churned customers but disproportionate
  revenue exposure

## Tech Stack
- **Snowflake** - Cloud data warehouse, SQL analytics
- **Python** - Pipeline orchestration, data processing
- **Groq API** - LLaMA 3.3 70B for AI-generated executive summaries
- **Pandas** - Data transformation and formatting
- **Schedule** - Automated weekly execution
- **SMTP / Gmail** - Automated stakeholder email delivery

## Skills Demonstrated
- Cloud data warehousing (Snowflake)
- Advanced SQL - window functions, subqueries, CASE logic, DATEDIFF
- Python automation and API integration
- Agentic AI pipeline design
- Business analytics and churn modeling
- Automated reporting and anomaly detection

## Setup
1. Clone the repo
2. Install dependencies

pip install snowflake-connector-python groq pandas python-dotenv schedule

3. Create a `.env` file with your credentials (see `.env.example`)
4. Run the pipeline

python main.py

## Project Structure
ai-churn-risk-analyzer/

├── main.py               # Full pipeline - queries, AI summary, email, scheduler

├── churn_report.txt      # Sample generated report

├── .gitignore            # Keeps credentials out of GitHub

└── README.md             # This file

## Author
**Nishant Chaudhari**
MS Business Analytics - UMass Amherst (Isenberg)
[LinkedIn](https://www.linkedin.com/in/nishant-chaudhari) | [Portfolio](https://nishantchaudhari.com)