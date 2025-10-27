"""Main entry point - automatically discovers and runs all producers"""
import os
import importlib
import inspect
import signal
import sys
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from producers.base_producer import BaseProducer


def discover_producers():
    """Automatically discover all producer classes"""
    producers_dir = Path(__file__).parent / 'producers'
    producer_classes = []
    
    # Find all Python files in producers directory
    for file in producers_dir.glob('*_producer.py'):
        if file.name == 'base_producer.py':
            continue
        
        # Import the module
        module_name = f"producers.{file.stem}"
        try:
            module = importlib.import_module(module_name)
            
            # Find classes that inherit from BaseProducer
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, BaseProducer) and 
                    obj is not BaseProducer and 
                    obj.__module__ == module_name):
                    producer_classes.append((name, obj))
                    print(f"✓ Discovered: {name}")
        
        except Exception as e:
            print(f"⚠️  Failed to load {file.name}: {e}")
    
    return producer_classes


def main():
    print("=" * 70)
    print("Stock Data Streaming System - Scheduler Mode")
    print("=" * 70)
    
    # Discover all producers
    print("\n🔍 Discovering producers...")
    producer_classes = discover_producers()
    
    if not producer_classes:
        print("❌ No producers found!")
        return
    
    print(f"\n✅ Found {len(producer_classes)} producer(s)\n")
    
    # Initialize scheduler
    scheduler = BackgroundScheduler()
    producers = []
    
    # Initialize each producer and add to scheduler
    for name, producer_class in producer_classes:
        try:
            print(f"\n🚀 Setting up {name}...")
            producer = producer_class()
            
            # Initialize the producer
            if not producer.initialize():
                print(f"⚠️  Skipping {name} due to initialization failure")
                continue
            
            # Add to scheduler
            scheduler.add_job(
                producer.fetch_and_send,
                trigger=IntervalTrigger(seconds=producer.fetch_interval),
                id=name,
                name=name,
                max_instances=1
            )
            
            # Run once immediately
            producer.fetch_and_send()
            
            producers.append(producer)
            print(f"✓ {name} scheduled (every {producer.fetch_interval}s)")
            
        except Exception as e:
            print(f"❌ Failed to setup {name}: {e}")
    
    if not producers:
        print("\n❌ No producers initialized successfully!")
        return
    
    # Start the scheduler
    scheduler.start()
    
    print("\n" + "=" * 70)
    print("✅ All producers running on schedule!")
    print("Press Ctrl+C to stop")
    print("=" * 70 + "\n")
    
    # Graceful shutdown handler
    def signal_handler(sig, frame):
        print("\n" + "=" * 70)
        print("🛑 Shutting down...")
        print("=" * 70)
        scheduler.shutdown(wait=False)
        for producer in producers:
            producer.cleanup()
        print("✅ Shutdown complete")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Keep main thread alive (scheduler runs in background)
    try:
        while True:
            import time
            time.sleep(45)  # Check every 45 seconds

            # Print scheduler status
            jobs = scheduler.get_jobs()
            print(f"\n[Status Check] Active jobs: {len(jobs)}")
            for job in jobs:
                if job.next_run_time:
                    next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')
                    print(f"  ✓ {job.name}: next run at {next_run}")
                else:
                    print(f"  ⚠️  {job.name}: no next run scheduled")
    
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == '__main__':
    main()