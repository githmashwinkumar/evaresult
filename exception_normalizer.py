"""Normalize Corrigan Peak's sample FreightWorks exception export.

Run: python exception_normalizer.py
Outputs: normalized_exceptions.csv, exception_summary.csv, review_required.csv
Assumption: naive timestamps are local terminal time; timezone is unknown.
"""
import csv
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
SOURCE = BASE / 'exceptions_raw.csv'


def normalize(row):
    item = {k: (v or '').strip() for k, v in row.items()}
    notes = []
    raw_terminal = item['terminal'].casefold()
    terminal_aliases = {'terminal 3': 'Terminal 3', 't3': 'Terminal 3'}
    terminal = terminal_aliases.get(raw_terminal)
    if terminal is None:
        notes.append('Unrecognized terminal; confirm mapping')
        terminal = item['terminal']

    carrier = item['carrier_code'].upper()
    if not carrier:
        notes.append('Missing carrier_code; cannot infer from other records')

    raw_ts = item['event_ts']
    parsed = None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M', '%Y-%m-%dT%H:%M:%SZ'):
        try:
            parsed = datetime.strptime(raw_ts, fmt)
            if fmt.endswith('Z'):
                parsed = parsed.replace(tzinfo=timezone.utc)
            break
        except ValueError:
            pass
    if parsed is None:
        notes.append('Unrecognized timestamp format')
        normalized_ts = raw_ts
    else:
        normalized_ts = parsed.isoformat(timespec='seconds')
        if parsed.tzinfo is None:
            notes.append('Timestamp timezone unspecified; kept as local/naive, not converted to UTC')

    return {
        'exception_id': item['exception_id'],
        'terminal': terminal,
        'event_type': item['event_type'],
        'carrier_code': carrier,
        'event_ts': normalized_ts,
        'review_required': 'yes' if any(n for n in notes if not n.startswith('Timestamp timezone unspecified')) else 'no',
        'notes': '; '.join(notes),
    }


def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    with SOURCE.open(newline='', encoding='utf-8-sig') as handle:
        source = list(csv.DictReader(handle))
    required = {'exception_id', 'terminal', 'event_type', 'carrier_code', 'event_ts'}
    if not source or not required.issubset(source[0]):
        raise ValueError('Missing rows or required columns')
    rows = [normalize(row) for row in source]
    if len({r['exception_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate exception IDs in source')
    write_csv(BASE / 'normalized_exceptions.csv', rows, list(rows[0]))
    counts = Counter(row['event_type'] for row in rows)
    summary = [{'event_type': key, 'count': counts[key]} for key in sorted(counts)]
    write_csv(BASE / 'exception_summary.csv', summary, ['event_type', 'count'])
    review = [row for row in rows if row['review_required'] == 'yes']
    write_csv(BASE / 'review_required.csv', review, list(rows[0]))
    print(f'Processed {len(rows)} records; {len(review)} require manual review.')
    print('Counts by event type:')
    for entry in summary:
        print(f"  {entry['event_type']}: {entry['count']}")
    print('Manual review IDs:', ', '.join(r['exception_id'] for r in review) or 'none')
    print('Timezone caution: naive source timestamps were NOT assumed to be UTC.')


if __name__ == '__main__':
    main()
