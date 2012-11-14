import datetime
import os

from django.conf import settings
from django.core.urlresolvers import reverse

from eventtools.conf.settings import FIRST_DAY_OF_WEEK
from eventtools.tests.eventtools_testapp.models import *
from eventtools.periods import Period, Month, Day, Year
from eventtools.utils import EventListManager
from eventtools.models import Rule
from _inject_app import TestCaseWithApp as TestCase


class TestPeriod(TestCase):

    def setUp(self):
        super(TestPeriod, self).setUp() #monkeypatch in the test app
        
        rule = Rule(frequency = "WEEKLY")
        rule.save()
        data = {
                'title': 'Recent Event',
               }
        recurring_event = TestEvent(**data)
        recurring_event.save()
        
        gendata = {
                    'start': datetime.datetime(2008, 1, 5, 8, 0),
                    'end': datetime.datetime(2008, 1, 5, 9, 0),
                    'repeat_until' : datetime.datetime(2008, 5, 5, 0, 0),
                    'rule': rule,
                  }
        
        recurring_event.create_generator(**gendata)
        
        self.period = Period(events=TestEvent.objects.all(),
                            start = datetime.datetime(2008,1,4,7,0),
                            end = datetime.datetime(2008,1,21,7,0))

    def test_get_occurrences(self):
        occurrence_list = self.period.occurrences
        self.assertEqual(["%s to %s" %(o.start, o.end) for o in occurrence_list],
            ['2008-01-05 08:00:00 to 2008-01-05 09:00:00',
             '2008-01-12 08:00:00 to 2008-01-12 09:00:00',
             '2008-01-19 08:00:00 to 2008-01-19 09:00:00'])

    def test_get_occurrence_partials(self):
        occurrence_dicts = self.period.get_occurrence_partials()
        self.assertEqual(
            [(occ_dict["class"],
            occ_dict["occurrence"].start,
            occ_dict["occurrence"].end)
            for occ_dict in occurrence_dicts],
            [
                (1,
                 datetime.datetime(2008, 1, 5, 8, 0),
                 datetime.datetime(2008, 1, 5, 9, 0)),
                (1,
                 datetime.datetime(2008, 1, 12, 8, 0),
                 datetime.datetime(2008, 1, 12, 9, 0)),
                (1,
                 datetime.datetime(2008, 1, 19, 8, 0),
                 datetime.datetime(2008, 1, 19, 9, 0))
            ])

    def test_has_occurrence(self):
        self.assert_( self.period.has_occurrences() )
        slot = self.period.get_time_slot( datetime.datetime(2008,1,4,7,0),
                                          datetime.datetime(2008,1,4,7,12) )
        self.failIf( slot.has_occurrences() )


class TestYear(TestCase):

    def setUp(self):
        super(TestYear, self).setUp() #monkeypatch in the test app
        self.year = Year(events=[], date=datetime.datetime(2008,4,1))

    def test_get_months(self):
        months = self.year.get_months()
        self.assertEqual([month.start for month in months],
            [datetime.datetime(2008, i, 1) for i in range(1,13)])


