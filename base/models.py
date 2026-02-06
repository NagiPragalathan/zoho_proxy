from django.db import models

class ZohoAccount(models.Model):
    account_name = models.CharField(max_length=255, default="Main Account")
    access_token = models.TextField()
    refresh_token = models.TextField()
    api_domain = models.CharField(max_length=255, default="https://www.zohoapis.com")
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
