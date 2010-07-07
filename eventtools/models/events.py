# −*− coding: UTF−8 −*−
from django.db.models.base import ModelBase
import datetime
from django.db import models
from django.utils.translation import ugettext, ugettext_lazy as _
import sys
from occurrencegenerators import *
from occurrences import *

from django.core.exceptions import ValidationError

"""
When you subclass EventBase (further down), two more models are injected into your app by EventModelBase (just below).

Say your EventBase subclass is called Lecture. You will get LectureOccurrenceGenerator and LectureOccurrence models. Briefly, OccurrenceGenerators generate Occurrences. Occurrences are saved to the database and retrieved from the database if they contain differences to the Occurrence values.

See occurrencegenerators.py and occurrences.py for details.

How to use EventBase:

Every EventBase model has several OccurrenceGenerators, each of which generate several Occurrences (and save the interesting ones to the database).

You can get the OccurrenceGenerators with Event.generators (it's the reverse relation name).

Since OccurrenceGenerators can generate a potentially infinite number of occurrences, you don't want to be able to get all the occurrences ever (it would take a while). You can tell whether an event has infinite amount of occurrences by seeing whether Event.get_last_day() returns a value. If it returns False, there's no end.

To get an Event's occurrences between two dates:

Event.get_occurrences(start_date, end_date).

This will return a list of EventOccurrences. Remember to use EventOccurrence.merged_event to display the details for each event (since merged_event takes in to account variations).

"""

class EventQuerySetBase(models.query.QuerySet):
    def occurrences_between(self, start, end):        
        occurrences = []
        for item in self:
            occurrences += item.generators.occurrences_between(start, end)
            
        return sorted(occurrences)

    def between(self, start, end):
        event_ids = []
        events = []
        occurrences = self.occurrences_between(start, end)
        
        for occurrence in occurrences:
            # import pdb; pdb.set_trace()
            if occurrence.unvaried_event.id not in event_ids: #just testing the id saves database lookups (er, maybe)
                event_ids.append(occurrence.unvaried_event.id)
                events.append(occurrence.unvaried_event)
    
        return events

class EventManagerBase(models.Manager):
    def get_query_set(self): 
        return EventQuerySetBase(self.model)
        
    def occurrences_between(self, start, end):
        return self.get_query_set().occurrences_between(start, end)
        
    def between(self, start, end):
         return self.get_query_set().between(start, end)

class EventModelBase(ModelBase):
    def __init__(cls, name, bases, attrs):
        """
        Dynamically generate two related classes to handle occurrences (get the vodka out, George).
        
        The two generated classes are ModelNameOccurrence and ModelNameOccurrenceGenerator.        
        """
        if name != 'EventBase': # This should only fire if this is a subclass (maybe we should make devs apply this metaclass to their subclass instead?)
            # Build names for the new classes
            occ_name = "%s%s" % (name, "Occurrence")
            gen_name = "%s%s" % (occ_name, "Generator")
        
            cls.add_to_class('_occurrence_model_name', occ_name)
            cls.add_to_class('_generator_model_name', gen_name)
        
            # Create the generator class
            # globals()[gen_name] # < injecting into globals doesn't work with some of django's import magic. We have to inject the new class directly into the module that contains the EventBase subclass. I am AMAZED that you can do this, and have it still work for future imports.
            setattr(sys.modules[cls.__module__], gen_name, type(gen_name,
                    (OccurrenceGeneratorBase,),
                    dict(__module__ = cls.__module__,),
                )
            )
            generator_class = sys.modules[cls.__module__].__dict__[gen_name]
            
            # add a foreign key back to the event class
            generator_class.add_to_class('event', models.ForeignKey(cls, related_name = 'generators'))

            # Create the occurrence class
            # globals()[occ_name]
            setattr(sys.modules[cls.__module__], occ_name, type(occ_name,
                    (OccurrenceBase,),
                    dict(__module__ = cls.__module__,),
                )
            )
            occurrence_class = sys.modules[cls.__module__].__dict__[occ_name]

            occurrence_class.add_to_class('generator', models.ForeignKey(generator_class, related_name = 'occurrences'))
            if hasattr(cls, 'varied_by'):
               occurrence_class.add_to_class('_varied_event', models.ForeignKey(cls.varied_by, related_name = 'occurrences', null=True))
               # we need to add an unvaried_event FK into the variation class, BUT at this point the variation class hasn't been defined yet. For now, let's insist that this is done by using a base class for variation.

        super(EventModelBase, cls).__init__(name, bases, attrs)

