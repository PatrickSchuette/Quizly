from django.contrib.auth.models import User
from rest_framework import serializers


class RegistrationSerializer(serializers.ModelSerializer):
    """Validate the registration data and create a new user account.

    The serializer receives the data of the registration form: username,
    email, password and a second password field (``confirmed_password``).
    It checks that the email address is not used yet and that both
    passwords match. If everything is valid, it creates the user with a
    hashed password.

    Both password fields are write-only, so they are never sent back in a
    response.
    """

    confirmed_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "confirmed_password"]
        extra_kwargs = {
            "password": {"write_only": True},
            "email": {"required": True},
        }

    def validate_email(self, value: str) -> str:
        """Check that the email address is not used by another user yet.

        Django's ``User`` model does not require unique email addresses, so
        this check makes sure that every email address can only be registered
        once.

        Args:
            value: The email address from the registration form.

        Returns:
            The unchanged email address if no other user uses it.

        Raises:
            serializers.ValidationError: If a user with this email address
                already exists.
        """
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate(self, data: dict) -> dict:
        """Check that both password fields contain the same value.

        This method runs after the checks of the single fields and has access
        to all fields at once. This is needed to compare ``password`` with
        ``confirmed_password``.

        Args:
            data: All validated fields of the registration form.

        Returns:
            The unchanged data if both passwords match.

        Raises:
            serializers.ValidationError: If the two passwords are different.
                The error is attached to the ``password`` field.
        """
        if data["password"] != data["confirmed_password"]:
            raise serializers.ValidationError(
                {"password": "Passwords do not match."}
            )
        return data

    def create(self, validated_data: dict) -> User:
        """Create and save the new user with a hashed password.

        ``User.objects.create_user`` is used instead of
        ``User.objects.create``, because only ``create_user`` hashes the
        password before it is stored.
        The field ``confirmed_password`` is only needed for the validation and
        is not saved.

        Args:
            validated_data: The data that passed all validation checks.

        Returns:
            The newly created user.
        """
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
