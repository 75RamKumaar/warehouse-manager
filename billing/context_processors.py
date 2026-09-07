from .models import BusinessProfile, BusinessSettings


def business_settings(request):
    """Makes `biz_settings` available in every template without passing it manually."""
    try:
        profile = BusinessProfile.active()
        return {'biz_settings': profile or BusinessSettings.load(), 'active_profile': profile}
    except Exception:
        # Table may not exist yet (e.g. before first migrate).
        return {}
