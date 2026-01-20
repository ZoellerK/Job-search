#!/usr/bin/env python3
"""
Scheduler - Runs job aggregator on a schedule
"""

import schedule
import time
import sys
from datetime import datetime
from job_aggregator import JobAggregator


def run_update():
    """Run job aggregation update"""
    print(f"\n{'='*60}")
    print(f"Scheduled update started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    aggregator = JobAggregator()
    aggregator.run_full_update()


def main():
    """Main scheduler loop"""
    # Parse command line arguments
    if len(sys.argv) > 1:
        time_str = sys.argv[1]
    else:
        time_str = "09:00"  # Default: 9 AM

    print(f"📅 Job Aggregator Scheduler")
    print(f"{'='*60}")
    print(f"Scheduled to run daily at {time_str}")
    print(f"Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    # Schedule the job
    schedule.every().day.at(time_str).do(run_update)

    # Also run immediately on start
    print("Running initial update...")
    run_update()

    # Keep running
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        print("\n\n👋 Scheduler stopped")


if __name__ == "__main__":
    main()
