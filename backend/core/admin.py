from django.contrib import admin

from .models import ClothRoll, DipRun, Loft, PassphraseToken

admin.site.register(Loft)
admin.site.register(ClothRoll)
admin.site.register(DipRun)


@admin.register(PassphraseToken)
class PassphraseTokenAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "loft",
        "plaintext",
        "valid_from",
        "valid_until",
        "issued_by",
        "revoked_at",
    )
    list_filter = ("loft", "revoked_at")
    search_fields = ("plaintext", "loft__name")
