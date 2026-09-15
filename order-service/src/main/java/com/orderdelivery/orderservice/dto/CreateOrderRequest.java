package com.orderdelivery.orderservice.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import java.util.List;

public class CreateOrderRequest {

    @NotNull(message = "customerId is required")
    private Long customerId;

    @NotNull(message = "deliveryLocationId is required")
    private Long deliveryLocationId;

    @NotNull(message = "paymentMethod is required")
    @Pattern(regexp = "card|cash|wallet|upi", message = "paymentMethod must be one of: card, cash, wallet, upi")
    private String paymentMethod;

    @NotEmpty(message = "items must not be empty")
    @Valid
    private List<OrderItemRequest> items;

    public Long getCustomerId() {
        return customerId;
    }

    public void setCustomerId(Long customerId) {
        this.customerId = customerId;
    }

    public Long getDeliveryLocationId() {
        return deliveryLocationId;
    }

    public void setDeliveryLocationId(Long deliveryLocationId) {
        this.deliveryLocationId = deliveryLocationId;
    }

    public String getPaymentMethod() {
        return paymentMethod;
    }

    public void setPaymentMethod(String paymentMethod) {
        this.paymentMethod = paymentMethod;
    }

    public List<OrderItemRequest> getItems() {
        return items;
    }

    public void setItems(List<OrderItemRequest> items) {
        this.items = items;
    }
}
