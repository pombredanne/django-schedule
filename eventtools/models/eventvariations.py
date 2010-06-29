from django.db.models.base import ModelBase
from django.db import models
from django.utils.translation import ugettext, ugettext_lazy as _

"""
If you're using EventBase, and now have OccurrenceGenerators and Occurences, you may find that you want to use a variation of an event for one occurrence. An EventVariationBase subclass is useful if there's something different about one (or more) of a series of events. For example:

	* There is a talk by the director after the screening
	* Graham the curator is away, so Jo is giving the talk instead
	* There is a special price for schools one day
	* An event is in a different venue
	* etc.

You can specify the fields that are allowed to be varied in a subclass of EventVariationBase. To attach an EventVariationBase model to an EventBase model, define a class property in EventBase called `varied_by`, and another in EventVariationBase called `varies`, each with the string of the model you want to connect to. For example:

    class Event(EventBase):
        title = models.CharField(_("Title"), max_length = 255)
        slug = models.SlugField(_("Slug"), max_length = 255)
        location = models.CharField(_("Location"), max_length = 255, blank=True)
        description = models.TextField(_("Description"), max_length=255, blank=True)   

        varied_by = "EventVariation"
    
        def __unicode__(self):
            return self.title
    
    class EventVariation(EventVariationBase):
        varies = "Event"
    
        location = models.CharField(_("Alternative Location"), max_length = 255, blank=True, null=True)
        description = models.TextField(_("Alternative Description"), max_length=255, blank=True, null=True)
    
EventVariation says that you are only allowed to vary `location` and `description` (and, by ommission, not `title`).

This plays out in each Occurrence, which will have a 'varied_event' field automatically added to it. For the occurrence o, you can access `o.varied_event`, `o.unvaried_event`, and `o.merged_event`. The last of these uses utils.MergedObject to access attributes of varied_event in favour of unvaried_event.

"""

class EventVariationModelBase(ModelBase):
    def __init__(cls, name, bases, attrs):
        if name != 'EventVariationBase': # This should only fire if this is a subclass
            #Inject an unvaried_event FK if none is defined.
            #Uses the unDRY cls.varies to name the class to FK to.
            if not attrs.has_key('unvaried_event'):
                cls.add_to_class('unvaried_event', models.ForeignKey(cls.varies, related_name="variations"))
                
        super(EventVariationModelBase, cls).__init__(name, bases, attrs)


class EventVariationBase(models.Model):
    __metaclass__ = EventVariationModelBase
    
    reason = models.CharField(_("Short reason for variation"), max_length = 255, help_text=_("this won't normally be shown to visitors, but is useful for identifying this variation in lists"))

    def __unicode__(self):
        return self.reason
        
    class Meta:
        abstract = True
