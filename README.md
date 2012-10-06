redisco-resources
=================

Redisco model resource and serializer for Django TastyPie

To use your redisco models with TastyPie, simply inherit from RediscoModelResource rathern than ModelResource
This is a direct modification of ModelResource from TastyPie

```
# models.py

from redisco import models as redisco_models

class MyObject(redisco_models.Model):
    some_value = redisco_models.CharField(max_length=30)
    is_active = redisco_models.BooleanField()
```


```
# resources.py

class MyResource(RediscoModelResource):
    id = fields.CharField(unique=True, attribute='id')

    class Meta:
        resource_name = 'my_object'
        object_class = MyObject
        filtering = {'my_id':['exact',]}
```


To use the redisco model serializer:

```
import RediscoSerializer

serializer = RediscoSerializer()

obj = MyObject.objects.get_or_create(some_value='hello world)

# To serialize
response_data['obj'] = serializer.serialize(obj)

```

