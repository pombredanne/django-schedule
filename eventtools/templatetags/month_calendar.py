import calendar
from datetime import date, timedelta
from dateutil.relativedelta import *
from django import template

register = template.Library()

def month_calendar(events_pool=[], month=None, show_header=True, selected_start=None, selected_end=None, week_start=0, ):
    """
    Creates a configurable html calendar displaying one month
    
    It takes four optional arguments:
    
    month: a date object representing the month to be displayed (ie. it needs to be a date within the month to be displayed).
    selected_start:
    selected_end:
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
        return {'date': day, 'classes': classes, 'events': events}
        
    month_calendar = [map(annotate, week) for week in month_calendar]
    links = {'prev': month+relativedelta(months=-1), 'next': month+relativedelta(months=+1)}
    
    return {'month': month, 'month_calendar': month_calendar, 'today': today, 'links': links, 'show_header': show_header}

register.inclusion_tag('month_calendar.html')(month_calendar)

def annotated_day(day, classes=None, events=None):
    return {'day': day, 'classes': classes, 'events': events}
register.inclusion_tag('annotated_day.html')(annotated_day)