class TestMonth(TestCase):

    def setUp(self):
        super(TestMonth, self).setUp() #monkeypatch in the test app
        rule = Rule(frequency = "WEEKLY")
        rule.save()
        eventdata = {
                'title': 'Recent Event',
               }
        recurring_event = TestEvent(**eventdata)
        recurring_event.save()

        gendata = {
                'start': datetime.datetime(2008, 1, 5, 8, 0),
                'end': datetime.datetime(2008, 1, 5, 9, 0),
                'repeat_until' : datetime.datetime(2008, 5, 5, 0, 0),
                'rule': rule,
        }

        recurring_event.create_generator(**gendata)

        self.month = Month(events=TestEvent.objects.all(),
                           date=datetime.datetime(2008, 2, 7, 9, 0))

    def test_get_weeks(self):
        weeks = self.month.get_weeks()
        actuals = [(week.start,week.end) for week in weeks]

        if FIRST_DAY_OF_WEEK == 0:
            expecteds = [
                (datetime.datetime(2008, 1, 27, 0, 0),
                 datetime.datetime(2008, 2, 3, 0, 0)),
                (datetime.datetime(2008, 2, 3, 0, 0),
                 datetime.datetime(2008, 2, 10, 0, 0)),
                (datetime.datetime(2008, 2, 10, 0, 0),
                 datetime.datetime(2008, 2, 17, 0, 0)),
                (datetime.datetime(2008, 2, 17, 0, 0),
                 datetime.datetime(2008, 2, 24, 0, 0)),
                (datetime.datetime(2008, 2, 24, 0, 0),
                 datetime.datetime(2008, 3, 2, 0, 0))
            ]
        else:
            expecteds = [
                (datetime.datetime(2008, 1, 28, 0, 0),
                 datetime.datetime(2008, 2, 4, 0, 0)),
                (datetime.datetime(2008, 2, 4, 0, 0),
                 datetime.datetime(2008, 2, 11, 0, 0)),
                (datetime.datetime(2008, 2, 11, 0, 0),
                 datetime.datetime(2008, 2, 18, 0, 0)),
                (datetime.datetime(2008, 2, 18, 0, 0),
                 datetime.datetime(2008, 2, 25, 0, 0)),
                (datetime.datetime(2008, 2, 25, 0, 0),
                 datetime.datetime(2008, 3, 3, 0, 0))
            ]

        for actual, expected in zip(actuals, expecteds):
            self.assertEqual(actual, expected)

    def test_get_days(self):
        """
        get_days returns a generator of 7 days for a given week
        """
        
        weeks = self.month.get_weeks()
        week = list(weeks)[0]
        days = week.get_days()
                
        actuals = [(len(day.occurrences), day.start, day.end) for day in days]

        if FIRST_DAY_OF_WEEK == 0:
            expecteds = [
                (0, datetime.datetime(2008, 1, 27, 0, 0),
                 datetime.datetime(2008, 1, 28, 0, 0)),
                (0, datetime.datetime(2008, 1, 28, 0, 0),
                 datetime.datetime(2008, 1, 29, 0, 0)),
                (0, datetime.datetime(2008, 1, 29, 0, 0),
                 datetime.datetime(2008, 1, 30, 0, 0)),
                (0, datetime.datetime(2008, 1, 30, 0, 0),
                 datetime.datetime(2008, 1, 31, 0, 0)),
                (0, datetime.datetime(2008, 1, 31, 0, 0),
                 datetime.datetime(2008, 2, 1, 0, 0)),
                (0, datetime.datetime(2008, 2, 1, 0, 0),
                 datetime.datetime(2008, 2, 2, 0, 0)),
                (1, datetime.datetime(2008, 2, 2, 0, 0),
                 datetime.datetime(2008, 2, 3, 0, 0)),
            ]

        else:
            expecteds = [
               (0, datetime.datetime(2008, 1, 28, 0, 0),
                 datetime.datetime(2008, 1, 29, 0, 0)),
                (0, datetime.datetime(2008, 1, 29, 0, 0),
                 datetime.datetime(2008, 1, 30, 0, 0)),
                (0, datetime.datetime(2008, 1, 30, 0, 0),
                 datetime.datetime(2008, 1, 31, 0, 0)),
                (0, datetime.datetime(2008, 1, 31, 0, 0),
                 datetime.datetime(2008, 2, 1, 0, 0)),
                (0, datetime.datetime(2008, 2, 1, 0, 0),
                 datetime.datetime(2008, 2, 2, 0, 0)),
                (1, datetime.datetime(2008, 2, 2, 0, 0),
                 datetime.datetime(2008, 2, 3, 0, 0)),
                (0, datetime.datetime(2008, 2, 3, 0, 0),
                 datetime.datetime(2008, 2, 4, 0, 0))
            ]
        
        for actual, expected in zip(actuals, expecteds):
            try:
                self.assertEqual(actual, expected)
            except AssertionError:
                import pdb; pdb.set_trace()



    def test_month_convenience_functions(self):
        self.assertEqual( self.month.prev_month().start, datetime.datetime(2008, 1, 1, 0, 0))
        self.assertEqual( self.month.next_month().start, datetime.datetime(2008, 3, 1, 0, 0))
        self.assertEqual( self.month.current_year().start, datetime.datetime(2008, 1, 1, 0, 0))
        self.assertEqual( self.month.prev_year().start, datetime.datetime(2007, 1, 1, 0, 0))
        self.assertEqual( self.month.next_year().start, datetime.datetime(2009, 1, 1, 0, 0))


class TestDay(TestCase):
    def setUp(self):
        super(TestDay, self).setUp() #monkeypatch in the test app
        self.day = Day(events=TestEvent.objects.all(),
                           date=datetime.datetime(2008, 2, 7, 9, 0))

    def test_day_setup(self):
        self.assertEqual( self.day.start, datetime.datetime(2008, 2, 7, 0, 0))
        self.assertEqual( self.day.end, datetime.datetime(2008, 2, 8, 0, 0))

    def test_day_convenience_functions(self):
        self.assertEqual( self.day.prev_day().start, datetime.datetime(2008, 2, 6, 0, 0))
        self.assertEqual( self.day.next_day().start, datetime.datetime(2008, 2, 8, 0, 0))

    def test_time_slot(self):
        slot_start = datetime.datetime(2008, 2, 7, 13, 30)
        slot_end = datetime.datetime(2008, 2, 7, 15, 0)
        period = self.day.get_time_slot( slot_start, slot_end )
        self.assertEqual( period.start, slot_start )
        self.assertEqual( period.end, slot_end )


class TestOccurrencePool(TestCase):

    def setUp(self):
        super(TestOccurrencePool, self).setUp() #monkeypatch in the test app
        rule = Rule(frequency = "WEEKLY")
        rule.save()
        data = {
                'title': 'Recent Event',
               }
        self.recurring_event = TestEvent(**data)
        self.recurring_event.save()

        gendata = {
                'start': datetime.datetime(2008, 1, 5, 8, 0),
                'end': datetime.datetime(2008, 1, 5, 9, 0),
                'repeat_until' : datetime.datetime(2008, 5, 5, 0, 0),
                'rule': rule,
        }

        self.recurring_event.create_generator(**gendata)

    def testPeriodFromPool(self):
        """
            Test that period initiated with occurrence_pool returns the same occurrences as "straigh" period
            in a corner case whereby a period's start date is equal to the occurrence's end date
        """
        start = datetime.datetime(2008, 1, 5, 9, 0)
        end = datetime.datetime(2008, 1, 5, 10, 0)
        parent_period = Period(TestEvent.objects.all(), start, end)
        period = Period(parent_period.events, start, end, parent_period.get_exceptional_occurrences(), parent_period.occurrences)
        self.assertEquals(parent_period.occurrences, period.occurrences)

