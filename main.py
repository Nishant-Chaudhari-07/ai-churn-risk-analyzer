import os
import pandas as pd
from groq import Groq
from dotenv import load_dotenv
import snowflake.connector
import smtplib
import schedule
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

load_dotenv()

# Connect to Snowflake
def get_snowflake_connection():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
        authenticator="username_password_mfa"
    )

# Query 1 - Segment level churn summary
def get_churn_by_segment(conn):
    query = """
    SELECT
        C_MKTSEGMENT,
        COUNT(*)                                               AS CHURNED_CUSTOMERS,
        ROUND(SUM(total_revenue), 2)                          AS REVENUE_AT_RISK,
        ROUND(AVG(total_revenue), 2)                          AS AVG_CUSTOMER_VALUE,
        ROUND(AVG(days_since_last_order), 0)                  AS AVG_DAYS_SILENT,
        ROUND(SUM(total_revenue) / SUM(SUM(total_revenue))
              OVER () * 100, 2)                               AS PCT_OF_TOTAL_RISK
    FROM (
        SELECT
            C.C_MKTSEGMENT,
            SUM(O.O_TOTALPRICE)                               AS total_revenue,
            DATEDIFF('day', MAX(O.O_ORDERDATE), '1998-12-31') AS days_since_last_order
        FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER C
        JOIN SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.ORDERS O
            ON C.C_CUSTKEY = O.O_CUSTKEY
        GROUP BY C.C_CUSTKEY, C.C_MKTSEGMENT
        HAVING days_since_last_order > 300
    ) churned
    GROUP BY C_MKTSEGMENT
    ORDER BY REVENUE_AT_RISK DESC
    """
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    return pd.DataFrame(results, columns=columns)

# Query 2 - Risk tier breakdown
def get_risk_tiers(conn):
    query = """
    SELECT
        C_MKTSEGMENT,
        CHURN_RISK_TIER,
        COUNT(*)                        AS CUSTOMERS,
        ROUND(SUM(total_revenue), 2)    AS REVENUE_AT_RISK
    FROM (
        SELECT
            C.C_MKTSEGMENT,
            SUM(O.O_TOTALPRICE)                                AS total_revenue,
            DATEDIFF('day', MAX(O.O_ORDERDATE), '1998-12-31') AS days_since_last_order,
            CASE
                WHEN DATEDIFF('day', MAX(O.O_ORDERDATE), '1998-12-31') > 400
                     AND SUM(O.O_TOTALPRICE) > 1500000 THEN 'HIGH'
                WHEN DATEDIFF('day', MAX(O.O_ORDERDATE), '1998-12-31') BETWEEN 300 AND 400
                     AND SUM(O.O_TOTALPRICE) > 1000000 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS CHURN_RISK_TIER
        FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER C
        JOIN SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.ORDERS O
            ON C.C_CUSTKEY = O.O_CUSTKEY
        GROUP BY C.C_CUSTKEY, C.C_MKTSEGMENT
        HAVING days_since_last_order > 300
    ) tiered
    GROUP BY C_MKTSEGMENT, CHURN_RISK_TIER
    ORDER BY C_MKTSEGMENT, CHURN_RISK_TIER
    """
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    return pd.DataFrame(results, columns=columns)

# Anomaly detection - flags if any segment risk exceeds threshold
def detect_anomalies(segment_df):
    anomalies = []
    high_risk_threshold = 20.5
    silence_threshold = 510

    for _, row in segment_df.iterrows():
        if row["PCT_OF_TOTAL_RISK"] > high_risk_threshold:
            anomalies.append(
                f"ALERT: {row['C_MKTSEGMENT']} segment exceeds risk threshold "
                f"at {row['PCT_OF_TOTAL_RISK']}% of total revenue at risk."
            )
        if row["AVG_DAYS_SILENT"] > silence_threshold:
            anomalies.append(
                f"ALERT: {row['C_MKTSEGMENT']} customers have been silent for "
                f"{row['AVG_DAYS_SILENT']} days on average - exceeds {silence_threshold} day threshold."
            )

    return anomalies if anomalies else ["No anomalies detected. All segments within normal parameters."]

