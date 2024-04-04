from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import *
from rest_framework.response import Response
from DamageTrackerAPI.utils.ModelViewSet import ModelViewSet
from rest_framework_simplejwt.tokens import RefreshToken

from DamageTrackerAPI.utils.smsc_api import SMSC
from users_app.models import User, ActivationCode
from users_app.serializers.user_serializers import UserSerializer, UserVerifyCodeSerializer, UserSendCodeSerializer, \
    VictimGetOrCreateSerializer


# Create your views here.
class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    serializer_list = {
        'send-code': UserSendCodeSerializer,
        'verify-code': UserVerifyCodeSerializer,
        'verify-employee-code': UserVerifyCodeSerializer,
        'victim-get-or-create': VictimGetOrCreateSerializer
    }

    def get_permissions(self):
        if self.action in ['send_code', 'verify_code', 'metadata']:
            return [AllowAny()]
        #return [IsAuthenticated()]
        return [AllowAny()]

    @action(detail=False, methods=['post'], url_path='send-code')
    def send_code(self, request):
        serializer = UserSendCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data['phone_number']
        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response({'error': 'Пользователь с таким номером телефона не найден в системе'},
                            status=status.HTTP_404_NOT_FOUND)

        try:
            activation_code = ActivationCode.objects.get(user=user)
            activation_code.code = ActivationCode.generate_activation_code()
            activation_code.save()
        except ActivationCode.DoesNotExist:
            activation_code = ActivationCode.objects.create(user=user)

        if activation_code.code:
            smsc = SMSC()
            r = smsc.send_sms(f'7{user.phone_number}', f"Ваш код: {activation_code.code}",
                              sender="BIK31.RU")
            print('r', r)

        return Response({'message': 'Код активации успешно отправлен'}, status=status.HTTP_200_OK)

    @staticmethod
    def _verify_activation_code(serializer):
        if not serializer.is_valid():
            return Response({'error': 'Неверные данные'}, status=status.HTTP_400_BAD_REQUEST)

        code = serializer.validated_data.get('code')
        try:
            activation_code = ActivationCode.objects.get(code=code)
        except ActivationCode.DoesNotExist:
            return Response({'error': 'Неверный код активации'}, status=status.HTTP_400_BAD_REQUEST)

        if activation_code.is_expired:
            return Response({'error': 'Срок действия кода активации истек'}, status=status.HTTP_400_BAD_REQUEST)

        return activation_code.user

    @action(detail=False, methods=['post'], url_path='verify-employee-code')
    def verify_employee_code(self, request):
        serializer = UserVerifyCodeSerializer(data=request.data)
        user = self._verify_activation_code(serializer)

        if isinstance(user, Response):
            return user

        if not user.is_employee:
            return Response({'error': 'Вы не сотрудник'}, status=status.HTTP_400_BAD_REQUEST)

        jwt = RefreshToken.for_user(user)
        data = {'refresh': str(jwt), 'access': str(jwt.access_token)}
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='verify-code')
    def verify_code(self, request):
        serializer = UserVerifyCodeSerializer(data=request.data)
        user = self._verify_activation_code(serializer)

        if isinstance(user, Response):
            return user

        jwt = RefreshToken.for_user(user)
        data = {'refresh': str(jwt), 'access': str(jwt.access_token)}
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='victim-get-or-create')
    def victim_get_or_create(self, request):
        serializer = VictimGetOrCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data['phone_number']
        user, created = User.objects.get_or_create(phone_number=phone_number)

        return Response({'id': user.id}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)



