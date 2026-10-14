from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    vendor = serializers.SerializerMethodField()

    def get_vendor(self, obj):
        if not obj.vendor_id:
            return None
        v = obj.vendor
        return {"id": str(v.id), "name": v.name, "status": v.status}

    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "title",
            "message",
            "vendor",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields
