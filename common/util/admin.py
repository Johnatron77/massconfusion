from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db.models import ManyToManyField, ForeignKey, Model
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString


def create_html_from_links(links: list[str], as_html_list: bool = False) -> SafeString:
    if len(links) == 0:
        return SafeString('')

    if len(links) > 1:
        if as_html_list:
            html = "<ul>"
            for link in links:
                html += f'<li>{link}</li>'
            html += "</ul>"
        else:
            html = ", ".join(links)
    else:
        html = links[0]

    return format_html(html)


def get_content_type_info(obj: Model) -> tuple[str, str]:
    content_type = ContentType.objects.get_for_model(obj)
    app_label = content_type.app_label
    model_name = content_type.model
    return app_label, model_name


def create_link(linked_obj, app_label: Optional[str] = None, label_prop: Optional[str] = None) -> str:
    model_app_label, model_name = get_content_type_info(linked_obj)

    if not app_label and not model_app_label:
        raise ValueError("app_label or model_app_label must be provided")

    if not app_label or (app_label and model_app_label and app_label != model_app_label):
        app_label = model_app_label

    view_name = f"admin:{app_label}_{model_name}_change"
    link_url = reverse(view_name, args=[linked_obj.pk])
    return "<a href='%s'>%s</a>" % (link_url, getattr(linked_obj, label_prop) if label_prop else linked_obj)


def linkify(field_name: str, label_prop: Optional[str] = None, short_description: Optional[str] = None, as_html_list: bool = False):
    def _linkify(obj: Model):
        app_label, _ = get_content_type_info(obj)
        field_type = obj._meta.get_field(field_name)
        items = None

        if isinstance(field_type, ManyToManyField):
            items = list(getattr(obj, field_name).all())
        elif isinstance(field_type, ForeignKey):
            items = [getattr(obj, field_name)]
        else:
            print(f'field_name {field_name} is not ManyToManyField or ForeignKey')

        links = [create_link(itm, app_label, label_prop) for itm in items if itm is not None]

        return create_html_from_links(links, as_html_list)

    _linkify.short_description = [short_description, field_name.replace("_", " ").capitalize()][short_description is None]

    return _linkify
