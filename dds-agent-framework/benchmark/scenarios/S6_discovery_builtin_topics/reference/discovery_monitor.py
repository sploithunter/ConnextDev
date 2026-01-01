#!/usr/bin/env python3
"""Discovery Monitor using DDS Discovery APIs.

Uses DomainParticipant discovery methods to find:
- Participants on the domain
- Topics being published
- Matched publications/subscriptions

Outputs JSONL with discovery events.
"""

import argparse
import json
import signal
import sys
import time

import rti.connextdds as dds


running = True


def signal_handler(signum, frame):
    global running
    running = False


def main():
    global running
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", "-d", type=int, default=0)
    parser.add_argument("--timeout", "-t", type=float, default=30.0)
    parser.add_argument("--topic-filter", type=str, default=None,
                        help="Filter for specific topic name")
    parser.add_argument("--poll-interval", type=float, default=0.5,
                        help="Polling interval in seconds")
    args = parser.parse_args()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    participant = dds.DomainParticipant(args.domain)
    
    # Track discovered entities (to avoid duplicates)
    seen_participants = set()
    seen_topics = set()
    
    start_time = time.time()
    
    print("Monitoring DDS discovery...", file=sys.stderr)
    
    while running:
        elapsed = time.time() - start_time
        if elapsed > args.timeout:
            break
        
        # Check for new participants
        for handle in participant.discovered_participants():
            key = str(handle)
            if key not in seen_participants:
                try:
                    data = participant.discovered_participant_data(handle)
                    output = {
                        "event": "participant_discovered",
                        "handle": key,
                        "participant_name": str(data.participant_name.name) if data.participant_name else None,
                    }
                    print(json.dumps(output), flush=True)
                except Exception as e:
                    print(f"Error getting participant data: {e}", file=sys.stderr)
                seen_participants.add(key)
        
        # Check for new topics
        for handle in participant.discovered_topics():
            key = str(handle)
            if key not in seen_topics:
                try:
                    data = participant.discovered_topic_data(handle)
                    topic_name = data.name
                    
                    # Apply filter
                    if args.topic_filter and args.topic_filter not in topic_name:
                        seen_topics.add(key)
                        continue
                    
                    output = {
                        "event": "topic_discovered",
                        "topic": topic_name,
                        "type": data.type_name,
                        "handle": key,
                        "durability": str(data.durability.kind) if hasattr(data.durability, 'kind') else str(data.durability),
                    }
                    print(json.dumps(output), flush=True)
                except dds.UnsupportedError:
                    # Some discovered topic data not accessible (limitation)
                    output = {
                        "event": "topic_discovered",
                        "handle": key,
                        "note": "topic data not accessible",
                    }
                    print(json.dumps(output), flush=True)
                except Exception as e:
                    print(f"Error getting topic data: {e}", file=sys.stderr)
                seen_topics.add(key)
        
        time.sleep(args.poll_interval)
    
    # Final summary
    print(f"\nDiscovery summary:", file=sys.stderr)
    print(f"  Participants: {len(seen_participants)}", file=sys.stderr)
    print(f"  Topics: {len(seen_topics)}", file=sys.stderr)


if __name__ == "__main__":
    main()
