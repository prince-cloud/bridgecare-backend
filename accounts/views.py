from . import serializers
from rest_framework.response import Response
from rest_framework import permissions as rest_permissions
from django.utils.translation import gettext_lazy as _
from rest_framework.views import APIView


class ProfileView(APIView):
    serializer_class = serializers.UserSerializer
    permission_classes = (rest_permissions.IsAuthenticated,)

    def get(self, request):
        user = request.user
        serializer = serializers.UserSerializer(
            instance=user,
            many=False,
            context={"request": request},
        )
        return Response(data=serializer.data)
