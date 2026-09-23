from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from config.pagination import DefaultPagination
from .permissions import AdminModelPermission, IsPlatformAdmin

ACTION_FLAGS = {ADDITION: "add", CHANGE: "change", DELETION: "delete"}


class AdminAuditMixin:
    """Write a django.contrib.admin LogEntry for every mutation made through
    the admin API, so the portal's history pages and recent-actions feed are
    real audit records (and stay consistent with changes made in /crt/)."""

    def _log(self, instance, flag, message):
        LogEntry.objects.create(
            user_id=self.request.user.pk,
            content_type_id=ContentType.objects.get_for_model(instance).pk,
            object_id=str(instance.pk),
            object_repr=str(instance)[:200],
            action_flag=flag,
            change_message=message,
        )

    @staticmethod
    def _snapshot(obj):
        """Raw column values of a model instance, excluding auto timestamps —
        used to diff a record before/after a custom action runs."""
        return {
            f.name: getattr(obj, f.attname)
            for f in obj._meta.concrete_fields
            if not getattr(f, "auto_now", False) and not getattr(f, "auto_now_add", False)
        }

    def get_object(self):
        obj = super().get_object()
        # Snapshot before a possible in-place mutation by a custom @action.
        self._action_snapshot = self._snapshot(obj)
        return obj

    def finalize_response(self, request, response, *args, **kwargs):
        if (
            request.method == "POST"
            and getattr(self, "action", "") not in {"create", "update", "partial_update", "destroy"}
            and 200 <= response.status_code < 400
            and getattr(self, "_action_snapshot", None) is not None
        ):
            pk = self.kwargs.get(self.lookup_field)
            obj = self.get_queryset().filter(pk=pk).first()
            if obj is not None:
                after = self._snapshot(obj)
                changed = sorted(
                    name
                    for name, before in self._action_snapshot.items()
                    if before != after.get(name)
                )
                message = (
                    f"Changed {', '.join(changed)} via {self.action} action (admin portal)."
                    if changed
                    else f"Ran {self.action} action (admin portal)."
                )
                self._log(obj, CHANGE, message)
            self._action_snapshot = None
        return super().finalize_response(request, response, *args, **kwargs)

    def perform_create(self, serializer, **save_kwargs):
        instance = serializer.save(**save_kwargs)
        self._instance = instance
        self._log(instance, ADDITION, "Created via admin portal.")

    def perform_update(self, serializer):
        changed = ", ".join(sorted(k.replace("_", " ") for k in serializer.validated_data)) or "saved"
        instance = serializer.save()
        self._instance = instance
        self._log(instance, CHANGE, f"Changed {changed} (admin portal).")

    def perform_destroy(self, instance):
        self._log(instance, DELETION, "Deleted via admin portal.")
        instance.delete()


class AdminFacetMixin:
    """Generic facet counts for the admin portal's filter sidebar.

    Declare `facet_fields = [...]` on the viewset. Counts are computed over
    the search-filtered queryset, so they respond to what the operator typed.
    """

    facet_fields: list = []

    @action(detail=False, methods=["get"])
    def facets(self, request, *args, **kwargs):
        from django.db.models import Count

        requested = [f for f in request.query_params.getlist("facet") if f in self.facet_fields]
        if not requested:
            requested = list(self.facet_fields)

        search_backend = filters.SearchFilter()
        base_qs = search_backend.filter_queryset(request, self.get_queryset(), self)

        model = self.queryset.model
        result = {}
        for field in requested:
            model_field = model._meta.get_field(field)
            is_fk = model_field.is_relation and (model_field.many_to_one or model_field.one_to_one)
            value_name = f"{field}_id" if is_fk else field

            rows = list(
                base_qs.values(value_name)
                .annotate(n=Count("pk"))
                .order_by("-n")[:200]
            )

            labels = {}
            if is_fk:
                related = model_field.related_model
                ids = [row[value_name] for row in rows if row[value_name] is not None]
                labels = {str(o.pk): str(o) for o in related.objects.filter(pk__in=ids)}

            options = []
            for row in rows:
                raw = row[value_name]
                if raw is None:
                    continue
                if is_fk:
                    value, label = str(raw), labels.get(str(raw), str(raw))
                elif isinstance(raw, bool):
                    value, label = str(raw).lower(), ("Yes" if raw else "No")
                elif getattr(model_field, "choices", None):
                    display = dict(model_field.choices).get(raw)
                    value, label = str(raw), str(display) if display is not None else str(raw)
                else:
                    value, label = str(raw), str(raw)
                options.append({"value": value, "label": label, "count": row["n"]})
            options.sort(key=lambda o: (-o["count"], o["label"]))
            result[field] = options
        return Response(result)


