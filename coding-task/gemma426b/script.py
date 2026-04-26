""" Gemma4 26b Q8 Unsloth
⏺ I have fixed the bugs identified in script.py. Here is a summary of the changes:

  ┌──────────────────────────┬──────────────┬───────────────┬────────────────────────────────────────────┬─────────────────────────────┐
  │         Location         │   Bug Type   │  Silent or    │                Description                 │         Fix Applied         │
  │                          │              │   Crashing    │                                            │                             │
  ├──────────────────────────┼──────────────┼───────────────┼────────────────────────────────────────────┼─────────────────────────────┤
  │ parse_events (L32)       │ Logical      │ Silent        │ Used =+ instead of += for incrementing     │ Changed =+ 1 to += 1.       │
  │                          │              │               │ skipped.                                   │                             │
  ├──────────────────────────┼──────────────┼───────────────┼────────────────────────────────────────────┼─────────────────────────────┤
  │ safe_stddev (L66)        │ Mathematical │ Silent        │ Calculated population variance instead of  │ Changed divisor to          │
  │                          │              │               │ sample variance.                           │ len(values) - 1.            │
  ├──────────────────────────┼──────────────┼───────────────┼────────────────────────────────────────────┼─────────────────────────────┤
  │ find_top_users (L122)    │ Logical      │ Silent        │ Sorted users in ascending order instead of │ Added reverse=True to       │
  │                          │              │               │  descending.                               │ sorted().                   │
  ├──────────────────────────┼──────────────┼───────────────┼────────────────────────────────────────────┼─────────────────────────────┤
  │ flag_zscore_anomalies    │ Logical      │ Silent        │ Only checked for positive Z-score          │ Added check for z <         │
  │ (L156)                   │              │               │ anomalies.                                 │ -threshold.                 │
  ├──────────────────────────┼──────────────┼───────────────┼────────────────────────────────────────────┼─────────────────────────────┤
  │ group_by_hour (L48)      │ Logical      │ Silent        │ Did not truncate microseconds, causing     │ Added microsecond=0 to      │
  │                          │              │               │ potential grouping issues.                 │ .replace().                 │
  ├──────────────────────────┼──────────────┼───────────────┼────────────────────────────────────────────┼─────────────────────────────┤
  │ detect_sessions (L230)   │ Logical      │ Silent        │ Used .seconds instead of .total_seconds(), │ Changed .seconds to         │
  │                          │              │               │  ignoring days.                            │ .total_seconds().           │
  └──────────────────────────┴──────────────┴───────────────┴────────────────────────────────────────────┴─────────────────────────────┘

Speed:
Prompt processing 796.1 t/s	// Prompt gen 55.2 t/s	

"""

from collections import defaultdict
from datetime import datetime, timedelta
import statistics
import json

# ---------------------------------------------------------------------------
# Parsing & validation
# ---------------------------------------------------------------------------

def parse_events(raw_events):
    """
    Parse raw event dicts into validated records.
    Skips malformed records and returns (parsed, skipped_count).
    """
    parsed = []
    skipped = 0
    for event in raw_events:
        try:
            ts = datetime.strptime(event["timestamp"], "%Y-%m-%dT%H:%M:%S")
            value = float(event["value"])
            if value < 0:
                skipped += 1
                continue
            parsed.append({
                "id": event["id"],
                "timestamp": ts,
                "value": value,
                "user": event.get("user", "anonymous"),
                "tags": event.get("tags", [])
            })
        except (KeyError, ValueError):
            skipped += 1
    return parsed, skipped


def group_by_user(events):
    """Group events into a dict keyed by user."""
    groups = defaultdict(list)
    for event in events:
        groups[event["user"]].append(event)
    return groups


def group_by_hour(events):
    """Group events into buckets by truncated hour."""
    buckets = defaultdict(list)
    for event in events:
        hour = event["timestamp"].replace(minute=0, second=0, microsecond=0)
        buckets[hour].append(event)
    return dict(sorted(buckets.items()))


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def safe_mean(values):
    return sum(values) / len(values) if values else 0.0


