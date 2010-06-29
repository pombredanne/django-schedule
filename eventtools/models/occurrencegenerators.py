# −*− coding: UTF−8 −*−
from dateutil import rrule
from django.db.models.base import ModelBase
from eventtools.utils import OccurrenceReplacer
import datetime
from django.template.defaultfilters import date as date_filter
from django.db import models
from django.utils.translation import ugettext, ugettext_lazy as _
from rules import Rule

class OccurrenceGeneratorModelBase(ModelBase):
    """
    When we create an OccurrenceGenerator, add to it an occurrence_model_name so it knows what to generate.
    """
    
    def __init__(cls, name, bases, attrs):
        if name != 'OccurrenceGeneratorBase': # This should only fire if this is a subclass
            model_name = name[0:-len("Generator")].lower()
            cls.add_to_class('_occurrence_model_name', model_name)
        super(OccurrenceGeneratorModelBase, cls).__init__(name, bases, attrs)
    
class OccurrenceGeneratorBase(models.Model):
    """
    Defines a set of repetition rules for an event
    """
    
    __metaclass__ = OccurrenceGeneratorModelBase
    
    first_start_date = models.DateField(_('first start date'))
    first_start_time = models.TimeField(_('first start time'))
    first_end_date = models.DateField(_('first end date'), null = True, blank = True)
    first_end_time = models.TimeField(_('first end time')) #wasn't originally required, but it turns out you do have to say when an event ends...
    rule = models.ForeignKey(Rule, verbose_name=_("repetition rule"), null = True, blank = True, help_text="Select '----' for a one-off event.")
    repeat_until = models.DateTimeField(null = True, blank = True, help_text=_("This date is ignored for one-off events."))
    
    class Meta:
        ordering = ('first_start_date', 'first_start_time')
        abstract = True
        verbose_name = _('occurrence generator')
        verbose_name_plural = _('occurrence generators')

    def _occurrence_model(self):
        return models.get_model(self._meta.app_label, self._occurrence_model_name)
    OccurrenceModel = property(_occurrence_model)

        
    def _end_recurring_period(self):
        return self.repeat_until
#         if self.end:
#             return datetime.datetime.combine(self.end_day, datetime.time.max)
#         else:
#             return None	
    end_recurring_period = property(_end_recurring_period)

    # for backwards compatibility    
    def _get_start(self):
        return datetime.datetime.combine(self.first_start_date, self.first_start_time)

    def _set_start(self, value):
        self.first_start_date = value.date()
        self.first_start_time = value.time()
        
    start = property(_get_start, _set_start)
    
    def _get_end_time(self):
        return self.first_end_time
        
    def _set_end_time(self, value):
        self.first_end_time = value
    
    end_time = property(_get_end_time, _set_end_time)    
        
    def _end(self):
        return datetime.datetime.combine(self.first_end_date or self.first_start_date, self.first_end_time)
    end = property(_end)

    def __unicode__(self):
        date_format = u'l, %s' % ugettext("DATE_FORMAT")
        return ugettext('%(title)s: %(start)s-%(end)s') % {
            'title': unicode(self.event),
            'start': date_filter(self.start, date_format),
            'end': date_filter(self.end, date_format),
        }

    def get_occurrences(self, start, end):
        exceptional_occurrences = self.occurrences.all()
        occ_replacer = OccurrenceReplacer(exceptional_occurrences)
        occurrences = self._get_occurrence_list(start, end)
        final_occurrences = []
        for occ in occurrences:
            # replace occurrences with their exceptional counterparts
            if occ_replacer.has_occurrence(occ):
                p_occ = occ_replacer.get_occurrence(occ)
                # ...but only if they are within this period
                if p_occ.start < end and p_occ.end >= start:
                    final_occurrences.append(p_occ)
            else:
              final_occurrences.append(occ)
        # then add exceptional occurrences which originated outside of this period but now
        # fall within it
        final_occurrences += occ_replacer.get_additional_occurrences(start, end)

        # import pdb; pdb.set_trace()
        return final_occurrences
        

    def get_rrule_object(self):
        if self.rule is not None:
            if self.rule.complex_rule:
                try:
                    return rrule.rrulestr(str(self.rule.complex_rule),dtstart=self.start)
                except:
                    pass
            params = self.rule.get_params()
            frequency = 'rrule.%s' % self.rule.frequency
            simple_rule = rrule.rrule(eval(frequency), dtstart=self.start, **params)
            set = rrule.rruleset()
            set.rrule(simple_rule)
