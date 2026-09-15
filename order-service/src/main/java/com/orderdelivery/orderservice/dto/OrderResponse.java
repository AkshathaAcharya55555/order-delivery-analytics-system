package com.orderdelivery.orderservice.dto;

import com.orderdelivery.orderservice.entity.Order;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

public class OrderResponse {

    private final Long orderId;
    private final Long customerId;
    private final Long deliveryLocationId;
    private final Long riderId;
    private final String status;
    private final LocalDateTime orderPlacedAt;
    private final BigDecimal totalAmount;
    private final String paymentMethod;
    private final List<OrderItemResponse> items;

    public OrderResponse(Long orderId, Long customerId, Long deliveryLocationId, Long riderId,
                          String status, LocalDateTime orderPlacedAt, BigDecimal totalAmount,
                          String paymentMethod, List<OrderItemResponse> items) {
        this.orderId = orderId;
        this.customerId = customerId;
        this.deliveryLocationId = deliveryLocationId;
        this.riderId = riderId;
        this.status = status;
        this.orderPlacedAt = orderPlacedAt;
        this.totalAmount = totalAmount;
        this.paymentMethod = paymentMethod;
        this.items = items;
    }

    public static OrderResponse from(Order order) {
        List<OrderItemResponse> itemResponses = order.getItems().stream()
                .map(item -> new OrderItemResponse(
                        item.getOrderItemId(),
                        item.getProductName(),
                        item.getCategory(),
                        item.getUnitPrice(),
                        item.getQuantity(),
                        item.computeLineTotal()))
                .collect(Collectors.toList());

        return new OrderResponse(
                order.getOrderId(),
                order.getCustomerId(),
                order.getDeliveryLocationId(),
                order.getRiderId(),
                order.getStatus().name(),
                order.getOrderPlacedAt(),
                order.getTotalAmount(),
                order.getPaymentMethod(),
                itemResponses);
    }

    public Long getOrderId() {
        return orderId;
    }

    public Long getCustomerId() {
        return customerId;
    }

    public Long getDeliveryLocationId() {
        return deliveryLocationId;
    }

    public Long getRiderId() {
        return riderId;
    }

    public String getStatus() {
        return status;
    }

    public LocalDateTime getOrderPlacedAt() {
        return orderPlacedAt;
    }

    public BigDecimal getTotalAmount() {
        return totalAmount;
    }

    public String getPaymentMethod() {
        return paymentMethod;
    }

    public List<OrderItemResponse> getItems() {
        return items;
    }
}