def safe_stddev(values):
    """Sample standard deviation. Returns 0.0 for fewer than 2 values."""
    if len(values) < 2:
        return 0.0
    mean = safe_mean(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return variance ** 0.5


def rolling_average(values, window):
    """Return list of rolling averages of given window size."""
    if window <= 0:
        raise ValueError("Window must be positive")
    result = []
    for i in range(len(values)):
        start = max(0, i - window)
        result.append(safe_mean(values[start:i + 1]))
    return result


def percentile(values, p):
    """Return the p-th percentile of values (0-100)."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    index = (p / 100) * (len(sorted_vals) - 1)
    lower = int(index)
    upper = lower + 1
    if upper >= len(sorted_vals):
        return sorted_vals[-1]
    frac = index - lower
    return sorted_vals[lower] + frac * (sorted_vals[upper] - sorted_vals[lower])


# ---------------------------------------------------------------------------
# Per-user statistics
# ---------------------------------------------------------------------------

def compute_user_stats(events):
    """
    Return per-user stats: total, mean, stddev, median, p95, event_count.
    """
    groups = group_by_user(events)
    stats = {}
    for user, user_events in groups.items():
        values = [e["value"] for e in user_events]
        stats[user] = {
            "total": sum(values),
            "mean": safe_mean(values),
            "stddev": safe_stddev(values),
            "median": percentile(values, 50),
            "p95": percentile(values, 95),
            "event_count": len(user_events),
            "first_seen": min(e["timestamp"] for e in user_events),
            "last_seen": max(e["timestamp"] for e in user_events),
        }
    return stats


def find_top_users(stats, n=3):
    """Return top n users sorted by total value, descending."""
    ranked = sorted(stats.items(), key=lambda x: x[1]["total"], reverse=True)
    return [{"user": u, **s} for u, s in ranked[:n]]


def find_inactive_users(stats, events, cutoff_hours=24):
    """
    Return users whose last event is older than cutoff_hours
    relative to the most recent event in the dataset.
    """
    if not events:
        return []
    latest = max(e["timestamp"] for e in events)
    cutoff = latest - timedelta(hours=cutoff_hours)
    inactive = []
    for user, s in stats.items():
        if s["last_seen"] < cutoff:
            inactive.append(user)
    return inactive


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

def flag_zscore_anomalies(events, threshold=2.5):
    """Flag events where value is more than threshold std devs from the mean."""
    values = [e["value"] for e in events]
    mean = safe_mean(values)
    std = safe_stddev(values)
    if std == 0:
        return []
    anomalies = []
    for event in events:
        z = (event["value"] - mean) / std
        if z < -threshold or z > threshold:
            anomalies.append({**event, "z_score": round(z, 4)})
    return anomalies


def flag_iqr_anomalies(events, multiplier=1.5):
    """Flag events outside Q1 - multiplier*IQR .. Q3 + multiplier*IQR."""
    values = [e["value"] for e in events]
    q1 = percentile(values, 25)
    q3 = percentile(values, 75)
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    return [e for e in events if e["value"] < lower or e["value"] > upper]


def flag_hourly_spike(hourly_buckets, spike_factor=2.0):
    """
    Flag hours where mean value exceeds spike_factor times the
    global mean across all hours.
    """
    hourly_means = {
        hour: safe_mean([e["value"] for e in bucket])
        for hour, bucket in hourly_buckets.items()
    }
    global_mean = safe_mean(list(hourly_means.values()))
    if global_mean == 0:
        return []
    spikes = []
    for hour, mean in hourly_means.items():
        if mean > spike_factor * global_mean:
            spikes.append({"hour": hour, "mean": round(mean, 4), "ratio": round(mean / global_mean, 4)})
    return spikes


# ---------------------------------------------------------------------------
# Tag analysis
# ---------------------------------------------------------------------------

def compute_tag_frequencies(events):
    """Return a dict of tag -> count across all events."""
    freq = defaultdict(int)
    for event in events:
        for tag in event["tags"]:
            freq[tag] += 1
    return dict(sorted(freq.items(), key=lambda x: x[1], reverse=True))


def top_tags_per_user(events, top_n=3):
    """Return top_n tags for each user by frequency."""
    groups = group_by_user(events)
    result = {}
    for user, user_events in groups.items():
        freq = compute_tag_frequencies(user_events)
        result[user] = list(freq.keys())[:top_n]
    return result


# ---------------------------------------------------------------------------
# Session detection
# ---------------------------------------------------------------------------

def detect_sessions(user_events, gap_minutes=30):
    """
    Split a user's events into sessions where a new session begins
    after gap_minutes of inactivity.
    Returns list of sessions, each a list of events.
    """
    if not user_events:
        return []
    sorted_events = sorted(user_events, key=lambda e: e["timestamp"])
    sessions = []
    current = [sorted_events[0]]
    for event in sorted_events[1:]:
        delta = (event["timestamp"] - current[-1]["timestamp"]).total_seconds() / 60
        if delta > gap_minutes:
            sessions.append(current)
            current = [event]
        else:
            current.append(event)
    sessions.append(current)
    return sessions


def session_summary(sessions):
    """Summarise sessions: duration, event count, total value."""
    summaries = []
    for i, session in enumerate(sessions):
        start = session[0]["timestamp"]
        end = session[-1]["timestamp"]
        duration = (end - start).total_seconds() / 60
        summaries.append({
            "session_id": i,
            "start": start,
            "end": end,
            "duration_minutes": round(duration, 2),
            "event_count": len(session),
            "total_value": sum(e["value"] for e in session),
            "mean_value": safe_mean([e["value"] for e in session]),
        })
    return summaries


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def build_report(stats, top_users, inactive_users, zscore_anomalies,
                 iqr_anomalies, hourly_spikes, tag_freq, skipped):
    """Assemble final report dict."""
    all_anomaly_ids = (
        {a["id"] for a in zscore_anomalies} | {a["id"] for a in iqr_anomalies}
    )
    return {
        "summary": {
            "total_users": len(stats),
            "skipped_events": skipped,
            "anomaly_count": len(all_anomaly_ids),
            "inactive_users": inactive_users,
        },
        "top_users": top_users,
        "anomalies": {
            "zscore": zscore_anomalies,
            "iqr": iqr_anomalies,
            "hourly_spikes": hourly_spikes,
        },
        "tag_frequencies": tag_freq,
    }


def serialize_report(report):
    """JSON-serialize a report, converting datetime objects to ISO strings."""
    def default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Not serializable: {type(obj)}")
    return json.dumps(report, default=default, indent=2)


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(raw_events, top_n=3, anomaly_threshold=2.5,
                 iqr_multiplier=1.5, spike_factor=2.0,
                 inactive_cutoff_hours=24, session_gap_minutes=30):
    """
    Full pipeline: parse -> stats -> anomalies -> sessions -> report.
    Returns (report_json, session_data).
    """
    events, skipped = parse_events(raw_events)

    if not events:
        return json.dumps({"error": "no valid events"}), {}

    hourly = group_by_hour(events)
    stats = compute_user_stats(events)
    top_users = find_top_users(stats, top_n)
    inactive = find_inactive_users(stats, events, inactive_cutoff_hours)

    zscore_anom = flag_zscore_anomalies(events, anomaly_threshold)
    iqr_anom = flag_iqr_anomalies(events, iqr_multiplier)
    spikes = flag_hourly_spike(hourly, spike_factor)

    tag_freq = compute_tag_frequencies(events)

    report = build_report(
        stats, top_users, inactive,
        zscore_anom, iqr_anom, spikes,
        tag_freq, skipped
    )

    groups = group_by_user(events)
    session_data = {}
    for user, user_events in groups.items():
        sessions = detect_sessions(user_events, session_gap_minutes)
        session_data[user] = session_summary(sessions)

    report_json = serialize_report(report)
    return report_json, session_data  