# Generate AI executive summary
def generate_exec_summary(segment_df, tier_df, anomalies):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    prompt = f"""
You are a senior business analyst preparing an executive summary for the Chief Revenue Officer.

Below is customer churn analysis data. Write a concise, professional executive summary (250-300 words) that includes:
1. Overall situation - total customers at risk and total revenue exposure
2. Segment breakdown - which segments are most at risk and why it matters
3. Risk tier analysis - how HIGH/MEDIUM/LOW risk customers are distributed
4. Anomaly flags - highlight any anomalies detected
5. Two specific, actionable recommendations for retention strategy

SEGMENT CHURN DATA:
{segment_df.to_string(index=False)}

RISK TIER DATA:
{tier_df.to_string(index=False)}

ANOMALY DETECTION RESULTS:
{chr(10).join(anomalies)}

Write in a direct, executive-ready tone. Lead with the most critical finding first.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024
    )
    return response.choices[0].message.content

# Save report to file
def save_report(segment_display, tier_display, anomalies, summary):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"churn_report_{timestamp}.txt"

    with open(filename, "w") as f:
        f.write("=" * 60 + "\n")
        f.write("CUSTOMER CHURN & REVENUE RISK ANALYSIS REPORT\n")
        f.write(f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}\n")
        f.write("=" * 60 + "\n\n")
        f.write("SEGMENT CHURN SUMMARY\n")
        f.write("-" * 60 + "\n")
        f.write(segment_display.to_string(index=False))
        f.write("\n\n")
        f.write("RISK TIER BREAKDOWN\n")
        f.write("-" * 60 + "\n")
        f.write(tier_display.to_string(index=False))
        f.write("\n\n")
        f.write("ANOMALY DETECTION\n")
        f.write("-" * 60 + "\n")
        f.write("\n".join(anomalies))
        f.write("\n\n")
        f.write("AI EXECUTIVE SUMMARY\n")
        f.write("-" * 60 + "\n")
        f.write(summary)
        f.write("\n")

    return filename

# Send email with report attached
def send_email(report_filename, anomalies, summary):
    sender = os.getenv("GMAIL_USER")
    password = os.getenv("GMAIL_APP_PASSWORD")
    recipient = os.getenv("GMAIL_USER")

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = f"Churn Risk Report - {datetime.now().strftime('%B %d, %Y')}"

    anomaly_text = "\n".join(anomalies)
    body = f"""Hi,

Your automated churn risk report has been generated.

ANOMALY STATUS:
{anomaly_text}

EXECUTIVE SUMMARY:
{summary}

Full report attached.

This report was generated automatically by the Churn Risk Analyzer.
"""
    msg.attach(MIMEText(body, "plain"))

    with open(report_filename, "rb") as f:
        attachment = MIMEBase("application", "octet-stream")
        attachment.set_payload(f.read())
        encoders.encode_base64(attachment)
        attachment.add_header("Content-Disposition", f"attachment; filename={report_filename}")
        msg.attach(attachment)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

    print(f"Report emailed to {recipient}")

# Main pipeline
def run_pipeline():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Running churn analysis pipeline...")

    print("Connecting to Snowflake...")
    conn = get_snowflake_connection()

    print("Running queries...")
    segment_df = get_churn_by_segment(conn)
    tier_df = get_risk_tiers(conn)
    conn.close()

    # Format for display
    segment_display = segment_df.copy()
    segment_display["REVENUE_AT_RISK"] = segment_display["REVENUE_AT_RISK"].apply(lambda x: f"${x:,.2f}")
    segment_display["AVG_CUSTOMER_VALUE"] = segment_display["AVG_CUSTOMER_VALUE"].apply(lambda x: f"${x:,.2f}")
    segment_display["PCT_OF_TOTAL_RISK"] = segment_display["PCT_OF_TOTAL_RISK"].apply(lambda x: f"{x}%")

    tier_display = tier_df.copy()
    tier_display["REVENUE_AT_RISK"] = tier_display["REVENUE_AT_RISK"].apply(lambda x: f"${x:,.2f}")

    print("\n--- SEGMENT CHURN SUMMARY ---")
    print(segment_display.to_string(index=False))

    print("\n--- RISK TIER BREAKDOWN ---")
    print(tier_display.to_string(index=False))

    print("\nRunning anomaly detection...")
    anomalies = detect_anomalies(segment_df)
    print("\n--- ANOMALY DETECTION ---")
    for a in anomalies:
        print(a)

    print("\nGenerating AI executive summary...")
    summary = generate_exec_summary(segment_df, tier_df, anomalies)
    print("\n--- AI EXECUTIVE SUMMARY ---")
    print(summary)

    print("\nSaving report...")
    filename = save_report(segment_display, tier_display, anomalies, summary)
    print(f"Report saved to {filename}")

    print("\nSending email...")
    send_email(filename, anomalies, summary)

    print("\nPipeline complete.")

if __name__ == "__main__":
    # Run immediately on launch
    run_pipeline()

    # Then schedule every Monday at 8am
    schedule.every().monday.at("08:00").do(run_pipeline)
    print("\nScheduler running - pipeline will execute every Monday at 08:00")
    print("Press Ctrl+C to stop.\n")

    while True:
        schedule.run_pending()
        time.sleep(60)