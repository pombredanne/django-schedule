from operator import itemgetter

from django.db import models
from django.db.models.base import ModelBase
from django.db.models.fields import FieldDoesNotExist
from django.db.models import Count
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext, ugettext_lazy as _
from django.template.defaultfilters import urlencode

from mptt.models import MPTTModel, MPTTModelBase
from mptt.managers import TreeManager

from eventtools.utils.inheritingdefault import ModelInstanceAwareDefault #TODO: deprecate
from eventtools.utils.pprint_timespan \
    import pprint_datetime_span, pprint_date_span
from eventtools.utils.dateranges import DateTester
from eventtools.utils.domain import django_root_url

class EventQuerySet(models.query.QuerySet):
    # much as you may be tempted to add "starts_between" and other
    # OccurrenceQuerySet methods, resist (for the sake of DRYness and some
    # performance). Instead, use OccurrenceQuerySet.starts_between().events().
    # We have to relax this for opening and closing occurrences, as they're 
    # relevant to a particular event.
    
    def occurrences(self, *args, **kwargs):
        """
        Returns the occurrences for events in this queryset. NB that only
        occurrences attached directly to events, ie not child events, are returned.
        """
        return self.model.OccurrenceModel().objects\
            .filter(event__in=self)\
            .filter(*args, **kwargs)
        
    def complete_occurrences(self, *args, **kwargs):
        """
        Returns the occurrences for events in this queryset and their children.
        """
        event_ids = []
        for e in self:
            for c in e.get_descendants(include_self=True):
                event_ids.append(c.id)
        
        return self.model.OccurrenceModel().objects\
            .filter(event__in=event_ids)\
            .filter(*args, **kwargs)
        
    def opening_occurrences(self):
        """
        Returns the opening occurrences for the events in this queryset.
        
        Since it uses Event.opening_occurrence(), the default behaviour is to
        look at the complete_occurrences (ie, occurrences of children are
        included).
        """
        pks = []
        for e in self:
            try:
                pks.append(e.opening_occurrence().id)
            except AttributeError:
                pass
        return self.occurrences(pk__in=pks)
        
    def closing_occurrences(self):
        """
        Returns the closing occurrences for the events in this queryset.
        
        Since it uses Event.opening_occurrence(), the behaviour is to look at
        the complete_occurrences (ie, occurrences of children are included).
        """
        pks = []
        for e in self:
            try:
                pks.append(e.closing_occurrence().id)
            except AttributeError:
                pass
        return self.occurrences(pk__in=pks)
        
    def _with_relatives_having(self, relatives_fn, *args, **kwargs):
        """
        Return the set of items in self that have relatives matching a
        particular criteria.
        """
        match_ids = set()
        for obj in self:
            matches = relatives_fn(obj)
            if matches.count(): #weird bug where filter returns results on an empty qs!
                matches = matches.filter(*args, **kwargs)
                if matches.count():
                    match_ids.add(obj.id)
        return self.filter(id__in=match_ids)

    def _without_relatives_having(self, relatives_fn, *args, **kwargs):
        """
        Return the set of items in self that have 0 relatives matching a
        particular criteria.
        """
        match_ids = set()
        for obj in self:
            matches = relatives_fn(obj)
            if matches.count(): #weird bug where filter returns results on an empty qs!
                matches = matches.filter(*args, **kwargs)
                if matches.count() == 0:
                    match_ids.add(obj.id)
            else: #no relatives => win
                    match_ids.add(obj.id)                
        return self.filter(id__in=match_ids)

    def with_children_having(self, *args, **kwargs):
        return self._with_relatives_having(
            lambda x: x.get_children(), *args, **kwargs
        )
        
    def with_descendants_having(self, *args, **kwargs):
        include_self = kwargs.pop('include_self', True)
        return self._with_relatives_having(
            lambda x: x.get_descendants(include_self=include_self),
            *args,
            **kwargs
        )

    def with_parent_having(self, *args, **kwargs):
        return self._with_relatives_having(
            lambda x: self.filter(id=x.parent_id), *args, **kwargs
        )

    def with_ancestors_having(self, *args, **kwargs):
        return self._with_relatives_having(
            lambda x: x.get_ancestors(), *args, **kwargs
        )

    def without_children_having(self, *args, **kwargs):
        return self._without_relatives_having(
            lambda x: x.get_children(), *args, **kwargs
        )

    def without_descendants_having(self, *args, **kwargs):
        include_self = kwargs.pop('include_self', True)
        return self._without_relatives_having(
            lambda x: x.get_descendants(include_self=include_self), 
            *args, **kwargs
        )

    def without_parent_having(self, *args, **kwargs):
        return self._without_relatives_having(
            lambda x: self.filter(id=x.parent_id), *args, **kwargs
        )

    def without_ancestors_having(self, *args, **kwargs):
        return self._without_relatives_having(
            lambda x: x.get_ancestors(), *args, **kwargs
        )
        
    #some simple annotations
    def having_occurrences(self):
        return self.annotate(num_occurrences=Count('occurrences'))\
            .filter(num_occurrences__gt=0)

    def having_n_occurrences(self, n):
        return self.annotate(num_occurrences=Count('occurrences'))\
            .filter(num_occurrences=n)

    def having_no_occurrences(self):
        return self.having_n_occurrences(0)
        
    def highest_having_occurrences(self):
        """
        the highest objects that have occurrences meet these conditions:
            a) they have occurrences
            b) none of their ancestors have occurrences
        
        This is a possible first blush at 'The List Of Events', since it is the
        longest list of events whose descendants' occurrences will cover the
        entire set of occurrences with no repetitions.
        """
        return self.having_occurrences()._without_relatives_having(
            lambda x: x.get_ancestors().annotate(
                num_occurrences=Count('occurrences')
            ),
            num_occurrences__gt=0
        )


