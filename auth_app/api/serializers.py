from django.contrib.auth.models import User
from rest_framework import serializers


class RegistrationSerializer(serializers.ModelSerializer):
    """Validates registration data and creates a new user."""

    confirmed_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "confirmed_password"]
        extra_kwargs = {
            "password": {"write_only": True},
            "email": {"required": True},
        }

    def validate_email(self, value: str) -> str:
        """Make sure no other user is already registered with this email."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate(self, data: dict) -> dict:
        """Make sure both password fields contain the same value."""
        if data["password"] != data["confirmed_password"]:
            raise serializers.ValidationError(
                {"password": "Passwords do not match."}
            )
        return data

    def create(self, validated_data: dict) -> User:
        """Create the user with a properly hashed password."""
        validated_data.pop("confirmed_password")
        return User.objects.create_user(**validated_data)
