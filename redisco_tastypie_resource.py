from django.db.models.sql.constants import LOOKUP_SEP, QUERY_TERMS
from tastypie.bundle import Bundle
from tastypie.constants import ALL_WITH_RELATIONS, ALL
from tastypie.exceptions import InvalidFilterError, BadRequest
from tastypie.resources import Resource
from tastypie.utils.dict import dict_strip_unicode_keys

class RediscoModelResource(Resource):

    def obj_get(self, request=None, **kwargs):
        game = self.Meta.object_class.objects.get_by_id(kwargs['pk'])
        return game


    def get_object_list(self, request):
        manager = self.Meta.object_class.objects
        return manager

    def obj_get_list(self, request=None, **kwargs):
        """
        A ORM-specific implementation of ``obj_get_list``.

        Takes an optional ``request`` object, whose ``GET`` dictionary can be
        used to narrow the query.
        """
        filters = {}

        if hasattr(request, 'GET'):
            # Grab a mutable copy.
            filters = request.GET.copy()

        # Update with the provided kwargs.
        filters.update(kwargs)
        applicable_filters = self.build_filters(filters=filters)

        try:
            base_object_list = self.apply_filters(request, applicable_filters)
            return self.apply_authorization_limits(request, base_object_list)
        except ValueError:
            raise BadRequest("Invalid resource lookup data provided (mismatched type).")

    def build_filters(self, filters=None):
            """
            Given a dictionary of filters, create the necessary ORM-level filters.

            Keys should be resource fields, **NOT** model fields.

            Valid values are either a list of Django filter types (i.e.
            ``['startswith', 'exact', 'lte']``), the ``ALL`` constant or the
            ``ALL_WITH_RELATIONS`` constant.
            """
            # At the declarative level:
            #     filtering = {
            #         'resource_field_name': ['exact', 'gt', 'gte', 'lt', 'lte', 'range'],
            #         'resource_field_name_3': ALL,
            #         'resource_field_name_4': ALL_WITH_RELATIONS,
            #         ...
            #     }
            # Accepts the filters as a dict. None by default, meaning no filters.
            if filters is None:
                filters = {}

            qs_filters = {}

            for filter_expr, value in filters.items():
                filter_bits = filter_expr.split(LOOKUP_SEP)
                field_name = filter_bits.pop(0)
                filter_type = 'exact'

                if not field_name in self.fields:
                    # It's not a field we know about. Move along citizen.
                    continue

                if len(filter_bits) and filter_bits[-1] in QUERY_TERMS.keys():
                    filter_type = filter_bits.pop()

                lookup_bits = self.check_filtering(field_name, filter_type, filter_bits)

                if value in ['true', 'True', True]:
                    value = True
                elif value in ['false', 'False', False]:
                    value = False
                elif value in ('nil', 'none', 'None', None):
                    value = None

                # Split on ',' if not empty string and either an in or range filter.
                if filter_type in ('in', 'range') and len(value):
                    if hasattr(filters, 'getlist'):
                        value = filters.getlist(filter_expr)
                    else:
                        value = value.split(',')

                redis_model_field_name = LOOKUP_SEP.join(lookup_bits)
                qs_filter = "%s%s%s" % (redis_model_field_name, LOOKUP_SEP, filter_type)
                qs_filters[qs_filter] = value

            return dict_strip_unicode_keys(qs_filters)

    def check_filtering(self, field_name, filter_type='exact', filter_bits=None):
        """
        Given a field name, a optional filter type and an optional list of
        additional relations, determine if a field can be filtered on.

        If a filter does not meet the needed conditions, it should raise an
        ``InvalidFilterError``.

        If the filter meets the conditions, a list of attribute names (not
        field names) will be returned.
        """
        if filter_bits is None:
            filter_bits = []

        if not field_name in self._meta.filtering:
            raise InvalidFilterError("The '%s' field does not allow filtering." % field_name)

        # Check to see if it's an allowed lookup type.
        if not self._meta.filtering[field_name] in (ALL, ALL_WITH_RELATIONS):
            # Must be an explicit whitelist.
            if not filter_type in self._meta.filtering[field_name]:
                raise InvalidFilterError("'%s' is not an allowed filter on the '%s' field." % (filter_type, field_name))

        if self.fields[field_name].attribute is None:
            raise InvalidFilterError("The '%s' field has no 'attribute' for searching with." % field_name)

        # Check to see if it's a relational lookup and if that's allowed.
        if len(filter_bits):
            if not getattr(self.fields[field_name], 'is_related', False):
                raise InvalidFilterError("The '%s' field does not support relations." % field_name)

            if not self._meta.filtering[field_name] == ALL_WITH_RELATIONS:
                raise InvalidFilterError("Lookups are not allowed more than one level deep on the '%s' field." % field_name)

            # Recursively descend through the remaining lookups in the filter,
            # if any. We should ensure that all along the way, we're allowed
            # to filter on that field by the related resource.
            related_resource = self.fields[field_name].get_related_resource(None)
            return [self.fields[field_name].attribute] + related_resource.check_filtering(filter_bits[0], filter_type, filter_bits[1:])

        return [self.fields[field_name].attribute]


    def apply_filters(self, request, applicable_filters):
        """
        An ORM-specific implementation of ``apply_filters``.

        Start by extracting any exact filters.
        If there are non-exact filters, use zfilter since that's how Redisco wants to play it
        """

        m = self.get_object_list(request)
        exact_filters = dict([(k.split(LOOKUP_SEP)[0], v) for k,v in applicable_filters.items() if '%sexact' % LOOKUP_SEP in k])
        inexact_filters = dict([(k, v) for k,v in applicable_filters.items() if '%sexact' % LOOKUP_SEP not in k])

        if exact_filters and inexact_filters:
            ol = m.filter(**exact_filters).zfilter(**inexact_filters)
        elif exact_filters:
            ol = m.filter(**exact_filters)
        elif inexact_filters:
            ol = m.zfilter(**inexact_filters)
        else:
            ol = m.all()

        return ol

    def detail_uri_kwargs(self, bundle_or_obj):
        kwargs = {}
        if isinstance(bundle_or_obj, Bundle):
            kwargs['pk'] = bundle_or_obj.obj.id
        else:
            kwargs['pk'] = bundle_or_obj.id

        return kwargs

    def get_resource_uri(self, bundle_or_obj):
        kwargs = {
            'resource_name': self._meta.resource_name,
        }
        if isinstance(bundle_or_obj, Bundle):
            kwargs['pk'] = bundle_or_obj.obj.id
        else:
            kwargs['pk'] = bundle_or_obj.id
        if self._meta.api_name is not None:
            kwargs['api_name'] = self._meta.api_name
        return self._build_reverse_url("api_dispatch_detail", kwargs=kwargs)