class EventBase(models.Model):
    """
    Event information minus the scheduling details.
    
    Event scheduling is handled by one or more OccurrenceGenerators
    """
    
    #injected by EventModelBase:
    # _occurrence_model_name
    # _generator_model_name
    
    __metaclass__ = EventModelBase
    _date_description = models.TextField(_("Describe when this event occurs"), blank=True, help_text=_("e.g. \"Every Tuesday and Thursday in March 2010\". If this is ommitted, an automatic description will be attempted."))
    
    objects = EventManagerBase()
    
    class Meta:
        abstract = True

    def date_description(self):
        if self._date_description:
            return self._date_description
        gens = self.generators.all()
        if gens:
            return _("\n ").join([g.date_description() for g in gens])
        else:
            return _("Date TBA")
    date_description = property(date_description)
    
    def _opts(self):
        return self._meta
    opts = property(_opts) #for use in templates (without underscore necessary)

    def _occurrence_model(self):
        return models.get_model(self._meta.app_label, self._occurrence_model_name)
    OccurrenceModel = property(_occurrence_model)

    def _generator_model(self):
        return models.get_model(self._meta.app_label, self._generator_model_name)
    GeneratorModel = property(_generator_model)

    def _has_zero_generators(self):
        return self.generators.count() == 0
    has_zero_generators = property(_has_zero_generators)
        
    def _has_multiple_occurrences(self):
        return self.generators.count() > 1 or (self.generators.count() > 0 and self.generators.all()[0].rule != None)
    has_multiple_occurrences = property(_has_multiple_occurrences)
    
    def clean(self):
        """
        validation:
        if there are variations, throw a validation error.
        (otherwise, the normal date_description function is used).
        """
        if self.variations_count() > 0:
            raise ValidationError("Sorry, we can't figure out how to describe an event with variations. Please add your own date description under Visitor Info.")
 
 
    def get_first_generator(self):
        return self.generators.order_by('first_start_date', 'first_start_time')[0]
    first_generator = get_first_generator
            
    def get_first_occurrence(self):
        try:
            return self.first_generator().get_first_occurrence()		
        except IndexError:
            raise IndexError("This Event type has no generators defined")
    get_one_occurrence = get_first_occurrence # for backwards compatibility
    
    def get_occurrences(self, start, end):
        occs = []
        for gen in self.generators.all():
            occs += gen.get_occurrences(start, end)
        return sorted(occs)
        
    def get_last_day(self):
        lastdays = []
        for generator in self.generators.all():
            if not generator.end_recurring_period:
                return False
            lastdays.append(generator.end_recurring_period)
        lastdays.sort()
        return lastdays[-1]

    def edit_occurrences_link(self):
        """ An admin link """
        # if self.has_multiple_occurrences:
        if self.has_zero_generators:
            return _('no occurrences yet (<a href="%s/">add a generator here</a>)' % self.id)
        else:
           return '<a href="%s/occurrences/">%s</a>' % (self.id, unicode(_("view/edit occurrences")))
    edit_occurrences_link.allow_tags = True
    edit_occurrences_link.short_description = _("Occurrences")
    
    def variations_count(self):
        """
        returns the number of variations that this event has
        """
        if self.__class__.varied_by:
            return self.variations.count()
        else:
            return "N/A"  
    variations_count.short_description = _("# Variations")
    
    def create_generator(self, *args, **kwargs):
        #for a bit of backwards compatibility. If you provide two datetimes, they will be split out into dates and times.
        if kwargs.has_key('start'):
            start = kwargs.pop('start')
            kwargs.update({
                'first_start_date': start.date(),
                'first_start_time': start.time()
            })
        if kwargs.has_key('end'):
            end = kwargs.pop('end')
            kwargs.update({
                'first_end_date': end.date(),
                'first_end_time': end.time()
            })
        repeat_until = kwargs.get('repeat_until')
        if repeat_until and isinstance(repeat_until, datetime.date):
            kwargs['repeat_until'] = datetime.datetime.combine(repeat_until, datetime.time.max)

        return self.generators.create(*args, **kwargs)
    
    def create_variation(self, *args, **kwargs):
        kwargs['unvaried_event'] = self
        return self.variations.create(*args, **kwargs)
        
    def next_occurrences(self, num_days=28):
        from events.periods import Period
        first = False
        last = False
        for gen in self.generators.all():
            if not first or gen.start < first:
                first = gen.start
            if gen.rule and not gen.end_day:
                last = False # at least one rule is infinite
                break
            if not gen.end_day:
                genend = gen.start
            else:
                genend = gen.end_recurring_period
            if not last or genend > last:
                last = genend
        if last:
            period = Period(self.generators.all(), first, last)
        else:
            period = Period(self.generators.all(), datetime.datetime.now(), datetime.datetime.now() + datetime.timedelta(days=num_days))		
        return period.get_occurrences()