import datetime
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

BADGES = {
    "available": "ok", "completed": "ok",
    "assigned": "info", "active": "info", "scheduled": "info",
    "maintenance": "warn", "in_progress": "warn",
    "retired": "muted", "returned": "muted",
    "lost": "bad", "overdue": "bad",
}


@register.filter
def resolve(obj, path):
    """Follow 'category.name' style paths; call methods; return '' when empty."""
    value = obj
    for part in str(path).split("."):
        if value is None:
            return ""
        value = getattr(value, part, "")
        if callable(value):
            value = value()
    return "" if value is None else value


@register.filter
def badge_class(value):
    return BADGES.get(str(value), "muted")


@register.filter
def naira(value):
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return "-"
    return f"\u20a6{amount:,.2f}"


@register.simple_tag(takes_context=True)
def page_url(context, page):
    """Link to another page of results while keeping the current filters."""
    query = context["request"].GET.copy()
    query["page"] = page
    return "?" + query.urlencode()


@register.filter
def cell(value):
    """Format a report cell: dates as 21 Sep 2026, money with commas."""
    if isinstance(value, datetime.date):
        return value.strftime("%d %b %Y")
    if isinstance(value, Decimal):
        return f"{value:,.2f}"
    return "" if value is None else value