#             goodfriday = rrule.rrule(rrule.YEARLY, dtstart=self.start, byeaster=-2)
#             christmas = rrule.rrule(rrule.YEARLY, dtstart=self.start, bymonth=12, bymonthday=25)
#             set.exrule(goodfriday)
#             set.exrule(christmas)
            return set

    def _create_occurrence(self, start, end=None):
        if end is None:
            end = start + (self.end - self.start)
        occ = self.OccurrenceModel(
            generator=self,
            unvaried_start_date=start.date(),
            unvaried_start_time=start.time(),
            unvaried_end_date=end.date(),
            unvaried_end_time=end.time(),
        )
        return occ
    
    def check_for_exceptions(self, occ):
        """
        Pass in an occurrence, pass out the occurrence, or an exceptional occurrence, if one exists in the db.
        """
        try:
            return self.OccurrenceModel.objects.get(
                generator = self,
                unvaried_start_date = occ.unvaried_start_date,
                unvaried_start_time = occ.unvaried_start_time,
                unvaried_end_date = occ.unvaried_end_date,
                unvaried_end_time = occ.unvaried_end_time,
            )
        except self.OccurrenceModel.DoesNotExist:
            return occ
                
    def get_first_occurrence(self):
        occ = self.OccurrenceModel(
                generator=self,
                unvaried_start_date=self.first_start_date,
                unvaried_start_time=self.first_start_time,
                unvaried_end_date=self.first_end_date,
                unvaried_end_time=self.first_end_time,
            )
        occ = self.check_for_exceptions(occ)
        return occ
    
    def get_one_occurrence(self):
        """
        This gets ANY accurrence, it doesn't matter which.
        So the quick thing is to try getting one from the database.
        If that fails, then just create the first occurrence.
        """
        try:
            return self.OccurrenceModel.objects.filter(generator=self)[0]
        except IndexError:
            return self.get_first_occurrence()
        return occ

    def get_occurrence(self, date):
        rule = self.get_rrule_object()
        if rule:
            next_occurrence = rule.after(date, inc=True)
        else:
            next_occurrence = self.start
        if next_occurrence == date:
            try:
                return self.OccurrenceModel.objects.get(generator__event = self, unvaried_start_date = date)
            except self.OccurrenceModel.DoesNotExist:
                return self._create_occurrence(next_occurrence)
        # import pdb; pdb.set_trace()

    def _get_occurrence_list(self, start, end):
        """
        generates a list of unexceptional occurrences for this event from start to end.
        """
        
        difference = (self.end - self.start)
        if self.rule is not None:
            occurrences = []
            if self.end_recurring_period and self.end_recurring_period < end:
                end = self.end_recurring_period
            rule = self.get_rrule_object()
            o_starts = rule.between(start-difference, end, inc=True)
            for o_start in o_starts:
                o_end = o_start + difference
                occurrences.append(self._create_occurrence(o_start, o_end))
            return occurrences
        else:
            # check if event is in the period
            if self.start < end and self.end >= start:
                return [self._create_occurrence(self.start)]
            else:
                return []
                        
    def _occurrences_after_generator(self, after=None):
        """
        returns a generator that produces unexceptional occurrences after the
        datetime ``after``.
        """

        if after is None:
            after = datetime.datetime.now()
        rule = self.get_rrule_object()
        if rule is None:
            if self.end > after:
                yield self._create_occurrence(self.start, self.end)
            raise StopIteration
        date_iter = iter(rule)
        difference = self.end - self.start
        while True:
            o_start = date_iter.next()
            if o_start > self.end_recurring_period:
                raise StopIteration
            o_end = o_start + difference
            if o_end > after:
                yield self._create_occurrence(o_start, o_end)


    def occurrences_after(self, after=None):
        """
        returns a generator that produces occurrences after the datetime
        ``after``.	Includes all of the exceptional Occurrences.
        """
        occ_replacer = OccurrenceReplacer(self.occurrence_set.all())
        generator = self._occurrences_after_generator(after)
        while True:
            next = generator.next()
            yield occ_replacer.get_occurrence(next)