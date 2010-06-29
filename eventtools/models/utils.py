# −*− coding: UTF−8 −*−
class MergedObject():
    """
    Objects of this class behave as though they are a merge of two other objects (which we'll call General and Special). The attributes of Special override the corresponding attributes of General, *unless* the value of the attribute in Special == None.
    
    All attributes are read-only, to save you from a world of pain.
    
    """

    def __init__(self, general, special):
        self._general = general
        self._special = special
        
    def __getattr__(self, value):
        
        try:
            result = getattr(self._special, value)
            if result == None:
                raise AttributeError
        except AttributeError:
            result = getattr(self._general, value)

        return result
        
    def __setattr__(self, attr, value):
        if attr in ['_general', '_special']:
            self.__dict__[attr] = value
        else:
            raise AttributeError("Set the attribute on one of the objects that are being merged.")
    
