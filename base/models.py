from django.db import models

class ZohoAccount(models.Model):
    account_name = models.CharField(max_length=255, default="Main Account")
    tenant_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    access_token = models.TextField()
    refresh_token = models.TextField()
    api_domain = models.CharField(max_length=255, default="https://www.zohoapis.com")
    accounts_server = models.CharField(max_length=255, default="https://accounts.zoho.com")
    bookings_service_id = models.CharField(max_length=255, null=True, blank=True)
    bookings_staff_id = models.CharField(max_length=255, null=True, blank=True)
    expiry_time = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Set all other accounts to not primary
            ZohoAccount.objects.filter(is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.account_name