class EventTreeManager(TreeManager):
    
    def get_query_set(self): 
        return EventQuerySet(self.model).order_by(
            self.tree_id_attr, self.left_attr)
        
    def occurrences(self, *args, **kwargs):
        return self.get_query_set().occurrences(*args, **kwargs)
    def complete_occurrences(self, *args, **kwargs):
        return self.get_query_set().complete_occurrences(*args, **kwargs)
    def opening_occurrences(self, *args, **kwargs):
        return self.get_query_set().opening_occurrences(*args, **kwargs)
    def closing_occurrences(self, *args, **kwargs):
        return self.get_query_set().closing_occurrences(*args, **kwargs)

 
    def with_children_having(self, *args, **kwargs):
        return self.get_query_set().with_children_having(*args, **kwargs)        
    def with_descendants_having(self, *args, **kwargs):
        return self.get_query_set().with_descendants_having(*args, **kwargs)        
    def with_parent_having(self, *args, **kwargs):
        return self.get_query_set().with_parent_having(*args, **kwargs)        
    def with_ancestors_having(self, *args, **kwargs):
        return self.get_query_set().with_ancestors_having(*args, **kwargs)        
    def without_children_having(self, *args, **kwargs):
        return self.get_query_set().without_children_having(*args, **kwargs)        
    def without_descendants_having(self, *args, **kwargs):
        return self.get_query_set().without_descendants_having(*args, **kwargs)        
    def without_parent_having(self, *args, **kwargs):
        return self.get_query_set().without_parent_having(*args, **kwargs)        
    def without_ancestors_having(self, *args, **kwargs):
        return self.get_query_set().without_ancestors_having(*args, **kwargs)        
    def having_occurrences(self):
        return self.get_query_set().having_occurrences()        
    def having_n_occurrences(self, n):
        return self.get_query_set().having_n_occurrences(n)        
    def having_no_occurrences(self):
        return self.get_query_set().having_no_occurrences()        
    def highest_having_occurrences(self):
        return self.get_query_set().highest_having_occurrences()        
            
class EventOptions(object):
    """
    Options class for Event models. Use this as an inner class called EventMeta.
    ie.:
    
    class MyModel(EventModel):
        class EventMeta:
            fields_to_inherit = ['name', 'slug', 'description']
        ...     
    """
    
    fields_to_inherit = []
    event_manager_class = EventTreeManager
    event_manager_attr = 'eventobjects'
    
    def __init__(self, opts):
        # Override defaults with options provided
        if opts:
            for key, value in opts.__dict__.iteritems():
                setattr(self, key, value)


class EventModelBase(MPTTModelBase):
    def __new__(meta, class_name, bases, class_dict):
        """
        Create subclasses of EventModel. This:
         - (via super) adds the MPTT fields to the class
         - adds the EventManager to the model
         - overrides MPTT's TreeManager to the model, so that the treemanager
           includes eventtools methods.
        """
        event_opts = class_dict.pop('EventMeta', None)
        class_dict['_event_meta'] = EventOptions(event_opts)
        cls = super(EventModelBase, meta) \
            .__new__(meta, class_name, bases, class_dict)
                
        try:
            EventModel
        except NameError:
            # We're defining the base class right now, so don't do anything
            # We only want to add this stuff to the subclasses.
            # (Otherwise if field names are customized, we'll end up adding two
            # copies)
            pass
        else:
            for field_name in class_dict['_event_meta'].fields_to_inherit:
                try:
                    field = cls._meta.get_field(field_name)
                    #injecting our fancy inheriting default
                    field.default = ModelInstanceAwareDefault(
                        field_name,
                        field.default
                    )
                except models.FieldDoesNotExist:
                    continue
            
            # Add a custom manager
            assert issubclass(
                cls._event_meta.event_manager_class, EventTreeManager
            ), 'Custom Event managers must subclass EventTreeManager.'
            
            # since EventTreeManager subclasses TreeManager, it also needs the
            # mptt options
            manager = cls._event_meta.event_manager_class(cls._mptt_meta)
            manager.contribute_to_class(cls, cls._event_meta.event_manager_attr)
            setattr(cls, '_event_manager',
                getattr(cls, cls._event_meta.event_manager_attr)
            )
            
            # override the treemanager with self too,
            # so we don't need to recast all querysets
            manager.contribute_to_class(cls, cls._mptt_meta.tree_manager_attr)
            setattr(cls, '_tree_manager', getattr(cls, cls._mptt_meta.tree_manager_attr))

        return cls

