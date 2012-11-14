import calendar
from datetime import date, timedelta
from dateutil.relativedelta import *
from django import template
from django.template.context import RequestContext
from django.template import TemplateSyntaxError

from eventtools.models.events import EventBase

register = template.Library()

def month_calendar(context, events_pool=[], month=None, show_header=True, selected_start=None, selected_end=None, week_start=0, strip_empty_weeks=None):
    """
    Creates a configurable html calendar displaying one month
    
    Optional arguments:
    
    month: a date object representing the month to be displayed (ie. it needs to be a date within the month to be displayed).
    show_header:
    selected_start:
    selected_end:
    week_start:
    strip_empty_weeks: None, 'leading', 'trailing', 'both'
    """

    cal = calendar.Calendar(week_start)
    today = date.today()
    if not month:
        month = date.today()
    if not selected_end:
        selected_end = selected_start
        
    # month_calendar is a list of the weeks in the month of the year as full weeks. Weeks are lists of seven day numbers
    month_calendar = cal.monthdatescalendar(month.year, month.month)
    
    events_by_date = {}
    
    if isinstance(events_pool, EventBase):
        events_pool = [events_pool]
    
    for event in events_pool:
        occs = event.get_occurrences(month_calendar[0][0], month_calendar[-1][-1])
        for occ in occs:
            if events_by_date.has_key(occ.start_date):
                events_by_date[occ.start_date].append(occ.merged_event)
            else:
                events_by_date[occ.start_date] = [occ.merged_event]

    # annotate each day with a list of class names that describes their status in the calendar - not_in_month, today, selected
    def annotate(day):
        classes = []
        if day.month != month.month:
            classes.append('not_in_month')
        if day == today:
            classes.append('today')
        if selected_start:
            if selected_end >= day >= selected_start:
                classes.append('selected')
        events = events_by_date.get(day, [])
        if events:
            classes.append("has_events")
        else:
            classes.append("no_events")
        return {'date': day, 'classes': classes, 'events': events}

    month_calendar = [map(annotate, week) for week in month_calendar]

    STRIP_EMPTY_WEEKS_OPTIONS = (None, 'leading', 'trailing', 'both')
    if strip_empty_weeks not in STRIP_EMPTY_WEEKS_OPTIONS:
        raise TemplateSyntaxError(
            "strip_empty_weeks argument must be one of %r, not %r" % (
                STRIP_EMPTY_WEEKS_OPTIONS, strip_empty_weeks))

    if strip_empty_weeks:
        def is_empty(week):
            return not any([any(day['events']) for day in week])
        empty_weeks = [is_empty(week) for week in month_calendar]

        if all(empty_weeks):
            pass # or remove altogether?
        else:
            start, end = 0, len(empty_weeks)
            if strip_empty_weeks in ('leading', 'both'):
                start = empty_weeks.index(False)
            if strip_empty_weeks in ('trailing', 'both'):
                empty_weeks.reverse()
                end -= empty_weeks.index(False)
            month_calendar = month_calendar[start:end]

    links = {'prev': month+relativedelta(months=-1), 'next': month+relativedelta(months=+1)}

    return {'month': month, 'month_calendar': month_calendar, 'today': today, 'links': links, 'show_header': show_header, "request":context['request']}

register.inclusion_tag('eventtools/month_calendar.html', takes_context=True)(month_calendar)

def annotated_day(context, day, classes=None, events=None):
    return {'day': day, 'classes': classes, 'events': events, "request":context['request']}
register.inclusion_tag('eventtools/annotated_day.html', takes_context=True)(annotated_day)
