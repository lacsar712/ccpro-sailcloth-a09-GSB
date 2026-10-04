from django.contrib import admin

from .models import ClothRoll, DipRun, Loft, PassToken


@admin.register(PassToken)
class PassTokenAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "loft",
        "passphrase",
        "valid_from",
        "valid_until",
        "issued_by",
        "revoked_at",
    )
    list_filter = ("loft", "revoked_at")
    search_fields = ("passphrase",)


admin.site.register(Loft)
admin.site.register(ClothRoll)
admin.site.register(DipRun)