class EventModel(MPTTModel):
    __metaclass__ = EventModelBase
    
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')
    title = models.CharField(max_length=100)
    slug = models.SlugField("URL name", unique=True, help_text="This is used in\
     the event's URL, and should be unique and unchanging.")
    season_description = models.CharField(_("season"), blank=True, null=True, 
        max_length=200, help_text="a summary description of when this event \
        is on (e.g. 24 August - 12 September 2012). One will be generated from \
        the occurrences if not provided)"
    )
    sessions_description = models.TextField(_("sessions"), blank=True,
        null=True, help_text="a detailed description of when sessions are\
        (e.g. \'Tuesdays and Thursdays throughout Feburary, at 10:30am\')"
    )

    class Meta:
        abstract = True
        ordering = ['tree_id', 'lft'] 
    
    def __unicode__(self):
        return self.title

    @classmethod
    def OccurrenceModel(cls):
        """
        Returns the class used for occurrences
        """
        return cls.occurrences.related.model

    @classmethod
    def GeneratorModel(cls):
        """
        Returns the class used for generators
        """
        return cls.generators.related.model
        
    @classmethod
    def ExclusionModel(cls):
        """
        Returns the class used for exclusions
        """
        return cls.exclusions.related.model

    def save(self, *args, **kwargs):
        """
        When an event is saved, the changes to fields are cascaded to children,
        and any endless generators are updated, so that a few more occurrences
        are generated
        """
        #this has to happen before super.save, so that we can tell what's
        #changed
        self._cascade_changes_to_children()
        r = super(EventModel, self).save(*args, **kwargs)

        endless_generators = self.generators.filter(repeat_until__isnull=True)
        [g.save() for g in endless_generators]

        return r
                
    def reload(self):
        """
        Used for refreshing events in a queryset that may have changed.        
        Call with x = x.reload() - it doesn't change self.
        """
        return type(self)._event_manager.get(pk=self.pk)
        
    def _cascade_changes_to_children(self):
        if self.pk:
            saved_self = type(self)._event_manager.get(pk=self.pk)
            attribs = type(self)._event_meta.fields_to_inherit
        
            for child in self.get_children():
                for a in attribs:
                    try:
                        saved_value = getattr(saved_self, a)
                        ch_value = getattr(child, a)
                        if ch_value == saved_value:
                            #the child's value is unchanged from the parent
                            new_value = getattr(self, a)
                            setattr(child, a, new_value)
                    except AttributeError:
                        continue
                child.save() #cascades to grandchildren
    
    def complete_occurrences(self):
        return self.get_descendants(include_self=True).occurrences()

    def complete_occurrences_count(self):
        """needed by admin"""
        return self.complete_occurrences().count()
        
    def direct_opening_occurrence(self):
        try:
            return self.occurrences.all()[0]
        except IndexError:
            return None
        
    def direct_closing_occurrence(self):
        try:
            return self.occurrences.all().reverse()[0]
        except IndexError:
            return None

    def complete_opening_occurrence(self):
        try:
            return self.complete_occurrences().all()[0]
        except IndexError:
            return None
        
    def complete_closing_occurrence(self):
        try:
            return self.complete_occurrences().all().reverse()[0]
        except IndexError:
            return None
            
    opening_occurrence = complete_opening_occurrence
    closing_occurrence = complete_closing_occurrence


    def get_absolute_url(self):
        return reverse('events:event', kwargs={'event_slug': self.slug })
        
    def has_finished(self):
        """ the event has finished if the closing occurrence has finished. """
        return self.closing_occurrence().has_finished
                        
    def season(self):
        """
        Returns a string describing the first and last dates of this event.
        """
        if self.season_description:
            return self.season_description
        
        o = self.opening_occurrence()
        c = self.closing_occurrence()
        if o and c:
            first = o.start.date()
            last = c.start.date()        
            return pprint_date_span(first, last)

        return None

    def sessions(self):
        return self.sessions_description # TODO: fall back to auto-generated?

    def highest_ancestor_having_occurrences(self, include_self=True, test=False):
        ancestors = self.get_ancestors()
        if ancestors:
            ancestors_with_occurrences = ancestors.having_occurrences()
            if ancestors_with_occurrences:
                return ancestors_with_occurrences[0]
        if include_self and self.complete_occurrences().count():
            return self
        return None
        
    # ical functions coming back soon
    # def ics_url(self):
    #     """
    #     Needs to be fully-qualified (for sending to calendar apps). Your app needs to define
    #     an 'ics_for_event' view and url, and properties for populating an ics for each event
    #     (see OccurrenceModel.as_icalendar for default properties)
    #     """
    #     return django_root_url() + reverse("ics_for_event", args=[self.pk])
    # 
    # def webcal_url(self):
    #     return self.ics_url().replace("http://", "webcal://").replace("https://", "webcal://")
    #     
    # def gcal_url(self):
    #     return  "http://www.google.com/calendar/render?cid=%s" % urlencode(self.ics_url())
