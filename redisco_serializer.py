from redisco.models import Model
from tastypie.serializers import Serializer


class RediscoSerializer(Serializer):
    formats = ['redisco_json', 'json', 'jsonp', 'xml', 'yaml', 'html', 'plist']
    content_types = {
        'json': 'application/json',
        'jsonp': 'text/javascript',
        'xml': 'application/xml',
        'yaml': 'text/yaml',
        'html': 'text/html',
        'plist': 'application/x-plist',
        'redisco_json': 'application/json',
    }

    def redisco_to_dictinary(self, obj):
        if isinstance(obj, list):
            new_list = list()
            for i in obj:
                if isinstance(i, Model):
                    new_list.append(self.redisco_to_dictinary(i))
#                    new_list.append(i.attributes_dict)
            return new_list
        elif isinstance(obj, Model):
            dict = obj.attributes_dict

            if obj._meta.meta and obj._meta.meta.serializable_fields:
                for k, v in dict.items():
                    if not k in obj.Meta.serializable_fields:
                        dict.pop(k)

            return dict
        else:
            return obj


    def to_redisco_json(self, data, options=None):
        dict = data.attributes_dict
        for k, v in dict.items():
            dict[k] = self.redisco_to_dictinary(dict[k])

        if data._meta.meta and data._meta.meta.serializable_fields:
            for k, v in dict.items():
                if not k in data.Meta.serializable_fields:
                    dict.pop(k)
        json = super(RediscoSerializer, self).to_json(dict)
        return json

    def from_redisco_json(self, content):
        pass
