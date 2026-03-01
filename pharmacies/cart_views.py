from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .cart_service import CartService
from .models import Drug


class CartItemInputSerializer(serializers.Serializer):
    """Serializer for adding items to cart - only drug_id and quantity needed"""

    drug_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)

    def validate_drug_id(self, value):
        try:
            drug = Drug.objects.select_related("pharmacy").get(id=value)
            self.context["drug"] = drug
        except Drug.DoesNotExist:
            raise serializers.ValidationError("Drug not found")
        return str(value)

    def validate(self, attrs):
        attrs["drug"] = self.context.get("drug")
        return attrs


class CartUpdateSerializer(serializers.Serializer):
    """Serializer for updating cart item quantity"""

    drug_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=0)

    def validate_drug_id(self, value):
        try:
            drug = Drug.objects.select_related("pharmacy").get(id=value)
            self.context["drug"] = drug
        except Drug.DoesNotExist:
            raise serializers.ValidationError("Drug not found")
        return str(value)

    def validate(self, attrs):
        attrs["drug"] = self.context.get("drug")
        return attrs


class CartPrescriptionSerializer(serializers.Serializer):
    """Serializer for setting prescription code"""

    prescription_code = serializers.CharField(max_length=100)


class CartItemOutputSerializer(serializers.Serializer):
    """Serializer for cart item output"""

    drug_id = serializers.CharField()
    drug_name = serializers.CharField()
    drug_image = serializers.CharField(allow_null=True)
    base_unit = serializers.CharField(allow_null=True)
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    pharmacy_id = serializers.CharField()
    pharmacy_name = serializers.CharField()


class PharmacyGroupSerializer(serializers.Serializer):
    """Serializer for items grouped by pharmacy"""

    pharmacy_id = serializers.CharField()
    pharmacy_name = serializers.CharField()
    items = CartItemOutputSerializer(many=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)


class CartOutputSerializer(serializers.Serializer):
    """Serializer for cart output"""

    items = CartItemOutputSerializer(many=True)
    # items_by_pharmacy = PharmacyGroupSerializer(many=True)
    total_items = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    prescription_code = serializers.CharField(allow_null=True)


class CartView(APIView):
    """
    API view for managing shopping cart stored in Redis.
    Cart is user-based and can contain items from multiple pharmacies.
    Cart items expire after 18 hours automatically.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses={200: CartOutputSerializer},
    )
    def get(self, request):
        """Get all cart items for the authenticated user"""
        user_id = str(request.user.id)
        cart = CartService.get_cart(user_id)

        return Response(
            CartOutputSerializer(cart).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=CartItemInputSerializer,
        responses={201: CartOutputSerializer},
    )
    def post(self, request):
        """Add an item to the cart"""
        serializer = CartItemInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        drug = serializer.validated_data["drug"]
        pharmacy = drug.pharmacy  # Get pharmacy from drug's ForeignKey
        user_id = str(request.user.id)

        # Get drug image URL
        drug_image = None
        if drug.image:
            drug_image = request.build_absolute_uri(drug.image.url)

        cart = CartService.add_item(
            user_id=user_id,
            pharmacy_id=str(pharmacy.id),
            pharmacy_name=pharmacy.pharmacy_name,
            drug_id=str(drug.id),
            drug_name=drug.name,
            quantity=serializer.validated_data["quantity"],
            unit_price=drug.unit_price,
            drug_image=drug_image,
            base_unit=drug.base_unit,
        )

        return Response(
            CartOutputSerializer(cart).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=CartUpdateSerializer,
        responses={200: CartOutputSerializer},
    )
    def patch(self, request):
        """Update item quantity in the cart"""
        serializer = CartUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        drug = serializer.validated_data["drug"]
        user_id = str(request.user.id)
        pharmacy_id = str(drug.pharmacy.id)  # Get pharmacy from drug's ForeignKey
        drug_id = str(serializer.validated_data["drug_id"])
        quantity = serializer.validated_data["quantity"]

        cart = CartService.update_item_quantity(
            user_id=user_id,
            pharmacy_id=pharmacy_id,
            drug_id=drug_id,
            quantity=quantity,
        )

        return Response(
            CartOutputSerializer(cart).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="drug_id",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="UUID of the drug to remove",
            ),
        ],
        responses={200: CartOutputSerializer},
    )
    def delete(self, request):
        """Remove an item from the cart"""
        drug_id = request.query_params.get("drug_id")

        if not drug_id:
            return Response(
                {"error": "drug_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get pharmacy from drug's ForeignKey
        try:
            drug = Drug.objects.select_related("pharmacy").get(id=drug_id)
            pharmacy_id = str(drug.pharmacy.id)
        except Drug.DoesNotExist:
            return Response(
                {"error": "Drug not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        user_id = str(request.user.id)

        cart = CartService.remove_item(
            user_id=user_id,
            pharmacy_id=pharmacy_id,
            drug_id=drug_id,
        )

        return Response(
            CartOutputSerializer(cart).data,
            status=status.HTTP_200_OK,
        )


class CartClearView(APIView):
    """API view for clearing the cart"""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="pharmacy_id",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="UUID of the pharmacy. If provided, clears only items from that pharmacy. If not provided, clears entire cart.",
            ),
        ],
        responses={
            200: {"type": "object", "properties": {"message": {"type": "string"}}}
        },
    )
    def delete(self, request):
        """
        Clear items from the cart.
        If pharmacy_id is provided, clears only items from that pharmacy.
        If no pharmacy_id, clears entire cart.
        """
        pharmacy_id = request.query_params.get("pharmacy_id")
        user_id = str(request.user.id)

        CartService.clear_cart(user_id, pharmacy_id)

        if pharmacy_id:
            message = f"Items from pharmacy {pharmacy_id} cleared from cart"
        else:
            message = "Cart cleared successfully"

        return Response(
            {"message": message},
            status=status.HTTP_200_OK,
        )


class CartPrescriptionView(APIView):
    """API view for associating a prescription with the cart"""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=CartPrescriptionSerializer,
        responses={200: CartOutputSerializer},
    )
    def post(self, request):
        """Associate a prescription code with the cart"""
        serializer = CartPrescriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = str(request.user.id)
        prescription_code = serializer.validated_data["prescription_code"]

        cart = CartService.set_prescription_code(
            user_id=user_id,
            prescription_code=prescription_code,
        )

        return Response(
            CartOutputSerializer(cart).data,
            status=status.HTTP_200_OK,
        )
