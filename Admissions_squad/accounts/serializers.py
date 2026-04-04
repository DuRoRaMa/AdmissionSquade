from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import CustomUser, Role, UserStudyInfo, Passport
from django.utils import timezone

class UserStudyInfoSerializer(serializers.ModelSerializer):
    faculty_display = serializers.CharField(source='get_faculty_display', read_only=True)
    study_form_display = serializers.CharField(source='get_study_form_display', read_only=True)

    class Meta:
        model = UserStudyInfo
        fields = (
            'id',
            'faculty',
            'faculty_display',
            'student_group',
            'study_form',
            'study_form_display',
        )
class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ('id', 'name',)
class PassportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Passport
        fields = (
            'id',
            'series',
            'number',
            'issued_by',
            'date_of_issue',
            'unit_code',
            'registration_address',
            'full_number',   # свойство модели
        )
        read_only_fields = ('id', 'full_number')
class ProfileUserSerializer(serializers.ModelSerializer):
    memberships = serializers.SerializerMethodField()
    study_info = UserStudyInfoSerializer(read_only=True)      # требует related_name='study_info'
    passport = PassportSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = (
            'email',
            'username',
            'first_name',
            'last_name',
            'middle_name',
            'phone',
            'gender',
            'birth_day',
            'is_blocked',
            'created_at',
            'updated_at',
            'memberships',
            'study_info',
            'passport',
        )
        read_only_fields = (
            'email',
            'username',
            'is_blocked',
            'created_at',
            'updated_at',
            'memberships',
            'study_info',
            'passport',
        )
    def get_memberships(self, obj):
        from squads.serializers import SquadMembershipSerializer
        memberships = obj.membersips.all()  # если related_name = 'membersips'
        return SquadMembershipSerializer(memberships, many=True).data
    # ----- Валидаторы -----
    def validate_phone(self, value):
        if value:
            # При обновлении исключаем текущего пользователя
            if self.instance:
                if CustomUser.objects.filter(phone=value).exclude(pk=self.instance.pk).exists():
                    raise serializers.ValidationError('Этот номер телефона уже используется')
            else:
                # При создании
                if CustomUser.objects.filter(phone=value).exists():
                    raise serializers.ValidationError('Этот номер телефона уже используется')
        return value

    def validate_first_name(self, value):
        if not value:
            raise serializers.ValidationError('Имя обязательно для заполнения.')
        return value

    def validate_last_name(self, value):
        if not value:
            raise serializers.ValidationError('Фамилия обязательна для заполнения.')
        return value

    def validate_birth_day(self, value):
        if value and value > timezone.now().date():
            raise serializers.ValidationError('Дата рождения не может быть в будущем.')
        return value

    # ----- Обновление -----
    def update(self, instance, validated_data):
        # Обновляем только разрешённые поля
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.middle_name = validated_data.get('middle_name', instance.middle_name)
        instance.phone = validated_data.get('phone', instance.phone)
        instance.gender = validated_data.get('gender', instance.gender)
        instance.birth_day = validated_data.get('birth_day', instance.birth_day)

        # Вызываем валидацию модели (clean())
        try:
            instance.full_clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)

        instance.save()
        return instance
class UserListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'middle_name',
                  'full_name', 'is_blocked', 'is_staff', 'date_joined')
    
    def get_full_name(self, obj):
        return obj.get_full_name()
class UserDetailSerializer(serializers.ModelSerializer):
    memberships = serializers.SerializerMethodField()
    study_info = UserStudyInfoSerializer(read_only=True)
    passport = PassportSerializer(read_only=True)
    
    class Meta:
        model = CustomUser
        fields = (
            'id', 'email', 'username', 'first_name', 'last_name', 'middle_name',
            'phone', 'gender', 'birth_day', 'is_blocked', 'is_staff', 'is_active',
            'date_joined', 'created_at', 'updated_at', 'memberships', 'study_info', 'passport'
        )
        read_only_fields = ('id', 'email', 'username', 'is_blocked', 'is_staff', 
                           'is_active', 'date_joined', 'created_at', 'updated_at')
    
    def get_memberships(self, obj):
        from squads.serializers import SquadMembershipSerializer
        memberships = obj.membersips.filter(is_active=True)  # только активные
        return SquadMembershipSerializer(memberships, many=True).data

# --- Сериализатор для админского обновления пользователя ---
class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'middle_name', 'phone', 
                  'gender', 'birth_day', 'is_blocked', 'is_staff')
    
    def validate_phone(self, value):
        if value:
            if self.instance:
                if CustomUser.objects.filter(phone=value).exclude(pk=self.instance.pk).exists():
                    raise serializers.ValidationError('Этот номер телефона уже используется')
            else:
                if CustomUser.objects.filter(phone=value).exists():
                    raise serializers.ValidationError('Этот номер телефона уже используется')
        return value
    
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        try:
            instance.full_clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)
        instance.save()
        return instance
# --- Сериализатор для смены пароля ---
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    confirm_new_password = serializers.CharField(required=True)
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Старый пароль неверен.')
        return value
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({'confirm_new_password': 'Новые пароли не совпадают.'})
        return attrs