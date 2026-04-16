import re

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import (
    CustomUser,
    Passport,
    Role,
    ROLE_PERMISSION_CODES,
    UserStudyInfo,
)


class UserStudyInfoSerializer(serializers.ModelSerializer):
    faculty_display = serializers.CharField(source="get_faculty_display", read_only=True)
    study_form_display = serializers.CharField(source="get_study_form_display", read_only=True)

    class Meta:
        model = UserStudyInfo
        fields = (
            "id",
            "faculty",
            "faculty_display",
            "student_group",
            "study_form",
            "study_form_display",
        )


class RoleShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ("id", "name", "slug")


class RoleSerializer(serializers.ModelSerializer):
    parent_detail = RoleShortSerializer(source="parent", read_only=True)
    effective_permissions = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "parent",
            "parent_detail",
            "permissions",
            "effective_permissions",
            "is_system",
        )
        read_only_fields = ("id", "effective_permissions", "is_system")

    def get_effective_permissions(self, obj):
        return obj.get_all_permissions()

    def validate_slug(self, value):
        value = (value or "").strip().lower()
        if not value:
            raise serializers.ValidationError("Slug обязателен.")
        if not re.fullmatch(r"[a-z0-9_-]+", value):
            raise serializers.ValidationError(
                "Slug может содержать только латинские буквы в нижнем регистре, цифры, дефис и нижнее подчеркивание."
            )
        return value

    def validate_permissions(self, value):
        invalid_permissions = sorted(set(value or []) - set(ROLE_PERMISSION_CODES))
        if invalid_permissions:
            raise serializers.ValidationError(
                f"Неизвестные права: {', '.join(invalid_permissions)}"
            )
        return sorted(set(value or []))

    def validate_parent(self, value):
        if self.instance and value and value.pk == self.instance.pk:
            raise serializers.ValidationError("Роль не может ссылаться сама на себя.")
        return value


class PassportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Passport
        fields = (
            "id",
            "series",
            "number",
            "issued_by",
            "date_of_issue",
            "unit_code",
            "registration_address",
            "full_number",
        )
        read_only_fields = ("id", "full_number")


class ProfileUserSerializer(serializers.ModelSerializer):
    memberships = serializers.SerializerMethodField()
    study_info = UserStudyInfoSerializer(read_only=True)
    passport = PassportSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = (
            "email",
            "username",
            "first_name",
            "last_name",
            "middle_name",
            "phone",
            "gender",
            "birth_day",
            "is_blocked",
            "created_at",
            "updated_at",
            "memberships",
            "study_info",
            "passport",
            "is_staff",
        )
        read_only_fields = (
            "email",
            "username",
            "is_blocked",
            "created_at",
            "updated_at",
            "memberships",
            "study_info",
            "passport",
            "is_staff",
        )

    def get_memberships(self, obj):
        from squads.serializers import SquadMembershipSerializer

        memberships = obj.memberships.select_related("role", "squad").all()
        return SquadMembershipSerializer(memberships, many=True).data

    def validate_phone(self, value):
        if value:
            queryset = CustomUser.objects.filter(phone=value)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError("Этот номер телефона уже используется")
        return value

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)

        instance.save()
        return instance


class UserListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "middle_name",
            "full_name",
            "is_blocked",
            "is_staff",
            "date_joined",
        )

    def get_full_name(self, obj):
        return obj.get_full_name()


class UserDetailSerializer(serializers.ModelSerializer):
    memberships = serializers.SerializerMethodField()
    study_info = UserStudyInfoSerializer(read_only=True)
    passport = PassportSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "middle_name",
            "phone",
            "gender",
            "birth_day",
            "is_blocked",
            "is_staff",
            "is_active",
            "date_joined",
            "created_at",
            "updated_at",
            "memberships",
            "study_info",
            "passport",
        )
        read_only_fields = (
            "id",
            "email",
            "username",
            "is_blocked",
            "is_staff",
            "date_joined",
            "created_at",
            "updated_at",
            "memberships",
            "study_info",
            "passport",
        )

    def get_memberships(self, obj):
        from squads.serializers import SquadMembershipSerializer

        memberships = obj.memberships.select_related("role", "squad").all()
        return SquadMembershipSerializer(memberships, many=True).data


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = (
            "first_name",
            "last_name",
            "middle_name",
            "phone",
            "gender",
            "birth_day",
            "is_blocked",
            "is_staff",
            "is_active",
        )

    def validate_phone(self, value):
        if value:
            queryset = CustomUser.objects.filter(phone=value)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError("Этот номер телефона уже используется")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Старый пароль введен неверно.")
        return value

    def validate_new_password(self, value):
        if value.isdigit():
            raise serializers.ValidationError("Пароль не должен состоять только из цифр.")
        return value