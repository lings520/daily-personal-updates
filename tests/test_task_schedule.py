"""Interpret the exported iCalendar with a recurrence parser, including UTC conversion."""
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from dateutil.rrule import rrulestr

ROOT = Path(__file__).resolve().parents[1]


class TaskScheduleTests(unittest.TestCase):
    def setUp(self):
        self.task = json.loads((ROOT/'tasks/morning-market-update.json').read_text())
        rule = '\n'.join(line for line in self.task['schedule'].splitlines() if line not in ('BEGIN:VEVENT','END:VEVENT'))
        self.schedule = rrulestr(rule, tzids={'Asia/Hong_Kong': ZoneInfo('Asia/Hong_Kong')})

    def test_next_five_runs_are_hkt_mornings(self):
        after = datetime(2026,11,2,0,tzinfo=timezone.utc)
        runs = list(self.schedule.xafter(after,count=5))
        self.assertEqual([d.astimezone(ZoneInfo('Asia/Hong_Kong')).isoformat() for d in runs], [
            '2026-11-03T08:00:00+08:00','2026-11-04T08:00:00+08:00',
            '2026-11-05T08:00:00+08:00','2026-11-06T08:00:00+08:00','2026-11-07T08:00:00+08:00'])
        self.assertEqual([d.astimezone(timezone.utc).hour for d in runs],[0]*5)

    def test_next_run_after_saturday_is_tuesday(self):
        after = datetime(2026,11,7,8,0,tzinfo=ZoneInfo('Asia/Hong_Kong'))
        next_run = self.schedule.after(after,inc=False)
        self.assertEqual(next_run.isoformat(),'2026-11-10T08:00:00+08:00')

    def test_hkt_hour_survives_us_dst_boundary(self):
        after = datetime(2027,3,8,0,tzinfo=timezone.utc)
        runs = list(self.schedule.xafter(after,count=10))
        self.assertEqual({d.astimezone(timezone.utc).hour for d in runs},{0})
        self.assertEqual({d.astimezone(ZoneInfo('Asia/Hong_Kong')).hour for d in runs},{8})
        self.assertEqual(self.task['default_timezone'],'Asia/Hong_Kong')


if __name__=='__main__':unittest.main()