class AdminHistoryMixin:
    """Per-object audit trail from django.contrib.admin's log."""

    @action(detail=True, methods=["get"])
    def history(self, request, *args, **kwargs):
        obj = self.get_object()
        ct = ContentType.objects.get_for_model(obj)
        entries = (
            LogEntry.objects.filter(content_type_id=ct.pk, object_id=str(obj.pk))
            .select_related("user")
            .order_by("-action_time")[:100]
        )
        return Response(
            [
                {
                    "id": str(e.id),
                    "action_time": e.action_time.isoformat(),
                    "user_name": str(e.user) if e.user else "system",
                    "resource": self.queryset.model._meta.model_name,
                    "object_id": str(e.object_id),
                    "object_repr": e.object_repr,
                    "action": ACTION_FLAGS.get(e.action_flag, "change"),
                    "message": e.get_change_message(),
                }
                for e in entries
            ]
        )


class AdminLabelMixin:
    """Attach `<fk>_label` keys to serialized responses, holding str() of the
    related object, so the portal never renders a raw UUID. FKs the serializer
    already labels (e.g. `user_name`) are left alone, and related rows are
    fetched with one query per FK field per page — never per row."""

    _page_objects = None

    def _attach_labels(self, rows, objects):
        if not rows or not objects or len(rows) != len(objects):
            return
        # concrete_fields covers ForeignKey and OneToOneField (M2M is not
        # concrete) — both must be labelled.
        fk_fields = [f for f in objects[0].__class__._meta.concrete_fields if f.is_relation]
        for f in fk_fields:
            sample = rows[0]
            if f.name not in sample or f"{f.name}_label" in sample or f"{f.name}_name" in sample:
                continue
            ids = {getattr(o, f.attname) for o in objects if getattr(o, f.attname) is not None}
            if not ids:
                for row in rows:
                    row[f"{f.name}_label"] = None
                continue
            labels = {str(pk): str(o) for pk, o in f.related_model.objects.in_bulk(ids).items()}
            for row, o in zip(rows, objects):
                val = getattr(o, f.attname)
                row[f"{f.name}_label"] = labels.get(str(val)) if val is not None else None

    def paginate_queryset(self, queryset):
        page = super().paginate_queryset(queryset)
        self._page_objects = list(page) if page is not None else None
        return page

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        page, self._page_objects = self._page_objects, None
        if page and isinstance(response.data, dict):
            self._attach_labels(response.data.get("results", []), page)
        return response

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        data = self.get_serializer(instance).data
        self._attach_labels([data], [instance])
        return Response(data)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        instance = getattr(self, "_instance", None)
        if instance is not None and response.status_code == 201:
            self._attach_labels([response.data], [instance])
        self._instance = None
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        instance = getattr(self, "_instance", None)
        if instance is not None and response.status_code == 200:
            self._attach_labels([response.data], [instance])
        self._instance = None
        return response


class AdminModelViewSet(AdminAuditMixin, AdminLabelMixin, AdminFacetMixin, AdminHistoryMixin, viewsets.ModelViewSet):
    """
    Base for every admin_api resource. Admin-only, paginated, with search,
    filter, and ordering wired up. Resource viewsets set queryset,
    serializer_class, search_fields, filterset_fields, ordering_fields —
    and optionally facet_fields for the portal's filter counts.
    """

    permission_classes = [IsPlatformAdmin, AdminModelPermission]
    pagination_class = DefaultPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    # Most resources use UUID pks, where "-id" ordering is meaningless — defer
    # to each queryset's own default order unless ?ordering= is passed.
    ordering = []

    def get_required_permission(self):
        """Django-model-permission for the current action, e.g.
        accounts.change_user. Custom @actions require the model's change
        permission, matching the Django admin convention."""
        model = self.queryset.model
        app = model._meta.app_label
        name = model._meta.model_name
        if self.action in {"list", "retrieve", "facets", "history"}:
            return f"{app}.view_{name}"
        if self.action == "create":
            return f"{app}.add_{name}"
        if self.action == "destroy":
            return f"{app}.delete_{name}"
        return f"{app}.change_{name}"

    def get_permissions(self):
        self.required_permission = self.get_required_permission()
        return [IsPlatformAdmin(), AdminModelPermission()]


class AdminReadOnlyViewSet(AdminLabelMixin, AdminFacetMixin, AdminHistoryMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only variant for audit/log-style resources. Custom @actions
    declared on these viewsets still require the model's change permission."""

    permission_classes = [IsPlatformAdmin, AdminModelPermission]
    pagination_class = DefaultPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    ordering = []

    def get_required_permission(self):
        model = self.queryset.model
        app = model._meta.app_label
        name = model._meta.model_name
        if self.action in {"list", "retrieve", "facets", "history"}:
            return f"{app}.view_{name}"
        return f"{app}.change_{name}"

    def get_permissions(self):
        self.required_permission = self.get_required_permission()
        return [IsPlatformAdmin(), AdminModelPermission()]
