from django.contrib import admin

from locations.models import Place, PostalCode


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin[Place]):
    list_display = ("name", "state", "latitude", "longitude")
    list_filter = ("state",)
    search_fields = ("name",)
    readonly_fields = ("key",)


@admin.register(PostalCode)
class PostalCodeAdmin(admin.ModelAdmin[PostalCode]):
    list_display = ("code", "latitude", "longitude")
    search_fields = ("code",)
